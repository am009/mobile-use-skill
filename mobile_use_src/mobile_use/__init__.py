"""
Mobile Use Skills
基于AppAgent封装的Android设备控制技能模块
"""

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .screen import get_screenshot
from .controller import (
    tap,
    text,
    long_press,
    swipe,
    back, home, enter, keyevent,
    get_device_size,
)
from .grounding import GroundingConfig, solve as solve_grounded_action


def interact_with_screen(
    image: Union[str, Path],
    instruction: str,
    *,
    config: Optional[GroundingConfig] = None,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    max_rounds: Optional[int] = None,
    out: Optional[Union[str, Path]] = None,
    workdir: Optional[Union[str, Path]] = None,
    timeout_sec: Optional[int] = None,
) -> Dict[str, Any]:
    """Resolve a screenshot + natural-language instruction into a device action and execute it.

    This is the Python equivalent of the grounding CLI, with one extra step:
    after the grounding workflow returns an accepted action, this helper
    immediately dispatches the action through the controller layer.

    Args:
        image: Path to the screenshot used for grounding.
        instruction: Natural-language instruction such as ``"点击微信"``.
        config: Optional ``GroundingConfig`` to use as the base configuration.
        model: Optional model override for the grounding agents.
        reasoning_effort: Optional reasoning effort override passed to Codex.
        max_rounds: Maximum operator/evaluator rounds.
        out: Optional output directory for grounding run artifacts.
        workdir: Working directory used when invoking the Codex CLI.
        timeout_sec: Per-agent timeout in seconds.

    Returns:
        A dict containing the normal grounding result plus an ``execution``
        object. When grounding is accepted, ``execution`` reports that the
        controller call was performed and includes the controller result.
        When grounding is unresolved, ``execution.performed`` is ``False``.

    Raises:
        FileNotFoundError: If ``image`` does not exist.
        RuntimeError: If the grounding pipeline or underlying controller call fails.
        ValueError: If the accepted action is missing required runtime fields.
    """
    grounding_config = _build_grounding_config(
        config=config,
        model=model,
        reasoning_effort=reasoning_effort,
        max_rounds=max_rounds,
        out=out,
        workdir=workdir,
        timeout_sec=timeout_sec,
    )
    result = solve_grounded_action(
        image_path=str(Path(image).resolve()),
        instruction=instruction,
        config=grounding_config,
    )

    action = result.get("action")
    if result.get("status") != "accepted" or not isinstance(action, dict):
        result["execution"] = {
            "performed": False,
            "reason": "Grounding did not return an accepted action.",
        }
        return result

    result["execution"] = _execute_action(action)
    return result


def ground_and_execute(
    image: Union[str, Path],
    instruction: str,
    *,
    config: Optional[GroundingConfig] = None,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    max_rounds: Optional[int] = None,
    out: Optional[Union[str, Path]] = None,
    workdir: Optional[Union[str, Path]] = None,
    timeout_sec: Optional[int] = None,
) -> Dict[str, Any]:
    """Backward-compatible alias for :func:`interact_with_screen`."""
    return interact_with_screen(
        image=image,
        instruction=instruction,
        config=config,
        model=model,
        reasoning_effort=reasoning_effort,
        max_rounds=max_rounds,
        out=out,
        workdir=workdir,
        timeout_sec=timeout_sec,
    )


def _build_grounding_config(
    *,
    config: Optional[GroundingConfig],
    model: Optional[str],
    reasoning_effort: Optional[str],
    max_rounds: Optional[int],
    out: Optional[Union[str, Path]],
    workdir: Optional[Union[str, Path]],
    timeout_sec: Optional[int],
) -> GroundingConfig:
    grounding_config = replace(config) if config is not None else GroundingConfig()
    if model is not None:
        grounding_config.model = model
    if reasoning_effort is not None:
        grounding_config.reasoning_effort = reasoning_effort
    if max_rounds is not None:
        grounding_config.max_rounds = max_rounds
    if out is not None:
        grounding_config.out_dir = Path(out).resolve()
    if workdir is not None:
        grounding_config.workdir = Path(workdir).resolve()
    if timeout_sec is not None:
        grounding_config.timeout_sec = timeout_sec
    return grounding_config


def _execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("action_type")

    if action_type == "tap":
        point_px = _require_point(action.get("point_px"), "point_px")
        controller_result = tap(point_px[0], point_px[1])
    elif action_type == "long_press":
        point_px = _require_point(action.get("point_px"), "point_px")
        duration_ms = _require_positive_int(action.get("duration_ms"), "duration_ms")
        controller_result = long_press(point_px[0], point_px[1], duration=duration_ms)
    elif action_type == "swipe":
        start_px = _require_point(action.get("start_px"), "start_px")
        end_px = _require_point(action.get("end_px"), "end_px")
        duration_ms = _require_positive_int(action.get("duration_ms"), "duration_ms")
        controller_result = swipe(
            start_px[0],
            start_px[1],
            end_px[0],
            end_px[1],
            duration=duration_ms,
        )
    else:
        raise ValueError(f"Unsupported action_type: {action_type}")

    return {
        "performed": True,
        "action_type": action_type,
        "controller_result": controller_result,
    }


def _require_point(value: Any, field_name: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field_name} must be a [x, y] array")
    x, y = value
    if not isinstance(x, int) or not isinstance(y, int):
        raise ValueError(f"{field_name} must contain integers")
    return x, y


def _require_positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


__all__ = [
    # 屏幕
    "get_screenshot",
    # 控制
    "tap",
    "text",
    "long_press",
    "swipe",
    "back", "home", "enter", "keyevent",
    "get_device_size",
    "GroundingConfig",
    "solve_grounded_action",
    "interact_with_screen",
    "ground_and_execute",
]
