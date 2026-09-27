#!/bin/bash
# Sample host load and per-container CPU and memory while a load run is going,
# for docs/load-testing-demo.md (issue #212). Run it on the pilot host, in a
# second shell, just before pilot_load.py starts on the client; stop it with
# Ctrl-C when the run ends.
#
#   scripts/loadtest/host_stats.sh 2 > /tmp/pilot-load-host.csv
#
# One CSV row per container per sample: UTC time, the 1-minute load average,
# the container name, and what `docker stats` reports for it. Container names
# carry the Compose project, so the file says which API container was busy.
# Nothing in it identifies a user or a request.
#
# `docker stats --no-stream` takes a second or two to sample CPU, so rows land
# every INTERVAL plus that, and each row's time is when its sample began. A
# failed sample (the daemon busy, a container being recreated) writes one
# docker-stats-failed row and the sampler keeps going.
set -euo pipefail

INTERVAL=${1:-2}
if ! [[ $INTERVAL =~ ^[0-9]+$ ]] || [ "$INTERVAL" -lt 1 ]; then
  echo "usage: $0 [seconds between samples, default 2]" >&2
  exit 2
fi

echo "time_utc,load_1m,container,cpu_percent,mem_usage,mem_percent"
while true; do
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  load=$(cut -d ' ' -f 1 /proc/loadavg)
  if ! docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}' |
    while IFS= read -r line; do
      echo "$now,$load,$line"
    done; then
    echo "$now,$load,docker-stats-failed,,,"
  fi
  sleep "$INTERVAL"
done
