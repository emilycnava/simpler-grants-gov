"""add topportunity table for transfer

Revision ID: b1eb1bd4a647
Revises: 83964e6715a1
Create Date: 2024-01-29 14:07:42.665723

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1eb1bd4a647"
down_revision = "83964e6715a1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "transfer_topportunity",
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("oppnumber", sa.VARCHAR(length=160), nullable=True),
        sa.Column("opptitle", sa.VARCHAR(length=1020), nullable=True),
        sa.Column("owningagency", sa.VARCHAR(length=1020), nullable=True),
        sa.Column("oppcategory", sa.VARCHAR(length=4), nullable=True),
        sa.Column("category_explanation", sa.VARCHAR(length=1020), nullable=True),
        sa.Column("is_draft", sa.VARCHAR(length=4), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=True),
        sa.Column("modified_comments", sa.VARCHAR(length=4000), nullable=True),
        sa.Column("publisheruid", sa.VARCHAR(length=1020), nullable=True),
        sa.Column("publisher_profile_id", sa.Integer(), nullable=True),
        sa.Column("last_upd_id", sa.VARCHAR(length=200), nullable=True),
        sa.Column("last_upd_date", sa.Date(), nullable=True),
        sa.Column("creator_id", sa.VARCHAR(length=200), nullable=True),
        sa.Column("created_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("opportunity_id", name=op.f("transfer_topportunity_pkey")),
    )
    op.create_index(
        op.f("transfer_topportunity_is_draft_idx"),
        "transfer_topportunity",
        ["is_draft"],
        unique=False,
    )
    op.create_index(
        op.f("transfer_topportunity_oppcategory_idx"),
        "transfer_topportunity",
        ["oppcategory"],
        unique=False,
    )
    op.create_index(
        op.f("transfer_topportunity_opptitle_idx"),
        "transfer_topportunity",
        ["opptitle"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("transfer_topportunity_opptitle_idx"), table_name="transfer_topportunity")
    op.drop_index(op.f("transfer_topportunity_oppcategory_idx"), table_name="transfer_topportunity")
    op.drop_index(op.f("transfer_topportunity_is_draft_idx"), table_name="transfer_topportunity")
    op.drop_table("transfer_topportunity")
    # ### end Alembic commands ###