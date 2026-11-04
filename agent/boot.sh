#!/bin/sh
# Single image CMD (design: Boot). ADOT wraps the process only for the AgentCore backend.
set -e
if [ "${HARNESS_EXPORTER:-adot}" = "adot" ]; then
  exec opentelemetry-instrument python -m agent.main
fi
exec python -m agent.main
