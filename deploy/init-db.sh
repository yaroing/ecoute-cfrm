#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username postgres --dbname feedback \
  -v app="$APP_PASSWORD" -v sensitive="$SENSITIVE_PASSWORD" -v owner="$OWNER_PASSWORD" \
  -v sensitive_owner="$SENSITIVE_OWNER_PASSWORD" -v report="$REPORT_PASSWORD" <<'SQL'
CREATE ROLE feedback_owner LOGIN PASSWORD :'owner';
CREATE ROLE feedback_sensitive_owner LOGIN PASSWORD :'sensitive_owner';
CREATE ROLE feedback_app LOGIN PASSWORD :'app';
CREATE ROLE feedback_sensitive LOGIN PASSWORD :'sensitive';
CREATE ROLE feedback_report LOGIN PASSWORD :'report';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO feedback_owner;
CREATE SCHEMA sensible AUTHORIZATION feedback_sensitive_owner;
REVOKE ALL ON SCHEMA sensible FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO feedback_app, feedback_report;
GRANT USAGE ON SCHEMA sensible TO feedback_sensitive;
ALTER ROLE feedback_sensitive SET search_path = sensible;
ALTER ROLE feedback_sensitive_owner SET search_path = sensible;
GRANT ALL ON DATABASE feedback TO feedback_owner;
SQL
