"""
Adapter around `codex exec` and `codex exec resume`.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .schemas import SchemaValidationError


class CodexCliError(RuntimeError):
    """Raised when the Codex CLI invocation fails."""


@dataclass
class CodexSession:
    role: str
    session_id: Optional[str] = None


@dataclass
class CodexResponse:
    session_id: str
    raw_text: str
    payload: Dict[str, Any]
    stdout: str
    stderr: str


class CodexCliAdapter:
    def __init__(
        self,
        model: str,
        workdir: Path,
        codex_bin: str = "codex",
        timeout_sec: int = 300,
        format_retries: int = 1,
        reasoning_effort: Optional[str] = None,
    ) -> None:
        self.model = model
        self.workdir = Path(workdir)
        self.codex_bin = codex_bin
        self.timeout_sec = timeout_sec
        self.format_retries = format_retries
        self.reasoning_effort = reasoning_effort

    def invoke_json(
        self,
        session: CodexSession,
        prompt: str,
        image_paths: Sequence[Path],
        output_path: Path,
        validator: Callable[[Dict[str, Any]], Any],
        schema_path: Optional[Path] = None,
    ) -> Tuple[CodexSession, str, Any]:
        current_prompt = prompt
        current_schema = schema_path
        last_error: Optional[Exception] = None

        for _ in range(self.format_retries + 1):
            response = self._invoke_once(
                session=session,
                prompt=current_prompt,
                image_paths=image_paths,
                output_path=output_path,
                schema_path=current_schema,
            )
            session.session_id = response.session_id

            try:
                normalized = validator(response.payload)
                return session, response.raw_text, normalized
            except (SchemaValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
                last_error = exc
                current_schema = None
                current_prompt = self._repair_prompt(response.raw_text, str(exc))

        raise SchemaValidationError(
            "Failed to obtain valid JSON from %s: %s" % (session.role, last_error)
        )

    def _invoke_once(
        self,
        session: CodexSession,
        prompt: str,
        image_paths: Sequence[Path],
        output_path: Path,
        schema_path: Optional[Path],
    ) -> CodexResponse:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        if session.session_id:
            command = self._resume_command(
                session_id=session.session_id,
                prompt=prompt,
                image_paths=image_paths,
                output_path=output_path,
            )
        else:
            command = self._start_command(
                prompt=prompt,
                image_paths=image_paths,
                output_path=output_path,
                schema_path=schema_path,
            )

        completed = subprocess.run(
            command,
            cwd=str(self.workdir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=self.timeout_sec,
        )
        if completed.returncode != 0:
            raise CodexCliError(
                "Codex CLI failed for %s.\nCommand: %s\nSTDOUT:\n%s\nSTDERR:\n%s"
                % (session.role, " ".join(command), completed.stdout, completed.stderr)
            )

        session_id = self._extract_session_id(completed.stdout) or session.session_id
        if not session_id:
            raise CodexCliError("Failed to extract Codex session id for %s" % session.role)
        if not output_path.exists():
            raise CodexCliError("Codex CLI did not produce --output-last-message for %s" % session.role)

        raw_text = output_path.read_text(encoding="utf-8").strip()
        payload = self._parse_json_text(raw_text)
        return CodexResponse(
            session_id=session_id,
            raw_text=raw_text,
            payload=payload,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _start_command(
        self,
        prompt: str,
        image_paths: Sequence[Path],
        output_path: Path,
        schema_path: Optional[Path],
    ) -> List[str]:
        command = [
            self.codex_bin,
            "exec",
            prompt,
            "--json",
            "--skip-git-repo-check",
            "--model",
            self.model,
            "--output-last-message",
            str(output_path),
        ]
        if self.reasoning_effort:
            command.extend(["-c", f'model_reasoning_effort="{self.reasoning_effort}"'])
        if schema_path is not None:
            command.extend(["--output-schema", str(schema_path)])
        command.extend(self._image_args(image_paths))
        return command

    def _resume_command(
        self,
        session_id: str,
        prompt: str,
        image_paths: Sequence[Path],
        output_path: Path,
    ) -> List[str]:
        command = [
            self.codex_bin,
            "exec",
            "resume",
            session_id,
            prompt,
            "--json",
            "--skip-git-repo-check",
            "--model",
            self.model,
            "--output-last-message",
            str(output_path),
        ]
        if self.reasoning_effort:
            command.extend(["-c", f'model_reasoning_effort="{self.reasoning_effort}"'])
        command.extend(self._image_args(image_paths))
        return command

    def _image_args(self, image_paths: Sequence[Path]) -> List[str]:
        args: List[str] = []
        for image_path in image_paths:
            args.extend(["--image", str(image_path)])
        return args

    def _extract_session_id(self, stdout: str) -> Optional[str]:
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                return event["thread_id"]
        return None

    def _parse_json_text(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = self._strip_code_fence(cleaned)
        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise SchemaValidationError("Expected a JSON object")
        return payload

    def _strip_code_fence(self, text: str) -> str:
        lines = text.strip().splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _repair_prompt(self, invalid_raw_text: str, error_message: str) -> str:
        return "\n".join(
            [
                "Your previous reply was not valid JSON for the required structure.",
                "Return only one corrected JSON object.",
                "Do not add markdown or commentary.",
                "Validation error:",
                error_message,
                "Previous invalid reply:",
                invalid_raw_text,
            ]
        )
