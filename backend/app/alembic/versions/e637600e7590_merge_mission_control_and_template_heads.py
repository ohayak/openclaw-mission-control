"""merge mission control and template heads

Revision ID: e637600e7590
Revises: a1b2c3d4e5f6, fe56fa70289e
Create Date: 2026-03-14 00:57:49.565818

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'e637600e7590'
down_revision = ('a1b2c3d4e5f6', 'fe56fa70289e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
