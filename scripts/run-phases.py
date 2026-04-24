#!/usr/bin/env python3
"""
cc-company phase runner.
Reads tasks/{task-dir}/index.json, finds the next pending phase,
spawns a Claude Code session with the phase prompt, and updates status.

Usage: python3 run-phases.py <task-dir>
Example: python3 run-phases.py 0-mvp
"""

import itertools
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from _utils import find_project_root

ROOT = find_project_root()
TASKS_DIR = ROOT / "tasks"
TOP_INDEX_FILE = TASKS_DIR / "index.json"

KST = timezone(timedelta(hours=9))

COMMIT_MSG_TEMPLATE = "feat({task_name}): phase {phase_num} — {phase_name}"
RUNNER_COMMIT_MSG_TEMPLATE = "chore({task_name}): phase {phase_num} output + timestamps"
SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

_gh_cache: dict = {"gh_user": None, "token": None,
                   "name": None, "email": None, "expires_at": 0}


def resolve_gh_env(gh_user: Optional[str]) -> dict[str, str]:
    """Resolve GitHub profile for gh_user and return environment variables."""
    if gh_user is None:
        return {}

    global _gh_cache

    # Check cache
    if (
        _gh_cache["gh_user"] == gh_user
        and time.time() < _gh_cache["expires_at"]
    ):
        return {
            "GH_TOKEN": _gh_cache["token"],
            "GIT_AUTHOR_NAME": _gh_cache["name"],
            "GIT_AUTHOR_EMAIL": _gh_cache["email"],
            "GIT_COMMITTER_NAME": _gh_cache["name"],
            "GIT_COMMITTER_EMAIL": _gh_cache["email"],
        }

    # Cache miss: resolve token
    result = subprocess.run(
        ["gh", "auth", "token", "--user", gh_user],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"ERROR: gh auth token failed for user '{gh_user}'. Run 'gh auth login' first.")
        sys.exit(1)
    token = result.stdout.strip()

    # Resolve name
    result = subprocess.run(
        ["gh", "api", "/user", "--jq", ".name"],
        env={**os.environ, "GH_TOKEN": token},
        capture_output=True,
        text=True,
    )
    name = result.stdout.strip() if result.returncode == 0 else ""

    # Resolve email
    result = subprocess.run(
        ["gh", "api", "/user", "--jq", ".email"],
        env={**os.environ, "GH_TOKEN": token},
        capture_output=True,
        text=True,
    )
    email = result.stdout.strip() if result.returncode == 0 else ""

    # Update cache
    _gh_cache.update(
        gh_user=gh_user,
        token=token,
        name=name,
        email=email,
        expires_at=time.time() + 900,
    )

    return {
        "GH_TOKEN": token,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }


def now_iso() -> str:
    return datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S%z")
    # e.g. 2026-03-19T02:09:18+0900


def load_index(index_file: Path) -> dict:
    with open(index_file, "r") as f:
        return json.load(f)


def save_index(index_file: Path, data: dict):
    with open(index_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_next_phase(index: dict) -> Optional[dict]:
    for phase in index["phases"]:
        if phase["status"] == "pending":
            return phase
    return None


def get_last_phase(index: dict) -> Optional[dict]:
    for phase in reversed(index["phases"]):
        if phase["status"] != "pending":
            return phase
    return None


def get_task_dir() -> Path:
    if len(sys.argv) < 2:
        print("Usage: python3 run-phases.py <task-dir>")
        print("Example: python3 run-phases.py 0-mvp")
        sys.exit(1)
    task_dir = TASKS_DIR / sys.argv[1]
    if not task_dir.is_dir():
        print(f"ERROR: Task directory not found: {task_dir}")
        sys.exit(1)
    return task_dir


def load_phase_prompt(task_dir: Path, phase_num: int) -> str:
    phase_file = task_dir / f"phase{phase_num}.md"
    if not phase_file.exists():
        print(f"ERROR: {phase_file} not found")
        sys.exit(1)
    return phase_file.read_text()


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_run(*args, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    run_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, text=True, env=run_env
    )


def git_commit_docs(task_name: str, gh_env: dict[str, str]):
    """Commit task plan files (tasks/, docs/, prompts/) before phase execution."""
    git_run("add", "tasks/", "docs/", "prompts/")

    if git_run("diff", "--cached", "--quiet").returncode == 0:
        return

    msg = f"docs: create {task_name} plan"
    r = git_run("commit", "-m", msg, env=gh_env if gh_env else None)
    if r.returncode == 0:
        print(f"  ✓ {msg}")
    else:
        print(f"  WARN: docs commit failed: {r.stderr.strip()}")


def git_commit_phase(task_name: str, task_dir_name: str, phase_num: int, phase_name: str, gh_env: dict[str, str]) -> bool:
    """Two-step commit: Claude fallback (if needed) + runner housekeeping."""
    output_file = f"tasks/{task_dir_name}/phase{phase_num}-output.json"
    index_file = f"tasks/{task_dir_name}/index.json"
    top_index = "tasks/index.json"

    commit_env = gh_env if gh_env else None

    # --- Step 1: Claude fallback commit (code changes Claude didn't commit) ---
    git_run("add", "-A")
    # Unstage runner-generated files so they don't mix into Claude's commit
    git_run("reset", "HEAD", "--", output_file)
    # index.json and top index may have runner timestamp updates — unstage too
    git_run("reset", "HEAD", "--", index_file)
    git_run("reset", "HEAD", "--", top_index)

    if git_run("diff", "--cached", "--quiet").returncode != 0:
        msg = COMMIT_MSG_TEMPLATE.format(
            task_name=task_name, phase_num=phase_num, phase_name=phase_name
        )
        r = git_run("commit", "-m", msg, env=commit_env)
        if r.returncode != 0:
            print(f"  WARN: fallback commit failed: {r.stderr.strip()}")

    # --- Step 2: Runner housekeeping commit (output + timestamps) ---
    git_run("add", "-A")
    if git_run("diff", "--cached", "--quiet").returncode != 0:
        msg = RUNNER_COMMIT_MSG_TEMPLATE.format(
            task_name=task_name, phase_num=phase_num
        )
        r = git_run("commit", "-m", msg, env=commit_env)
        if r.returncode != 0:
            print(f"  WARN: housekeeping commit failed: {r.stderr.strip()}")
            return False

    return True


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

class Spinner:
    def __init__(self, message: str):
        self._message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._start_time = 0.0

    def _spin(self):
        chars = itertools.cycle(SPINNER_CHARS)
        while not self._stop.is_set():
            elapsed = int(time.monotonic() - self._start_time)
            sys.stderr.write(f"\r{next(chars)} {self._message} [{elapsed}s]")
            sys.stderr.flush()
            self._stop.wait(0.1)
        # Clear the line
        sys.stderr.write("\r" + " " * (len(self._message) + 20) + "\r")
        sys.stderr.flush()

    def __enter__(self):
        self._start_time = time.monotonic()
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start_time


# ---------------------------------------------------------------------------
# Preamble & phase execution
# ---------------------------------------------------------------------------

def build_preamble(project_name: str, task_dir_name: str, task_name: str) -> str:
    commit_example = COMMIT_MSG_TEMPLATE.format(
        task_name=task_name, phase_num="N", phase_name="<phase-name>"
    )
    return f"""당신은 {project_name} 프로젝트의 개발자입니다. 아래 phase의 작업을 수행하세요.

중요한 규칙:
1. 작업 전에 반드시 문서를 읽고 전체 설계를 이해하세요.
2. 이전 phase에서 작성된 코드를 꼼꼼히 읽고, 기존 코드와의 일관성을 유지하세요.
3. AC 검증을 직접 수행하고, 통과/실패에 따라 /tasks/{task_dir_name}/index.json을 업데이트하세요.
4. 불필요한 파일이나 코드를 추가하지 마세요. phase에 명시된 것만 작업하세요.
5. 기존 테스트를 깨뜨리지 마세요.
6. AC 통과 후, index.json 업데이트까지 완료했다면, 모든 변경사항을 아래 형식으로 커밋하세요:
   {commit_example}

아래는 이번 phase의 상세 내용입니다:

"""


def run_phase(task_dir: Path, phase: dict, preamble: str, gh_env: dict[str, str]) -> dict:
    phase_num = phase["phase"]
    phase_name = phase["name"]
    prompt_content = load_phase_prompt(task_dir, phase_num)

    full_prompt = preamble + prompt_content

    output_file = task_dir / f"phase{phase_num}-output.json"

    cmd = [
        "claude",
        "-p",
        "--dangerously-skip-permissions",
        "--model", "sonnet",
        "--output-format", "json",
        full_prompt,
    ]

    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 minutes per phase
        env={**os.environ, **gh_env} if gh_env else None,
    )

    output_data = {
        "phase": phase_num,
        "name": phase_name,
        "exitCode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    if result.returncode != 0:
        print(f"\n  WARN: Claude exited with code {result.returncode}")
        print(f"  stderr: {result.stderr[:500]}")

    return output_data


# ---------------------------------------------------------------------------
# Top-level index helpers
# ---------------------------------------------------------------------------

def check_phase_status(index_file: Path, phase_num: int) -> str:
    fresh_index = load_index(index_file)
    for phase in fresh_index["phases"]:
        if phase["phase"] == phase_num:
            return phase.get("status", "pending")
    return "pending"


def update_top_index_status(task_dir_name: str, status: str):
    if not TOP_INDEX_FILE.exists():
        return
    top_index = load_index(TOP_INDEX_FILE)
    ts = now_iso()
    for task in top_index.get("tasks", []):
        if task.get("dir") == task_dir_name:
            task["status"] = status
            if status == "completed":
                task["completed_at"] = ts
            elif status == "error":
                task["failed_at"] = ts
            break
    save_index(TOP_INDEX_FILE, top_index)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    task_dir = get_task_dir()
    task_dir_name = task_dir.name
    index_file = task_dir / "index.json"

    if not index_file.exists():
        print(f"ERROR: {index_file} not found")
        sys.exit(1)

    index = load_index(index_file)
    project_name = index.get("project", "cc-company")
    task_name = index.get("task", task_dir_name)
    total_phases = index.get("totalPhases", len(index["phases"]))
    pending_count = sum(1 for p in index["phases"] if p["status"] == "pending")
    gh_user = index.get("gh_user")  # Optional
    gh_env = resolve_gh_env(gh_user)

    # --- Header ---
    print(f"\n{'='*60}")
    print(f"  hase Runner")
    print(
        f"  Task: {task_name} | Phases: {total_phases} | Pending: {pending_count}")
    if gh_user:
        print(f"  GitHub: {gh_user}")
    print(f"{'='*60}")

    # --- Error check ---
    last = get_last_phase(index)
    if last and last["status"] == "error":
        print(f"\n  ✗ Phase {last['phase']} ({last['name']}) failed.")
        if "error_message" in last:
            print(f"  Error: {last['error_message']}")
        print(
            f"  Fix the issue and reset status to 'pending' in {index_file} to retry.")
        sys.exit(1)

    # --- Docs commit ---
    git_commit_docs(task_name, gh_env)

    # --- Preamble ---
    preamble = build_preamble(project_name, task_dir_name, task_name)

    # --- Timestamps ---
    if "created_at" not in index:
        index["created_at"] = now_iso()
        save_index(index_file, index)
    if TOP_INDEX_FILE.exists():
        top_index = load_index(TOP_INDEX_FILE)
        for task in top_index.get("tasks", []):
            if task.get("dir") == task_dir_name and "created_at" not in task:
                task["created_at"] = index["created_at"]
                save_index(TOP_INDEX_FILE, top_index)
                break

    # --- Phase loop ---
    baseline = git_run("rev-parse", "HEAD").stdout.strip()

    while True:
        index = load_index(index_file)
        phase = find_next_phase(index)

        if phase is None:
            print("\n  All phases completed!")
            break

        phase_num = phase["phase"]
        phase_name = phase["name"]
        done_count = sum(
            1 for p in index["phases"] if p["status"] == "completed")

        # Record phase started_at (= execution start)
        ts_start = now_iso()
        for p in index["phases"]:
            if p["phase"] == phase_num and "started_at" not in p:
                p["started_at"] = ts_start
                save_index(index_file, index)
                break

        # Run with spinner
        with Spinner(f"Phase {phase_num}/{total_phases - 1} ({done_count} done): {phase_name}") as sp:
            run_phase(task_dir, phase, preamble, gh_env)
            elapsed = int(sp.elapsed)

        # Re-read index.json to check what Claude did
        fresh_index = load_index(index_file)
        status = None
        for p in fresh_index["phases"]:
            if p["phase"] == phase_num:
                status = p.get("status", "pending")
                break
        status = status or "pending"

        ts_end = now_iso()

        if status == "error":
            for p in fresh_index["phases"]:
                if p["phase"] == phase_num:
                    p["failed_at"] = ts_end
                    break
            save_index(index_file, fresh_index)
            print(f"  ✗ Phase {phase_num}: {phase_name} failed [{elapsed}s]")
            for p in fresh_index["phases"]:
                if p["phase"] == phase_num and "error_message" in p:
                    print(f"    Error: {p['error_message']}")
                    break
            print(
                f"  Fix the issue and reset status to 'pending' in {index_file} to retry.")
            update_top_index_status(task_dir_name, "error")
            sys.exit(1)

        if status == "completed":
            for p in fresh_index["phases"]:
                if p["phase"] == phase_num:
                    p["completed_at"] = ts_end
                    break
            save_index(index_file, fresh_index)

            # Generate docs-diff.md after phase 0 (docs update)
            if phase_num == 0:
                subprocess.run(
                    ["python3", str(
                        ROOT / "scripts" / "gen-docs-diff.py"), str(task_dir), baseline],
                    cwd=str(ROOT),
                )

            git_commit_phase(task_name, task_dir_name,
                             phase_num, phase_name, gh_env)
            print(
                f"  ✓ Phase {phase_num}: {phase_name} completed [{elapsed}s]")
        elif status == "pending":
            print(
                f"  ✗ Phase {phase_num}: {phase_name} — status still 'pending' after execution")
            print("    Claude did not update index.json. Marking as error.")

            for p in fresh_index["phases"]:
                if p["phase"] == phase_num:
                    p["status"] = "error"
                    p["error_message"] = "Claude did not update index.json status"
                    p["failed_at"] = ts_end
                    break
            save_index(index_file, fresh_index)
            update_top_index_status(task_dir_name, "error")
            sys.exit(1)

    # All phases done
    index = load_index(index_file)
    index["completed_at"] = now_iso()
    save_index(index_file, index)
    update_top_index_status(task_dir_name, "completed")

    # Commit any remaining changed files
    git_run("add", "-A")
    if git_run("diff", "--cached", "--quiet").returncode != 0:
        msg = f"chore({task_name}): mark task completed"
        r = git_run("commit", "-m", msg, env=gh_env if gh_env else None)
        if r.returncode == 0:
            print(f"  ✓ {msg}")
        else:
            print(f"  WARN: final commit failed: {r.stderr.strip()}")

    print(f"\n{'='*60}")
    print(f"  Task {task_dir_name}: all phases completed!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
