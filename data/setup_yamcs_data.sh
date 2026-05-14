#!/usr/bin/env bash
# Populate data/yamcs-data/ from the initial snapshot in data/yamcs-data-initial/.
set -euo pipefail

cd "$(dirname "$0")"

SRC="yamcs-data-initial"
DST="yamcs-data"

if [[ ! -d "$SRC" ]]; then
    echo "Error: source directory '$SRC' not found." >&2
    exit 1
fi

rm -rf "$DST"
mkdir -p "$DST"
cp -a "$SRC"/. "$DST"/

echo "Copied $SRC -> $DST"
