"""
Run artifact storage helpers.
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .types import EvaluatorResult, GroundingResult, OperatorAction, OverlayArtifact, TurnRecord


def _default_run_dir(project_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return project_root / "runs" / "grounding" / f"{timestamp}-{short_id}"


@dataclass
class RunStore:
    run_dir: Path
    input_image: Path
    trace_path: Path
    operator_history_path: Path
    evaluator_history_path: Path
    operator_last_path: Path
    evaluator_last_path: Path

    @classmethod
    def create(
        cls,
        image_path: Path,
        instruction: str,
        out_dir: Optional[Path] = None,
        project_root: Optional[Path] = None,
    ) -> "RunStore":
        root = out_dir or _default_run_dir(project_root or Path.cwd())
        root.mkdir(parents=True, exist_ok=True)
        _cleanup_previous_artifacts(root)
        input_image = root / "input.png"
        shutil.copy2(image_path, input_image)
        store = cls(
            run_dir=root,
            input_image=input_image,
            trace_path=root / "trace.jsonl",
            operator_history_path=root / "operator.history.jsonl",
            evaluator_history_path=root / "evaluator.history.jsonl",
            operator_last_path=root / "operator.last.json",
            evaluator_last_path=root / "evaluator.last.json",
        )
        store.write_json(
            root / "input.meta.json",
            {
                "instruction": instruction,
                "source_image": str(Path(image_path).resolve()),
                "copied_input_image": str(input_image),
            },
        )
        return store

    def overlay_path_for_turn(self, turn: int) -> Path:
        return self.run_dir / f"overlay.turn_{turn}.png"

    def overlay_meta_path_for_turn(self, turn: int) -> Path:
        return self.run_dir / f"overlay.turn_{turn}.json"

    def raw_message_path(self, role: str, turn: int) -> Path:
        return self.run_dir / f"{role}.raw.turn_{turn}.txt"

    def parsed_message_path(self, role: str, turn: int) -> Path:
        return self.run_dir / f"{role}.turn_{turn}.json"

    def final_path(self) -> Path:
        return self.run_dir / "final.json"

    def session_id_path(self, role: str) -> Path:
        return self.run_dir / f"{role}.session_id.txt"

    def write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def append_jsonl(self, path: Path, payload: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def persist_operator_turn(self, turn: int, action: OperatorAction, raw_text: str) -> None:
        payload = action.to_dict()
        self.write_text(self.raw_message_path("operator", turn), raw_text)
        self.write_json(self.parsed_message_path("operator", turn), payload)
        self.write_json(self.operator_last_path, payload)
        self.append_jsonl(self.operator_history_path, {"turn": turn, **payload})

    def persist_evaluator_turn(self, turn: int, result: EvaluatorResult, raw_text: str) -> None:
        payload = result.to_dict()
        self.write_text(self.raw_message_path("evaluator", turn), raw_text)
        self.write_json(self.parsed_message_path("evaluator", turn), payload)
        self.write_json(self.evaluator_last_path, payload)
        self.append_jsonl(self.evaluator_history_path, {"turn": turn, **payload})

    def persist_overlay(self, turn: int, overlay: OverlayArtifact) -> None:
        self.write_json(
            self.overlay_meta_path_for_turn(turn),
            {
                "turn": turn,
                "path": str(overlay.path),
                "description": overlay.description,
                "image_size": list(overlay.image_size),
            },
        )

    def persist_session_id(self, role: str, session_id: str) -> None:
        self.write_text(self.session_id_path(role), session_id + "\n")

    def persist_trace(self, record: TurnRecord) -> None:
        self.append_jsonl(self.trace_path, record.to_dict())

    def persist_final(self, result: GroundingResult) -> None:
        self.write_json(self.final_path(), result.to_dict())


def _cleanup_previous_artifacts(run_dir: Path) -> None:
    patterns = [
        "trace.jsonl",
        "final.json",
        "*.schema.json",
        "operator.history.jsonl",
        "evaluator.history.jsonl",
        "operator.last.json",
        "evaluator.last.json",
        "*.session_id.txt",
        "operator.turn_*.json",
        "evaluator.turn_*.json",
        "operator.raw.turn_*.txt",
        "evaluator.raw.turn_*.txt",
        "overlay.turn_*.png",
        "overlay.turn_*.json",
    ]
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.is_file():
                path.unlink()
