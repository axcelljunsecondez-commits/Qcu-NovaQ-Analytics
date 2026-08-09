#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "Seeding admin user..."
    python -m backend.db.seed --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" --role admin
fi

echo "Starting API..."
exec uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
