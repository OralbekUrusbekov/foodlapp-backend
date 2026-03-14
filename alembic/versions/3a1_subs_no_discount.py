"""drop discount_percentage from subscriptions

Revision ID: 3a1_subs_no_discount
Revises: 2a3f_subs_branch_null
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a1_subs_no_discount"
down_revision = "2a3f_subs_branch_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Колонка больше не используется в модели Subscription
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("discount_percentage")


def downgrade() -> None:
    # Восстанавливаем с тем же типом, что и раньше
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("discount_percentage", sa.Float(), nullable=True, server_default="0.0"))

