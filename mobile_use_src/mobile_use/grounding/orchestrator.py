"""
Grounding orchestration loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2

from .codex_cli_adapter import CodexCliAdapter, CodexSession
from .prompts import build_evaluator_prompt, build_operator_prompt
from .renderer import render_overlay
from .run_store import RunStore
from .schemas import (
    final_schema,
    evaluator_schema,
    normalize_evaluator_output,
    normalize_operator_output,
    operator_schema,
    write_schema,
)
from .types import GroundingResult, TurnRecord

DEFAULT_MODEL = "gpt-5.4-mini"


@dataclass
class GroundingConfig:
    model: str = DEFAULT_MODEL
    max_rounds: int = 6
    out_dir: Optional[Path] = None
    workdir: Optional[Path] = None
    timeout_sec: int = 900
    reasoning_effort: Optional[str] = None


def solve(image_path: str, instruction: str, config: Optional[GroundingConfig] = None) -> dict:
    config = config or GroundingConfig()
    image = Path(image_path).resolve()
    if not image.exists():
        raise FileNotFoundError("Input image not found: %s" % image)

    screen_size = _get_image_size(image)
    workdir = (config.workdir or Path.cwd()).resolve()
    store = RunStore.create(
        image_path=image,
        instruction=instruction,
        out_dir=config.out_dir.resolve() if config.out_dir else None,
        project_root=workdir,
    )

    operator_schema_path = store.run_dir / "operator.schema.json"
    evaluator_schema_path = store.run_dir / "evaluator.schema.json"
    final_schema_path = store.run_dir / "final.schema.json"
    write_schema(operator_schema_path, operator_schema())
    write_schema(evaluator_schema_path, evaluator_schema())
    write_schema(final_schema_path, final_schema())

    adapter = CodexCliAdapter(
        model=config.model,
        workdir=workdir,
        timeout_sec=config.timeout_sec,
        reasoning_effort=config.reasoning_effort,
    )
    operator_session = CodexSession(role="operator")
    evaluator_session = CodexSession(role="evaluator")

    latest_feedback = None
    latest_action = None
    latest_overlay = None
    last_evaluator_result = None

    for turn in range(1, config.max_rounds + 1):
        operator_prompt = build_operator_prompt(
            instruction=instruction,
            round_index=turn,
            feedback=latest_feedback.to_dict() if latest_feedback else None,
            overlay_description=latest_overlay.description if latest_overlay else None,
        )
        operator_images = [store.input_image]
        if latest_overlay is not None:
            operator_images.append(latest_overlay.path)
        operator_session, operator_raw, action = adapter.invoke_json(
            session=operator_session,
            prompt=operator_prompt,
            image_paths=operator_images,
            output_path=store.raw_message_path("operator", turn),
            validator=lambda payload, size=screen_size: normalize_operator_output(payload, size),
        )
        if operator_session.session_id:
            store.persist_session_id("operator", operator_session.session_id)
        store.persist_operator_turn(turn, action, operator_raw)

        overlay = render_overlay(
            image_path=store.input_image,
            action=action,
            output_path=store.overlay_path_for_turn(turn),
        )
        store.persist_overlay(turn, overlay)

        evaluator_prompt = build_evaluator_prompt(
            instruction=instruction,
            operator_output=action.to_dict(),
            overlay_description=overlay.description,
            round_index=turn,
        )
        evaluator_session, evaluator_raw, evaluator_result = adapter.invoke_json(
            session=evaluator_session,
            prompt=evaluator_prompt,
            image_paths=[store.input_image, overlay.path],
            output_path=store.raw_message_path("evaluator", turn),
            validator=lambda payload, action_type=action.action_type: normalize_evaluator_output(
                payload,
                action_type,
            ),
        )
        if evaluator_session.session_id:
            store.persist_session_id("evaluator", evaluator_session.session_id)
        store.persist_evaluator_turn(turn, evaluator_result, evaluator_raw)

        record = TurnRecord(turn=turn, operator=action, evaluator=evaluator_result, overlay=overlay)
        store.persist_trace(record)

        latest_feedback = evaluator_result
        latest_action = action
        latest_overlay = overlay
        last_evaluator_result = evaluator_result

        if evaluator_result.verdict == "accept":
            result = GroundingResult(
                status="accepted",
                rounds_used=turn,
                instruction=instruction,
                action=action,
                overlay_path=overlay.path,
                visual_description=overlay.description,
                evaluator_summary={
                    "score": evaluator_result.score,
                    "reason": evaluator_result.reason,
                },
                run_dir=store.run_dir,
            )
            store.persist_final(result)
            return result.to_dict()

    result = GroundingResult(
        status="unresolved",
        rounds_used=config.max_rounds,
        instruction=instruction,
        action=None,
        overlay_path=latest_overlay.path if latest_overlay else None,
        visual_description=latest_overlay.description if latest_overlay else None,
        evaluator_summary=None,
        best_candidate=latest_action,
        last_evaluator_feedback=last_evaluator_result,
        run_dir=store.run_dir,
    )
    store.persist_final(result)
    return result.to_dict()


def _get_image_size(image_path: Path) -> Tuple[int, int]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError("Failed to load image: %s" % image_path)
    height, width = image.shape[:2]
    return width, height
