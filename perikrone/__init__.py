"""Perikrone — a read-only security-posture auditor for small practices.

Points at whatever a practice runs, flags the real security gaps, and writes a
plain-English report mapped to the HIPAA controls each gap affects.

Perikrone — closest-point security.
"""

from .engine import AssessmentResult, assess
from .report import render_markdown

__version__ = "0.1.0"

__all__ = ["assess", "AssessmentResult", "render_markdown", "__version__"]
