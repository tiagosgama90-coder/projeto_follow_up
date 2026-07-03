#!/usr/bin/env python3
"""Soretrac Follow-up Comercial — Entry Point"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui.app import run_app

if __name__ == "__main__":
    run_app()
