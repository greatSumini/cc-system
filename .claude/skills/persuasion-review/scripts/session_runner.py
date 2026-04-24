"""claude -p 헤드리스 세션 래퍼.

각 세션은 (a) system prompt 템플릿 파일과 (b) task prompt 문자열을 받아
subprocess로 claude CLI를 실행하고, 지정된 출력 경로의 frontmatter를 파싱해 반환한다.

CLI 플래그가 버전에 따라 다를 수 있어 상단 상수로 뽑아두었다. 환경에 맞춰 조정.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


# claude CLI 경로 및 주요 플래그. 버전/설치 방식에 따라 조정 가능.
# 환경에 여러 claude 바이너리(예: pnpm glob 2.0.x와 ~/.claude/local/ 2.1.x)가 공존할 때
# subprocess PATH가 구버전을 집어 nested 실행이 "Execution error"로 조기 실패하는 사례 있음.
# 우선순위: ~/.claude/local/claude > PATH에서 first match.
import os as _os
import shutil as _shutil
_local_claude = _os.path.expanduser("~/.claude/local/claude")
CLAUDE_BIN = ((_local_claude if _os.path.exists(_local_claude) else None)
              or _shutil.which("claude")
              or "claude"
              )
PERMISSION_MODE = "bypassPermissions"  # 헤드리스 실행 시 Read/Write 허용 간소화


@dataclass
class SessionResult:
    output_path: Path
    frontmatter: dict
    body: str
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""

    @property
    def decision(self) -> str:
        return str(self.frontmatter.get("decision", "error"))

    @property
    def confidence(self) -> int:
        try:
            return int(self.frontmatter.get("confidence", 0))
        except (TypeError, ValueError):
            return 0

    @property
    def ok(self) -> bool:
        return self.error is None


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Markdown 문자열에서 --- 로 감싼 YAML frontmatter를 추출."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, text
    return meta, parts[2].lstrip("\n")


DEFAULT_ALLOWED_TOOLS = ("Read", "Write")


def run_session(
    *,
    system_prompt_path: Path,
    task_prompt: str,
    output_path: Path,
    timeout_sec: int = 600,
    allowed_tools: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS,
) -> SessionResult:
    """claude headless 세션을 1회 실행하고 결과 파일을 파싱해 반환.

    allowed_tools: 기본 (Read, Write). UX probe 등 Bash가 필요한 세션은 호출측에서 확장.
    """
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        CLAUDE_BIN,
        "-p", task_prompt,
        "--append-system-prompt", system_prompt,
        # subprocess에서는 상호작용 승인이 불가하므로 권한 체크를 완전히 스킵.
        # --permission-mode bypassPermissions만으로는 Write가 차단되는 사례 확인됨(2.1.117).
        "--dangerously-skip-permissions",
        "--allowed-tools", *allowed_tools,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return SessionResult(
            output_path=output_path,
            frontmatter={"decision": "error", "confidence": 0},
            body="",
            error=f"timeout after {timeout_sec}s",
            stdout=(exc.stdout or ""),
            stderr=(exc.stderr or ""),
        )
    except FileNotFoundError:
        return SessionResult(
            output_path=output_path,
            frontmatter={"decision": "error", "confidence": 0},
            body="",
            error=f"'{CLAUDE_BIN}' 바이너리를 찾을 수 없음. PATH 확인.",
        )

    if proc.returncode != 0:
        return SessionResult(
            output_path=output_path,
            frontmatter={"decision": "error", "confidence": 0},
            body="",
            error=f"subprocess failed (code {proc.returncode})",
            stdout=proc.stdout[-2000:],
            stderr=proc.stderr[-2000:],
        )

    if not output_path.exists():
        return SessionResult(
            output_path=output_path,
            frontmatter={"decision": "error", "confidence": 0},
            body="",
            error="output file not created by session",
            stdout=proc.stdout[-2000:],
            stderr=proc.stderr[-2000:],
        )

    content = output_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    return SessionResult(
        output_path=output_path,
        frontmatter=fm,
        body=body,
        stdout=proc.stdout[-2000:],
        stderr=proc.stderr[-2000:],
    )
