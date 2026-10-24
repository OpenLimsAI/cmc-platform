"""rehome cmc_data_platform to rd_pg container; drop meta / raw_qc_lims schemas

Revision ID: 004
Revises: 003
Create Date: 2026-06-03

Background:
    Between 2026-05-13 (revision 003) and 2026-06-03 the Mac dev environment was
    restructured significantly:

      * The dedicated ``postgres16`` Docker container was removed. Its data volume
        (``postgres16_postgres16_data``) still exists but is orphaned / abandoned.
      * ``cmc_data_platform`` now lives inside the ``rd_pg`` container (host port
        5432), alongside cmc_rd / cmc_analytics / cmc_gmp / etc.
      * The database scope was intentionally reduced: the ``meta`` and
        ``raw_qc_lims`` schemas were deliberately split out / retired. Going
        forward ``cmc_data_platform`` owns only ``material_mgmt`` and
        ``cost_accounting``.

    When this repo reconnected to the rd_pg copy it had NO ``alembic_version``
    table at all — Alembic had never tracked it. This revision re-establishes the
    baseline against the new reality.

    The authoritative full structure as of this revision is captured in
    ``assets/004/baseline_schema_2026-06-03.sql`` (pg_dump --schema-only). That
    file — not the historical 001->003 chain — is the disaster-recovery source of
    truth, because the 001->003 chain only ever patched a pre-existing,
    unversioned schema and could never build from an empty database.

    The already-current rd_pg database is brought under Alembic via
    ``alembic stamp head`` and never executes the code below. The DROP statements
    here exist only so that a hypothetical replay of the migration chain converges
    on the same reduced scope; they are guarded with IF EXISTS and are no-ops on
    the current database.
"""
from __future__ import annotations

from alembic import op


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # meta / raw_qc_lims were intentionally split out of cmc_data_platform.
    # IF EXISTS => harmless no-op on the live rd_pg database (already gone).
    op.execute("DROP SCHEMA IF EXISTS meta CASCADE")
    op.execute("DROP SCHEMA IF EXISTS raw_qc_lims CASCADE")


def downgrade() -> None:
    # Irreversible: the meta / raw_qc_lims schemas were retired by design and
    # their definitions are not retained here. To resurrect the pre-004 scope,
    # restore from a backup or from the 003-era assets, then `alembic stamp 003`.
    raise NotImplementedError(
        "Downgrade from 004 is not supported: meta / raw_qc_lims were "
        "intentionally retired and are not reconstructable from this migration."
    )
