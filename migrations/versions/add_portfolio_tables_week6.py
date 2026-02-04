"""Add portfolio_results, symbol_results, and trade_ledger tables

Revision ID: add_portfolio_tables_week6
Revises: cc616f59a219
Create Date: 2026-02-03

Week 6 migration: Adds database tables for portfolio backtesting support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_portfolio_tables_week6'
down_revision: Union[str, None] = 'cc616f59a219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'portfolio_results',
        sa.Column('batch_id', sa.String(length=64), nullable=False),
        sa.Column('symbols', sa.JSON(), nullable=False),
        sa.Column('strategy', sa.String(length=64), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('start_date', sa.String(length=10), nullable=False),
        sa.Column('end_date', sa.String(length=10), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('symbols_requested', sa.Integer(), nullable=True),
        sa.Column('symbols_completed', sa.Integer(), nullable=True),
        sa.Column('symbols_failed', sa.Integer(), nullable=True),
        sa.Column('failed_symbols', sa.JSON(), nullable=True),
        sa.Column('symbol_count', sa.Integer(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('average_sharpe', sa.Float(), nullable=True),
        sa.Column('average_return', sa.Float(), nullable=True),
        sa.Column('average_max_drawdown', sa.Float(), nullable=True),
        sa.Column('best_symbol', sa.String(length=16), nullable=True),
        sa.Column('worst_symbol', sa.String(length=16), nullable=True),
        sa.Column('runtime_seconds', sa.Float(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('batch_id')
    )
    op.create_index('ix_portfolio_results_batch_id', 'portfolio_results', ['batch_id'], unique=False)
    op.create_index('ix_portfolio_results_status', 'portfolio_results', ['status'], unique=False)
    op.create_index('ix_portfolio_results_created_at', 'portfolio_results', ['created_at'], unique=False)

    op.create_table(
        'symbol_results',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('batch_id', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('job_id', sa.String(length=64), nullable=True),
        sa.Column('sharpe', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('total_transaction_costs', sa.Float(), nullable=True),
        sa.Column('runtime_seconds', sa.Float(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['batch_id'], ['portfolio_results.batch_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_symbol_results_id', 'symbol_results', ['id'], unique=False)
    op.create_index('ix_symbol_results_batch_id', 'symbol_results', ['batch_id'], unique=False)
    op.create_index('ix_symbol_results_symbol', 'symbol_results', ['symbol'], unique=False)

    op.create_table(
        'trade_ledger',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('batch_id', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('entry_date', sa.DateTime(), nullable=True),
        sa.Column('exit_date', sa.DateTime(), nullable=True),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('shares', sa.Integer(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('pnl_pct', sa.Float(), nullable=True),
        sa.Column('strategy', sa.String(length=64), nullable=True),
        sa.Column('transaction_costs', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['batch_id'], ['portfolio_results.batch_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trade_ledger_id', 'trade_ledger', ['id'], unique=False)
    op.create_index('ix_trade_ledger_batch_id', 'trade_ledger', ['batch_id'], unique=False)
    op.create_index('ix_trade_ledger_symbol', 'trade_ledger', ['symbol'], unique=False)
    op.create_index('ix_trade_ledger_entry_date', 'trade_ledger', ['entry_date'], unique=False)
    op.create_index('ix_trade_ledger_strategy', 'trade_ledger', ['strategy'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_trade_ledger_strategy', table_name='trade_ledger')
    op.drop_index('ix_trade_ledger_entry_date', table_name='trade_ledger')
    op.drop_index('ix_trade_ledger_symbol', table_name='trade_ledger')
    op.drop_index('ix_trade_ledger_batch_id', table_name='trade_ledger')
    op.drop_index('ix_trade_ledger_id', table_name='trade_ledger')
    op.drop_table('trade_ledger')

    op.drop_index('ix_symbol_results_symbol', table_name='symbol_results')
    op.drop_index('ix_symbol_results_batch_id', table_name='symbol_results')
    op.drop_index('ix_symbol_results_id', table_name='symbol_results')
    op.drop_table('symbol_results')

    op.drop_index('ix_portfolio_results_created_at', table_name='portfolio_results')
    op.drop_index('ix_portfolio_results_status', table_name='portfolio_results')
    op.drop_index('ix_portfolio_results_batch_id', table_name='portfolio_results')
    op.drop_table('portfolio_results')
