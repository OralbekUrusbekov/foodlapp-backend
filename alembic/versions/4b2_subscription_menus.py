"""Add subscription_menus table

Revision ID: 4b2_subscription_menus
Revises: 3a1_subs_no_discount
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa


revision = "4b2_subscription_menus"
down_revision = "019286e6c789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_menus",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "food_id", name="uq_subscription_food"),
    )
    op.create_index(op.f("ix_subscription_menus_id"), "subscription_menus", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_subscription_menus_id"), table_name="subscription_menus")
    op.drop_table("subscription_menus")
