#!/usr/bin/env bash
# Fixture for Tier B symbols (Shell).
set -euo pipefail

build() {
  echo "build"
  inner_helper() { :; }
}

function deploy {
  build
}

function rollback() {
  :
}
