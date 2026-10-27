#!/bin/bash
set -e

echo "=== Starting Sewa Setu Multi-Service Engine ==="

# Add postgres binaries to PATH if present
for p in /usr/lib/postgresql/*/bin; do
    [ -d "$p" ] && export PATH="$p:$PATH"
done

# 1. Start PostgreSQL (Try system service first, fallback to user-space postgres)
echo "[1/4] Starting PostgreSQL..."
if command -v service >/dev/null 2>&1 && sudo -n service postgresql start >/dev/null 2>&1; then
    echo "Started postgres via system service."
    sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = 'sewasetu'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE USER sewasetu WITH SUPERUSER PASSWORD 'sewasetu123';"

    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'sewasetu'" | grep -q 1 || {
        sudo -u postgres psql -c "CREATE DATABASE sewasetu OWNER sewasetu;"
        sudo -u postgres psql -d sewasetu -f app/schema.sql
        sudo -u postgres psql -d sewasetu -f seed/seed.sql
    }
else
    echo "Starting postgres in user-space..."
    PGDATA="/tmp/pgdata"
    if [ ! -d "$PGDATA" ]; then
        mkdir -p "$PGDATA"
        initdb -D "$PGDATA" -U sewasetu --auth=trust
        postgres -D "$PGDATA" -p 5432 -k /tmp &
        sleep 4
        createdb -h 127.0.0.1 -p 5432 -U sewasetu sewasetu
        psql -h 127.0.0.1 -p 5432 -U sewasetu -d sewasetu -f app/schema.sql
        psql -h 127.0.0.1 -p 5432 -U sewasetu -d sewasetu -f seed/seed.sql
    else
        postgres -D "$PGDATA" -p 5432 -k /tmp &
        sleep 3
    fi
fi

# 2. Environment configuration
export PGHOST=127.0.0.1
export PGPORT=5432
export PGDATABASE=sewasetu
export PGUSER=sewasetu
export PGPASSWORD=sewasetu123
export SMS_GATEWAY_URL=http://127.0.0.1:8025
export MCP_SERVER_URL=http://127.0.0.1:8001
export PORTAL_URL=http://127.0.0.1:7860
export PUBLIC_BASE_URL=${SPACE_HOST:+https://$SPACE_HOST}
export PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-http://localhost:7860}
export AUTH_REQUIRED=true
export UPLOAD_DIR=/tmp/sewasetu/uploads
export PYTHONPATH=.:app

mkdir -p /tmp/sewasetu/uploads /tmp/sewasetu/logs

# Run deemed approval initial pass
python3 app/scripts/deemed_approval.py || true

# 3. Start SMS Gateway in background
echo "[2/4] Starting SMS Gateway on port 8025..."
python3 smsgw/app.py &

# 4. Start Dual MCP Server in background
echo "[3/4] Starting MCP Server on port 8001..."
python3 -m uvicorn mcp_server.server:app --host 127.0.0.1 --port 8001 &

sleep 3

# 5. Start Main Sewa Setu Portal on port 7860
echo "[4/4] Starting Sewa Setu Portal on port ${PORT:-7860}..."
export PORT=${PORT:-7860}
exec python3 app/app.py
