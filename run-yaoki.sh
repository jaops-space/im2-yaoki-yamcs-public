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

# Now open the two broswer windows
xdg-open http://localhost:8090 & # Yamcs GUI
xdg-open http://localhost:8888/lab/tree/analysis/yamcs_archive.ipynb & # Jupyter notebook

docker compose logs -f # And show the user the logs
