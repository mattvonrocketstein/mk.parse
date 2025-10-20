# BEGIN: Project Automation
#
# USAGE: 
#   make clean build test
#   make normalize static-analysis
#░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

.SHELL := bash
MAKEFLAGS += --warn-undefined-variables
.DEFAULT_GOAL := help

THIS_MAKEFILE := $(abspath $(firstword $(MAKEFILE_LIST)))
SRC_ROOT := $(shell dirname ${THIS_MAKEFILE})
docs.root=docs/

py.src_root:=src
img.ref=compose.mk:mkp
img.official=ghcr.io/mattvonrocketstein/mk.parse:v1.2.4
# img.ref=`case $${GITHUB_ACTIONS:-false} in false) echo ${img.local};; *) echo ${img.official};; esac`
dexec=docker run -v `pwd`:/workspace -w /workspace ${img.ref} $${args:-} 

include .cmk/compose.mk
$(call docker.import, namespace=mkp file=Dockerfile)
$(call mk.import.plugins, py.mk actions.mk docs.mk json.mk)

__main__: help.local

clean: flux.stage/clean mk.clean py.clean docker.clean

docker.clean:; force=1 ${make} docker.rmi/${img.official}
	@# Clean project docker images

mk.clean:; rm -f .tmp.*
	@# Cleans `.tmp.*` files

init: flux.stage/init mk.stat docker.stat pip.install/tox pip.install/uv
	@# Project init. 

build: flux.stage/build flux.timer/mkp.build
	@# Builds the docker container for this project

install:
	@# Global install (requires sudo)
	set -x && chmod +x ./src/mk.parse.py \
	&& cp ./src/mk.parse.py /usr/local/bin/mk.parse

test: flux.stage/test
	./src/mk.parse.py cblocks Makefile
	args='targets Makefile' && ${dexec}
	args='targets Makefile --locals' && ${dexec}
	args='targets Makefile --public' && ${dexec}
	args='targets Makefile --private' && ${dexec}
	args='targets Makefile --prefix build' && ${dexec}

#░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

$(call tox.import, normalize static-analysis)
validate lint: static-analysis
normalize: tox.normalize.dispatch/py.normalize

self.normalize:
	pushd src; shed; popd; 
	autopep8 --recursive --in-place src
	isort --settings-file .isort.cfg src
	(ruff check src --fix || true)
	( docformatter --recursive --in-place --wrap-descriptions 65 \
		--wrap-summaries 65 --pre-summary-newline --make-summary-multi-line src \
		|| true )

self.static-analysis:
	$(call log.target, ${no_ansi}source code ${sep} flake8 and vulture)
	flake8 --config .flake8 src
	vulture src --min-confidence 90
	$(call log.target, interrogate ${sep} docstring coverage follows)
	(interrogate -v src/ || true)
