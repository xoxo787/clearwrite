"""ClearWrite: readability-oriented editing with explicit uncertainty."""
__version__ = "0.3.0"
from .core import analyze, apply_plan, make_plan, prepare, verify
__all__ = ["analyze", "apply_plan", "make_plan", "prepare", "verify"]
