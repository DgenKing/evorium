#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
node tools/web3d/optimise.mjs
