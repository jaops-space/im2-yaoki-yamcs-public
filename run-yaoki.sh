#!/usr/bin/env bash
set -euo pipefail

if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to wait for Yamcs and Jupyter to be reachable."
    exit 1
fi

# Check if this image exists.  Build or load appropriately
if ! docker compose images -q | grep -q .; then
    docker compose up --build -d
else
    docker compose up -d
fi

# Now wait for the services to actually answer on the host ports that the
# browser will use. This avoids stale container readiness markers after restart.
wait_for_url() {
    local name="$1"
    local url="$2"

    printf 'Waiting for %s at %s' "$name" "$url"
    until curl -fsS "$url" >/dev/null 2>&1; do
        printf '.'
        sleep 1
    done
    printf '\n'
}

wait_for_url "Yamcs" "http://localhost:8090"
wait_for_url "Jupyter" "http://localhost:8888/lab"
echo "Ready."

# Now open the two browser windows
YAMCS_URL="http://localhost:8090"                                   # Yamcs GUI
JUPYTER_URL="http://localhost:8888/lab/tree/analysis/yamcs_archive.ipynb" # Jupyter notebook

kernel_name="$(uname -s)"

if [[ "$kernel_name" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
    open_cmd="open" # macOS
elif grep -qi microsoft /proc/version 2>/dev/null && command -v wslview >/dev/null 2>&1; then
    open_cmd="wslview" # WSL
elif command -v xdg-open >/dev/null 2>&1; then
    open_cmd="xdg-open" # Linux
else
    open_cmd=""
fi

echo "Yamcs GUI: $YAMCS_URL"
echo "Jupyter:   $JUPYTER_URL"

if [[ -n "$open_cmd" ]]; then
    "$open_cmd" "$YAMCS_URL" >/dev/null 2>&1 || echo "Could not auto-open Yamcs GUI."
    sleep 1
    "$open_cmd" "$JUPYTER_URL" >/dev/null 2>&1 || echo "Could not auto-open Jupyter."
else
    echo "Could not auto-open a browser. Open these URLs manually:"
    echo "  Yamcs GUI: $YAMCS_URL"
    echo "  Jupyter:   $JUPYTER_URL"
fi

# docker compose logs -f # And show the user the logs
echo "Services running. View logs with: docker compose logs -f"
