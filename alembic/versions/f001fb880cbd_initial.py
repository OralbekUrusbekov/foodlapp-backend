"""initial

Revision ID: f001fb880cbd
Revises: 
Create Date: 2026-02-12 07:11:44.492238

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f001fb880cbd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### 1. Users кестесі ###
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('phone', sa.String(), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'canteen_admin', 'cashier', 'client', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('bio', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('branch_id', sa.Integer(), nullable=True)
    )

    # ### 2. Restaurants кестесі ###
    op.create_table(
        'restaurants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=True, unique=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'])
    )

    # ### 3. Branches кестесі ###
    op.create_table(
        'branches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('opening_time', sa.Time(), nullable=True),
        sa.Column('closing_time', sa.Time(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=True, unique=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.ForeignKeyConstraint(['staff_id'], ['users.id'])
    )

    # ### 4. Foods кестесі ###
    op.create_table(
        'foods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('calories', sa.Integer(), nullable=True),
        sa.Column('ingredients', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'])
    )

    # ### 5. Orders кестесі ###
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'accepted', 'completed', 'cancelled', name='orderstatus'), nullable=False),
        sa.Column('qr_code', sa.String(), nullable=True, unique=True),
        sa.Column('qr_used', sa.Boolean(), nullable=True),
        sa.Column('qr_expire_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'])
    )

    # ### 6. Subscriptions кестесі ###
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('meal_limit', sa.Integer(), nullable=True),
        sa.Column('discount_percentage', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'])
    )

    # ### 7. OrderItems кестесі ###
    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('food_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id'])
    )

    # ### 8. UserSubscriptions кестесі ###
    op.create_table(
        'user_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('remaining_meals', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'])
    )


def downgrade() -> None:
    op.drop_table('user_subscriptions')
    op.drop_table('order_items')
    op.drop_table('subscriptions')
    op.drop_table('orders')
    op.drop_table('foods')
    op.drop_table('branches')
    op.drop_table('restaurants')
    op.drop_table('users')
