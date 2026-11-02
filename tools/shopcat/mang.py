"""mang -- moved to tools/client/mang.py (refactor-candidates E7, 2026-11-02). This shim keeps `import mang` and
`from mang import ...` working for the scripts in this directory (shopcat.py, newchar.py): it loads the real module
under the same name, so there is only one copy of MangClient and ClientExited."""
import importlib.util
import os
import sys

_spec = importlib.util.spec_from_file_location(
    "mang", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client", "mang.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["mang"] = _mod
_spec.loader.exec_module(_mod)
