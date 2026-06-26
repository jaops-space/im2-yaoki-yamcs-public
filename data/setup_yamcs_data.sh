#!/usr/bin/env bash
# Populate data/yamcs-data/ from the S3 yamcs-data snapshot.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v aws >/dev/null 2>&1; then
    echo "Error: aws CLI not found. Install it with: sudo apt install awscli" >&2
    exit 1
fi

SRC="s3://im2-yaoki-rover/yamcs-data/"
REGION="ap-northeast-1"
DST="yamcs-data"

rm -rf "$DST"
mkdir -p "$DST"
aws s3 cp "$SRC" "$DST"/ --recursive --region "$REGION"

echo "Copied $SRC -> $DST"
