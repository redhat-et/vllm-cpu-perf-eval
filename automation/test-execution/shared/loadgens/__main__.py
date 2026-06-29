"""
Entry point for running load generator abstraction as a module.

Usage:
    python3 -m shared.loadgens <command> [args...]
"""

from .cli import main

if __name__ == '__main__':
    main()
