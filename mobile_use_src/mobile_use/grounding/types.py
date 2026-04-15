"""
Shared datatypes for the grounding workflow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

ActionType = Literal["tap", "long_press", "swipe"]
Verdict = Literal["accept", "reject"]
Status = Literal["accepted", "unresolved"]


@dataclass
class OperatorAction:
    action_type: ActionType
    target_desc: str
    screen_size: Tuple[int, int]
    point_px: Optional[Tuple[int, int]] = None
    point_999: Optional[Tuple[int, int]] = None
    start_px: Optional[Tuple[int, int]] = None
    end_px: Optional[Tuple[int, int]] = None
    start_999: Optional[Tuple[int, int]] = None
    end_999: Optional[Tuple[int, int]] = None
    duration_ms: Optional[int] = None
    confidence: float = 0.0
    reason: str = ""
    python_call: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluatorResult:
    verdict: Verdict
    score: float
    reason: str
    issues: List[str]
    repair_hint: str
    expected_action_type: ActionType
    reject_labels: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OverlayArtifact:
    path: Path
    description: str
    image_size: Tuple[int, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "description": self.description,
            "image_size": list(self.image_size),
        }


@dataclass
class TurnRecord:
    turn: int
    operator: OperatorAction
    evaluator: EvaluatorResult
    overlay: OverlayArtifact

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "operator": self.operator.to_dict(),
            "evaluator": self.evaluator.to_dict(),
            "overlay": self.overlay.to_dict(),
        }


@dataclass
class GroundingResult:
    status: Status
    rounds_used: int
    instruction: str
    action: Optional[OperatorAction]
    overlay_path: Optional[Path]
    visual_description: Optional[str]
    evaluator_summary: Optional[Dict[str, Any]]
    best_candidate: Optional[OperatorAction] = None
    last_evaluator_feedback: Optional[EvaluatorResult] = None
    run_dir: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "status": self.status,
            "rounds_used": self.rounds_used,
            "instruction": self.instruction,
        }
        if self.action:
            data["action"] = self.action.to_dict()
        if self.overlay_path:
            data["overlay_path"] = str(self.overlay_path)
        if self.visual_description:
            data["visual_description"] = self.visual_description
        if self.evaluator_summary is not None:
            data["evaluator_summary"] = self.evaluator_summary
        if self.best_candidate:
            data["best_candidate"] = self.best_candidate.to_dict()
        if self.last_evaluator_feedback:
            data["last_evaluator_feedback"] = self.last_evaluator_feedback.to_dict()
        if self.run_dir:
            data["run_dir"] = str(self.run_dir)
        return data
