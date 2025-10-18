#!/usr/bin/env -S make -s -S -f 
##
# Project Automation
#
# Typical usage: `make clean build test`
##
SHELL := bash
.SHELLFLAGS?=-euo pipefail -c
MAKEFLAGS=-s -S --warn-undefined-variables
THIS_MAKEFILE:=$(abspath $(firstword $(MAKEFILE_LIST)))

export SRC_ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)
export PROJECT_ROOT := $(shell dirname ${THIS_MAKEFILE})
export CMK_PLUGINS_DIR=${SRC_ROOT}/.cmk
docs.root=docs/

include ${CMK_PLUGINS_DIR}/compose.mk
$(call mk.import.plugins, actions.mk docs.mk py.mk)
$(call docker.import, namespace=mkp file=Dockerfile)
img=compose.mk:mkp
export quiet=0

__main__: help #build
build: mkp.build

init: py.init py.pkg.install/test
# smoke-test: mkp.dispatch/self.smoke_test
# self.smoke_test:
dexec=docker run -v `pwd`:/workspace -w /workspace \
		--entrypoint /opt/mkp/py-mkp.py ${img} $${args:-} Makefile | ${jq} .
test: 
	${dexec}
	args='--locals' ${dexec}

# $(call tox.import, ruff type-check docs-build venv normalize itest stest utest)
$(call tox.import, normalize static-analysis)
normalize: tox.normalize.dispatch/py.normalize
# validate lint: validate.compose validate.json validate.makefiles static-analysis
# validate.makefiles: mk.validate/mcp/automation.mk 
self.static-analysis: py.static-analysis
# -v /var/run/docker.sock:/var/run/docker.sock

zonk:; echo foo