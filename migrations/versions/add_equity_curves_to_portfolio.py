"""Add equity_curve columns to portfolio and symbol results

Revision ID: add_equity_curves_to_portfolio
Revises: add_portfolio_tables_week6
Create Date: 2026-02-15

Adds equity_curve (JSON) to symbol_results and
portfolio_equity_curve (JSON) to portfolio_results for
per-symbol and aggregated equity curve storage.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_equity_curves_to_portfolio'
down_revision: Union[str, None] = 'add_portfolio_tables_week6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('symbol_results', sa.Column('equity_curve', sa.JSON(), nullable=True))
    op.add_column('portfolio_results', sa.Column('portfolio_equity_curve', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('portfolio_results', 'portfolio_equity_curve')
    op.drop_column('symbol_results', 'equity_curve')
