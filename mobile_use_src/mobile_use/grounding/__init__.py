"""
Grounding workflow for turning screenshots and natural-language intent into
structured mobile actions.
"""

from .orchestrator import GroundingConfig, solve

__all__ = ["GroundingConfig", "solve"]
