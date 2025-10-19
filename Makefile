# Project Automation
#░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

.SHELL := bash
# .SHELLFLAGS := -euo pipefail -c
MAKEFLAGS += --warn-undefined-variables
.DEFAULT_GOAL := help

THIS_MAKEFILE := $(abspath $(firstword $(MAKEFILE_LIST)))
SRC_ROOT := $(shell dirname ${THIS_MAKEFILE})
docs.root=docs/
# export CMK_LOG_IMPORTS?=1
export COMPOSE_PROFILES?=all
export MKDOCS_LISTEN_PORT=8003
export MCP_WORKSPACE_TAG?=mcp_workspace:local

py.src_root:=*.py
img.local=compose.mk:mkp
img.official=ghcr.io/mattvonrocketstein/mk.parse:v1.2.4
img.ref=`case $${GITHUB_ACTIONS:-false} in false) echo ${img.local};; *) echo ${img.official};; esac`
dexec=docker run -v `pwd`:/workspace -w /workspace ${img.ref} $${args:-} 

include .cmk/compose.mk
$(call docker.import, namespace=mkp file=Dockerfile)
$(call mk.import.plugins, py.mk actions.mk docs.mk json.mk)

#░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
__main__: help.local

clean: flux.stage/clean mk.clean py.clean docker.clean

docker.clean:; force=1 ${make} docker.rmi/${img.official}
	@# Clean project docker images

mk.clean:; rm -f .tmp.*
	@# Cleans `.tmp.*` files

init: flux.stage/init mk.stat docker.stat py.pip.install/tox pip.install/uv
	@# Project init. 

build: flux.stage/build flux.timer/mkp.build
	@# Project build. 

serve: workspace.serve


test: flux.stage/test
	args='targets Makefile' && ${dexec}
	args='targets Makefile --locals' && ${dexec}
	

$(call tox.import, normalize static-analysis)
validate lint: static-analysis
normalize: tox.normalize.dispatch/py.normalize
self.normalize: py.normalize
self.static-analysis: py.static-analysis
