#!/bin/sh
set -e

# Creates temporal databases for Temporal auto-setup on first run
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE temporal'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal')\gexec

    SELECT 'CREATE DATABASE temporal_visibility'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility')\gexec

    GRANT ALL PRIVILEGES ON DATABASE temporal TO "$POSTGRES_USER";
    GRANT ALL PRIVILEGES ON DATABASE temporal_visibility TO "$POSTGRES_USER";
EOSQL

