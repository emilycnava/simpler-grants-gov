"""legacy null agency

Revision ID: 558ad9563e9a
Revises: 56448a3ecb8f
Create Date: 2024-10-17 13:54:32.420425

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "558ad9563e9a"
down_revision = "56448a3ecb8f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("agency", "ldap_group", existing_type=sa.TEXT(), nullable=True, schema="api")
    op.alter_column("agency", "description", existing_type=sa.TEXT(), nullable=True, schema="api")
    op.alter_column("agency", "label", existing_type=sa.TEXT(), nullable=True, schema="api")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("agency", "label", existing_type=sa.TEXT(), nullable=False, schema="api")
    op.alter_column("agency", "description", existing_type=sa.TEXT(), nullable=False, schema="api")
    op.alter_column("agency", "ldap_group", existing_type=sa.TEXT(), nullable=False, schema="api")
    # ### end Alembic commands ###
