"""Compatibility package for running project CLIs as direct script paths.

When Python executes ``python scripts/tool.py``, it places the outer ``scripts``
directory on ``sys.path``. This package extends its search path to that outer
directory so imports such as ``scripts.contract_common`` remain resolvable.
Module execution (``python -m scripts.tool``) continues to use the normal
package at the repository root.
"""
from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[1]))
