#!/bin/sh
set -e

# Run migrations before starting the process.
# The Celery worker sets MIGRATE_ON_STARTUP=false so only one
# service migrates at a time.
if [ "${MIGRATE_ON_STARTUP:-true}" = "true" ]; then
    echo "Applying database migrations..."
    alembic upgrade head
fi

exec "$@"
