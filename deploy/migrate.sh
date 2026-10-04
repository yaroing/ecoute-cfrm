#!/bin/sh
set -eu
POSTGRES_USER=feedback_owner POSTGRES_PASSWORD="$OWNER_PASSWORD" python manage.py migrate --noinput
SENSITIVE_USER=feedback_sensitive_owner SENSITIVE_PASSWORD="$SENSITIVE_OWNER_PASSWORD" python manage.py migrate --database sensible --noinput
PGHOST=db PGDATABASE=feedback PGUSER=feedback_owner PGPASSWORD="$OWNER_PASSWORD" psql -v ON_ERROR_STOP=1 <<'SQL'
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO feedback_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO feedback_app;
REVOKE UPDATE, DELETE, TRUNCATE ON core_audit FROM feedback_app;
CREATE OR REPLACE VIEW feedback_summary AS SELECT channel, type, theme, zone, state, count(*) AS total FROM core_dossier WHERE NOT sensitive GROUP BY channel, type, theme, zone, state;
GRANT SELECT ON feedback_summary TO feedback_report;
SQL
PGHOST=db PGDATABASE=feedback PGUSER=feedback_sensitive_owner PGPASSWORD="$SENSITIVE_OWNER_PASSWORD" psql -v ON_ERROR_STOP=1 <<'SQL'
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA sensible TO feedback_sensitive;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sensible TO feedback_sensitive;
SQL
