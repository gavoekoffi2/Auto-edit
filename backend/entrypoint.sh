#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head 2>/dev/null || echo "Warning: migrations skipped (database may not be ready yet)"

echo "Starting application..."
exec "$@"
