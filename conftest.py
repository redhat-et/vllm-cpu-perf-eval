"""Root conftest.py for pytest configuration.

This file adds the project root to sys.path, allowing tests to use
absolute imports from the project root rather than requiring sys.path
manipulation in individual test files.
"""

import sys
from pathlib import Path

# Add project root to Python path for absolute imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
