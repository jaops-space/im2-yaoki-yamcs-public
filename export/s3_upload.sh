#!/usr/bin/env bash
# Uploads data to S3 for public release
# Note: JAOPS AWS credentials required
set -euo pipefail

BUCKET="s3://im2-yaoki-rover"
REGION="ap-northeast-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

aws s3 cp "$REPO/PublicRelease_YAOKI_IM2_data_analysis_by_JAOPS.pdf" "$BUCKET/" --region "$REGION"
aws s3 cp "$REPO/im2-yaoki-rover.yaml" "$BUCKET/" --region "$REGION"
aws s3 cp "$REPO/export/yaoki_parquet/" "$BUCKET/timeseries/" --recursive --region "$REGION"
aws s3 cp "$REPO/data/reconstructed_images/" "$BUCKET/images/" --recursive --region "$REGION"
aws s3 cp "$REPO/data/yamcs-data-initial/" "$BUCKET/yamcs-data/" --recursive --region "$REGION"
