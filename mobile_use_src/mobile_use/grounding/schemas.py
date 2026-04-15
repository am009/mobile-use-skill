"""
JSON-schema definitions and lightweight runtime validation helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .types import EvaluatorResult, OperatorAction

ACTION_TYPES = ["tap", "long_press", "swipe"]
VERDICTS = ["accept", "reject"]
REJECT_LABELS = [
    "wrong_target",
    "wrong_action_type",
    "unsafe_nearby_controls",
    "gesture_path_wrong",
    "too_uncertain",
]


class SchemaValidationError(ValueError):
    """Raised when model output cannot be normalized into a valid structure."""


def operator_schema() -> Dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "grounding_operator_output",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "action_type",
            "target_desc",
            "confidence",
            "reason",
        ],
        "properties": {
            "action_type": {"type": "string", "enum": ACTION_TYPES},
            "target_desc": {"type": "string", "minLength": 1},
            "point_999": _tuple_schema(2, max_value=999),
            "start_999": _tuple_schema(2, max_value=999),
            "end_999": _tuple_schema(2, max_value=999),
            "duration_ms": {"type": ["integer", "null"], "minimum": 1},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reason": {"type": "string", "minLength": 1},
        },
        "allOf": [
            {
                "if": {"properties": {"action_type": {"const": "tap"}}},
                "then": {"required": ["point_999"]},
            },
            {
                "if": {"properties": {"action_type": {"const": "long_press"}}},
                "then": {"required": ["point_999", "duration_ms"]},
            },
            {
                "if": {"properties": {"action_type": {"const": "swipe"}}},
                "then": {
                    "required": [
                        "start_999",
                        "end_999",
                        "duration_ms",
                    ],
                },
            },
        ],
    }


def evaluator_schema() -> Dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "grounding_evaluator_output",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "verdict",
            "score",
            "reason",
            "issues",
            "repair_hint",
            "expected_action_type",
        ],
        "properties": {
            "verdict": {"type": "string", "enum": VERDICTS},
            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reason": {"type": "string", "minLength": 1},
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "repair_hint": {"type": "string"},
            "expected_action_type": {"type": "string", "enum": ACTION_TYPES},
            "reject_labels": {
                "type": "array",
                "items": {"type": "string", "enum": REJECT_LABELS},
            },
        },
    }


def final_schema() -> Dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "grounding_final_output",
        "type": "object",
        "additionalProperties": True,
        "required": ["status", "rounds_used", "instruction"],
        "properties": {
            "status": {"type": "string", "enum": ["accepted", "unresolved"]},
            "rounds_used": {"type": "integer", "minimum": 1},
            "instruction": {"type": "string", "minLength": 1},
            "action": {"type": "object"},
            "overlay_path": {"type": "string"},
            "visual_description": {"type": "string"},
            "evaluator_summary": {"type": "object"},
            "best_candidate": {"type": "object"},
            "last_evaluator_feedback": {"type": "object"},
            "run_dir": {"type": "string"},
        },
    }


def write_schema(path: Path, schema: Dict[str, Any]) -> None:
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_operator_output(payload: Dict[str, Any], image_size: Tuple[int, int]) -> OperatorAction:
    action_type = _require_enum(payload, "action_type", ACTION_TYPES)
    target_desc = _require_string(payload, "target_desc")
    width, height = _resolve_screen_size(payload.get("screen_size"), image_size)
    confidence = _clamp_float(payload.get("confidence"), field_name="confidence")
    reason = _require_string(payload, "reason")

    point_999 = _optional_norm_point(payload.get("point_999"), field_name="point_999")
    start_999 = _optional_norm_point(payload.get("start_999"), field_name="start_999")
    end_999 = _optional_norm_point(payload.get("end_999"), field_name="end_999")
    duration_ms = _optional_positive_int(payload.get("duration_ms"), field_name="duration_ms")

    if action_type == "tap":
        if point_999 is None:
            raise SchemaValidationError("tap action requires point_999")
        point_px = _denormalize_point(point_999, width, height)
        python_call = f"tap({point_px[0]}, {point_px[1]})"
        return OperatorAction(
            action_type=action_type,
            target_desc=target_desc,
            screen_size=(width, height),
            point_px=point_px,
            point_999=point_999,
            confidence=confidence,
            reason=reason,
            python_call=python_call,
        )

    if action_type == "long_press":
        if point_999 is None:
            raise SchemaValidationError("long_press action requires point_999")
        duration_ms = duration_ms or 1000
        point_px = _denormalize_point(point_999, width, height)
        python_call = f"long_press({point_px[0]}, {point_px[1]}, duration={duration_ms})"
        return OperatorAction(
            action_type=action_type,
            target_desc=target_desc,
            screen_size=(width, height),
            point_px=point_px,
            point_999=point_999,
            duration_ms=duration_ms,
            confidence=confidence,
            reason=reason,
            python_call=python_call,
        )

    if start_999 is None or end_999 is None:
        raise SchemaValidationError("swipe action requires start_999 and end_999")
    duration_ms = duration_ms or 400
    start_px = _denormalize_point(start_999, width, height)
    end_px = _denormalize_point(end_999, width, height)
    python_call = (
        f"swipe({start_px[0]}, {start_px[1]}, {end_px[0]}, {end_px[1]}, "
        f"duration={duration_ms})"
    )
    return OperatorAction(
        action_type=action_type,
        target_desc=target_desc,
        screen_size=(width, height),
        start_px=start_px,
        end_px=end_px,
        start_999=start_999,
        end_999=end_999,
        duration_ms=duration_ms,
        confidence=confidence,
        reason=reason,
        python_call=python_call,
    )


def normalize_evaluator_output(payload: Dict[str, Any], fallback_action_type: str) -> EvaluatorResult:
    verdict = _require_enum(payload, "verdict", VERDICTS)
    raw_score = payload.get("score")
    if raw_score is None:
        score = 1.0 if verdict == "accept" else 0.0
    else:
        score = _clamp_float(raw_score, field_name="score")
    issues = _normalize_string_list(payload.get("issues"))
    repair_hint = _optional_string(payload.get("repair_hint"))
    reason = _optional_string(payload.get("reason"))
    if not reason:
        reason = repair_hint or (issues[0] if issues else "")
    if not reason:
        reason = f"Evaluator returned verdict={verdict} without an explicit reason."
    expected_action_type = payload.get("expected_action_type") or fallback_action_type
    if expected_action_type not in ACTION_TYPES:
        raise SchemaValidationError("expected_action_type must be one of tap, long_press, swipe")
    reject_labels = payload.get("reject_labels")
    if reject_labels is not None:
        reject_labels = _normalize_reject_labels(reject_labels)
    return EvaluatorResult(
        verdict=verdict,
        score=score,
        reason=reason,
        issues=issues,
        repair_hint=repair_hint,
        expected_action_type=expected_action_type,
        reject_labels=reject_labels,
    )


def _tuple_schema(length: int, max_value: Optional[int] = None) -> Dict[str, Any]:
    item: Dict[str, Any] = {"type": "integer", "minimum": 0}
    if max_value is not None:
        item["maximum"] = max_value
    return {
        "type": "array",
        "items": item,
        "minItems": length,
        "maxItems": length,
    }


def _require_enum(payload: Dict[str, Any], field_name: str, allowed: Sequence[str]) -> str:
    value = payload.get(field_name)
    if value not in allowed:
        raise SchemaValidationError(f"{field_name} must be one of {', '.join(allowed)}")
    return value


def _require_string(payload: Dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SchemaValidationError("string field must be a string")
    return value.strip()


def _normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SchemaValidationError("issues must be an array of strings")
    return [item.strip() for item in value if item.strip()]


def _normalize_reject_labels(value: Any) -> List[str]:
    if not isinstance(value, list):
        raise SchemaValidationError("reject_labels must be an array")
    invalid = [item for item in value if item not in REJECT_LABELS]
    if invalid:
        raise SchemaValidationError(
            f"reject_labels contains invalid values: {', '.join(sorted(set(invalid)))}"
        )
    return value


def _optional_positive_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        raise SchemaValidationError(f"{field_name} must be a positive integer")
    return value


def _clamp_float(value: Any, field_name: str) -> float:
    if not isinstance(value, (float, int)):
        raise SchemaValidationError(f"{field_name} must be a number")
    numeric = float(value)
    if numeric < 0.0 or numeric > 1.0:
        raise SchemaValidationError(f"{field_name} must be between 0.0 and 1.0")
    return numeric


def _optional_point(
    value: Any,
    width: int,
    height: int,
    field_name: str,
) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2:
        raise SchemaValidationError(f"{field_name} must be a [x, y] array")
    x, y = value
    if not isinstance(x, int) or not isinstance(y, int):
        raise SchemaValidationError(f"{field_name} must contain integers")
    return (_clamp(x, 0, max(width - 1, 0)), _clamp(y, 0, max(height - 1, 0)))


def _optional_norm_point(value: Any, field_name: str) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    if isinstance(value, dict):
        if set(value.keys()) != {"x", "y"}:
            raise SchemaValidationError(f"{field_name} object form must contain only x and y")
        x = value["x"]
        y = value["y"]
    else:
        if not isinstance(value, list) or len(value) != 2:
            raise SchemaValidationError(f"{field_name} must be a [x, y] array")
        x, y = value
    if not isinstance(x, int) or not isinstance(y, int):
        raise SchemaValidationError(f"{field_name} must contain integers")
    return (_clamp(x, 0, 999), _clamp(y, 0, 999))


def _resolve_screen_size(value: Any, fallback: Tuple[int, int]) -> Tuple[int, int]:
    if value is None:
        return fallback
    if not isinstance(value, list) or len(value) != 2:
        raise SchemaValidationError("screen_size must be a [width, height] array")
    width, height = value
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise SchemaValidationError("screen_size must contain positive integers")
    return width, height


def _denormalize_point(point_999: Tuple[int, int], width: int, height: int) -> Tuple[int, int]:
    max_x = max(width - 1, 0)
    max_y = max(height - 1, 0)
    return (
        int(round((point_999[0] * max_x) / 999.0)),
        int(round((point_999[1] * max_y) / 999.0)),
    )


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))
