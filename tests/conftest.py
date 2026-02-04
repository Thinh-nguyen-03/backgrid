"""Pytest configuration - sets up test environment before any imports."""

import os

os.environ["DATABASE_URL"] = "sqlite:///test_backgrid.db"
