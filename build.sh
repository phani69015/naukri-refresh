#!/usr/bin/env bash
# Builds build/function.zip for Lambda (python3.12, x86_64 or arm64 — requests is pure Python).
set -euo pipefail
cd "$(dirname "$0")"
[ -f resume.pdf ] || { echo "Put your resume at ./resume.pdf first" >&2; exit 1; }
rm -rf build && mkdir -p build/pkg
pip install -q -r requirements.txt -t build/pkg
cp handler.py naukri.py resume.pdf build/pkg/
(cd build/pkg && zip -qr ../function.zip .)
echo "Built build/function.zip"
