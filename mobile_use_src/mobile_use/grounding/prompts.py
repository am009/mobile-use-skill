"""
Prompt builders for the grounding workflow.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def build_operator_prompt(
    instruction: str,
    round_index: int,
    feedback: Optional[Dict[str, Any]] = None,
    overlay_description: Optional[str] = None,
) -> str:
    lines = [
        "You are operator agent.",
        "Your only task is to propose one executable mobile action that matches the screenshot and user instruction.",
        "Return JSON only. Do not use markdown fences. Do not return multiple candidates.",
        "Supported action_type values: tap, long_press, swipe.",
        "Always include confidence and reason.",
        "Do not output pixel coordinates. Use only normalized 0-999 coordinates.",
        "Represent coordinates as JSON arrays, not objects. Example: [385, 293].",
        "For tap: include point_999 as [x, y].",
        "For long_press: include point_999 as [x, y]. Do not include duration_ms; runtime fixes it to 1000ms.",
        "For swipe: include start_999 as [x, y] and end_999 as [x, y]. Do not include duration_ms; runtime fixes it to 1000ms.",
        "If evaluator feedback exists, prioritize fixing the exact issue it identified.",
        "When an overlay image is attached, treat it as the visualization of the previous proposal and use it to correct the next action.",
        f"Round: {round_index}",
        f"User instruction: {instruction}",
    ]
    if overlay_description:
        lines.extend(
            [
                "Latest overlay description:",
                overlay_description,
            ]
        )
    if feedback:
        lines.extend(
            [
                "Latest evaluator feedback JSON:",
                json.dumps(feedback, ensure_ascii=False, indent=2),
            ]
        )
    else:
        lines.append("This is the first proposal. Ground carefully against the screenshot.")
    return "\n".join(lines)


def build_evaluator_prompt(
    instruction: str,
    operator_output: Dict[str, Any],
    overlay_description: str,
    round_index: int,
) -> str:
    return "\n".join(
        [
            "You are evaluator agent.",
            "Your task is to strictly judge whether the operator's latest action truly matches the screenshot and the user instruction.",
            "Return JSON only. Do not use markdown fences.",
            "You may only use the current screenshot, the current overlay image, the user instruction, and the operator's latest JSON output.",
            "Do not infer any hidden history. Do not accept a proposal that is only approximately correct.",
            "If you reject, provide specific, actionable issues and a repair_hint.",
            f"Round: {round_index}",
            f"User instruction: {instruction}",
            f"Overlay description: {overlay_description}",
            "Operator latest JSON:",
            json.dumps(operator_output, ensure_ascii=False, indent=2),
        ]
    )
