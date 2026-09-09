#!/bin/sh
set -e

python -m backend.operations.preflight

echo "Starting API as an unprivileged user..."
exec uvicorn backend.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${API_WORKERS:-1}" \
    --limit-concurrency "${API_LIMIT_CONCURRENCY:-32}" \
    --timeout-graceful-shutdown "${API_GRACEFUL_SHUTDOWN_SECONDS:-30}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
    --no-access-log
