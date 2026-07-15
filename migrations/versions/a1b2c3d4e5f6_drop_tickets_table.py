"""Drop tickets table

Recent Tickets is now served live from Jira (the single source of truth), so
created tickets are no longer persisted locally. This removes the now-unused
tickets table.

Revision ID: a1b2c3d4e5f6
Revises: 192c4ee5d9c2
Create Date: 2026-07-14 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '192c4ee5d9c2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tickets_user_id'))
        batch_op.drop_index(batch_op.f('ix_tickets_project_key'))

    op.drop_table('tickets')


def downgrade():
    op.create_table('tickets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('jira_key', sa.String(length=50), nullable=False),
    sa.Column('jira_id', sa.String(length=50), nullable=False),
    sa.Column('project_key', sa.String(length=20), nullable=False),
    sa.Column('summary', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tickets_project_key'), ['project_key'], unique=False)
        batch_op.create_index(batch_op.f('ix_tickets_user_id'), ['user_id'], unique=False)
