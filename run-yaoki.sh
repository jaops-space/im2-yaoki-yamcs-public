#!/usr/bin/env bash
set -euo pipefail

# Check if this image exists.  Build or load appropriately
if ! docker compose images -q | grep -q .; then
    docker compose up --build -d
else
    docker compose up -d
fi

# Now wait for the docker to actually load.
echo "Waiting for services..."
until docker exec "$(docker compose ps -q)" test -f /ready 2>/dev/null; do :; done
echo "Ready."

# Now open the two browser windows
YAMCS_URL="http://localhost:8090"                                   # Yamcs GUI
JUPYTER_URL="http://localhost:8888/lab/tree/analysis/yamcs_archive.ipynb" # Jupyter notebook

if command -v xdg-open >/dev/null 2>&1; then
    open_cmd="xdg-open"
elif command -v open >/dev/null 2>&1; then
    open_cmd="open" # macOS
else
    open_cmd=""
fi

if [[ -n "$open_cmd" ]]; then
    "$open_cmd" "$YAMCS_URL" &
    "$open_cmd" "$JUPYTER_URL" &
else
    echo "Could not auto-open a browser. Open these URLs manually:"
    echo "  Yamcs GUI: $YAMCS_URL"
    echo "  Jupyter:   $JUPYTER_URL"
fi

# docker compose logs -f # And show the user the logs
echo "Services running. View logs with: docker compose logs -f"
