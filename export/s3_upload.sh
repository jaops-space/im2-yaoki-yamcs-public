#!/usr/bin/env bash
# Uploads data to S3 for public release
# Note: Lunar Ledger AWS credentials required
set -euo pipefail

BUCKET="s3://im2-yaoki-rover-public"
REGION="ap-northeast-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

aws s3 cp "$REPO/LICENSE.txt" "$BUCKET/" --region "$REGION"
aws s3 cp "$REPO/PublicRelease_Overview_Lunar_Ledger_YAOKI_Dymon_JAOPS.pdf" "$BUCKET/" --region "$REGION"
aws s3 cp "$REPO/PublicRelease_YAOKI_IM2_data_analysis_by_JAOPS.pdf" "$BUCKET/" --region "$REGION"
aws s3 cp "$REPO/im2-yaoki-rover.yaml" "$BUCKET/" --region "$REGION"
aws s3 cp "$REPO/export/yaoki_parquet/" "$BUCKET/timeseries/" --recursive --region "$REGION"
aws s3 cp "$REPO/data/reconstructed_images/" "$BUCKET/images/" --recursive --region "$REGION"

# S3 bucket browser (aws-js-s3-explorer) — single-file static app
aws s3 cp "$REPO/export/s3-explorer/index.html" "$BUCKET/" --region "$REGION"

# only the first time:
# aws s3 cp "$REPO/data/yamcs-data-initial/" "$BUCKET/yamcs-data/" --recursive --region "$REGION"
