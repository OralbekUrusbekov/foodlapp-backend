"""make subscription.branch_id nullable (global subscriptions)

Revision ID: 2a3f_subs_branch_null
Revises: 8119ef07c6c0
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a3f_subs_branch_null"
down_revision = "8119ef07c6c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # subscriptions.branch_id бастапқы initial migration-да NOT NULL,
    # бірақ логика бойынша абонемент GLOBAL болуы керек.
    op.alter_column(
        "subscriptions",
        "branch_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # Қайтадан NOT NULL қыламыз (ескі мінез-құлық)
    op.alter_column(
        "subscriptions",
        "branch_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

