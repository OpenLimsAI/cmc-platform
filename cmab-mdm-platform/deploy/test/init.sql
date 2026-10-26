-- Synthetic credentials only, for a new tmpfs PostgreSQL instance with no host ports.
CREATE ROLE cmab_app LOGIN PASSWORD 'phase1-ci-app-only';
CREATE ROLE cmab_audit_reader NOLOGIN;
