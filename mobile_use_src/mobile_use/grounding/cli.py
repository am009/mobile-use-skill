"""
CLI entrypoint for the screenshot grounding workflow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .orchestrator import DEFAULT_MODEL, GroundingConfig, solve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ground a mobile screenshot and natural-language instruction into a structured action.",
    )
    parser.add_argument("--image", required=True, help="Path to the screenshot")
    parser.add_argument("--instruction", required=True, help="Natural-language mobile instruction")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Codex model name")
    parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        help="Optional Codex reasoning effort override",
    )
    parser.add_argument("--max-rounds", type=int, default=6, help="Maximum operator/evaluator rounds")
    parser.add_argument("--out", help="Output directory for run artifacts")
    parser.add_argument(
        "--workdir",
        help="Working directory used when invoking `codex exec`",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=900,
        help="Per-agent Codex CLI timeout in seconds",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = GroundingConfig(
        model=args.model,
        max_rounds=args.max_rounds,
        out_dir=Path(args.out).resolve() if args.out else None,
        workdir=Path(args.workdir).resolve() if args.workdir else None,
        timeout_sec=args.timeout_sec,
        reasoning_effort=args.reasoning_effort,
    )
    result = solve(image_path=args.image, instruction=args.instruction, config=config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
