#!/bin/sh
set -e

# Apply any pending database migrations before serving. Idempotent — safe to
# run on every boot; a schema that is already current is a no-op.
flask db upgrade

# Hand off to gunicorn as PID 1 (via exec) so container stop/restart signals
# propagate cleanly to the workers.
exec gunicorn \
    --bind "0.0.0.0:${PORT:-5000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile - \
    app:app
