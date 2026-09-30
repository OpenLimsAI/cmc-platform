"""Add the LabVantage ParamList bridge index used by QC staging builds.

Revision ID: gmp_qc_stg_link_idx_20260929
Revises: gmp_qc_spec_raw_20260929
"""

from alembic import op

revision = "gmp_qc_stg_link_idx_20260929"
down_revision = "gmp_qc_spec_raw_20260929"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_sdiworkitemitem_paramlist_link
          ON raw_gmp_lims_labvantage.sdiworkitemitem
             (sdcid, keyid1, keyid2, keyid3,
              itemsdcid, itemkeyid1, itemkeyid2, itemkeyid3, iteminstance)
          INCLUDE (workitemid, workiteminstance);

        COMMENT ON INDEX raw_gmp_lims_labvantage.ix_sdiworkitemitem_paramlist_link IS
          'Supports LabVantage ParamList result to workitem bridge for QC staging rebuilds';
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX raw_gmp_lims_labvantage.ix_sdiworkitemitem_paramlist_link"
    )
