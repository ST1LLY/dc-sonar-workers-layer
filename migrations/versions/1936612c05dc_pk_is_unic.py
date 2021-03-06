"""pk is unic

Revision ID: 1936612c05dc
Revises: afeaa5fcdb4d
Create Date: 2022-07-11 19:26:31.286659

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1936612c05dc'
down_revision = 'afeaa5fcdb4d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'ntlm_brute_session', ['domain_pk'])
    op.create_unique_constraint(None, 'ntlm_dump_session', ['domain_pk'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'ntlm_dump_session', type_='unique')
    op.drop_constraint(None, 'ntlm_brute_session', type_='unique')
    # ### end Alembic commands ###
