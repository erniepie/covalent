# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

"""Remove asset meta table

Revision ID: 305e512a5a08
Revises: 075d71eceeba
Create Date: 2023-03-15 11:16:43.041030

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# pragma: allowlist nextline secret
revision = "305e512a5a08"
# pragma: allowlist nextline secret
down_revision = "075d71eceeba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("asset_meta")
    with op.batch_alter_table("electron_dependency", schema=None) as batch_op:
        batch_op.create_foreign_key("electron_link", "electrons", ["electron_id"], ["id"])

    with op.batch_alter_table("lattices", schema=None) as batch_op:
        batch_op.drop_column("transport_graph_filename")

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("lattices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("transport_graph_filename", sa.TEXT(), nullable=True))

    with op.batch_alter_table("electron_dependency", schema=None) as batch_op:
        batch_op.drop_constraint("electron_link", type_="foreignkey")

    op.create_table(
        "asset_meta",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("dispatch_id", sa.INTEGER(), nullable=False),
        sa.Column("asset_id", sa.TEXT(), nullable=False),
        sa.Column("digest_alg", sa.TEXT(), nullable=True),
        sa.Column("digest_hex", sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(
            ["dispatch_id"],
            ["lattices.dispatch_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###
