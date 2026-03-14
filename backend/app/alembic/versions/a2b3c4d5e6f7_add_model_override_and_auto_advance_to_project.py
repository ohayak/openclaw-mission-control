"""add model_override and auto_advance to project

Revision ID: a2b3c4d5e6f7
Revises: 1a31ce608336
Create Date: 2026-03-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = '1a31ce608336'
branch_labels = None
depends_on = None


def upgrade():
    # Add model_override: nullable string for AI model override (e.g. "claude-opus-4-5")
    op.add_column(
        'project',
        sa.Column('model_override', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    )
    # Add auto_advance: boolean with default False
    op.add_column(
        'project',
        sa.Column('auto_advance', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade():
    op.drop_column('project', 'auto_advance')
    op.drop_column('project', 'model_override')
