"""
Shared utilities for agentinc scripts.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def find_project_root() -> Path:
    """.git 디렉토리가 존재하는 폴더를 만날 때까지 위로 이동하여 프로젝트 루트를 반환."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root (no .git directory found)")


# ---------------------------------------------------------------------------
# GitHub environment utilities
# ---------------------------------------------------------------------------

_gh_cache: dict = {"gh_user": None, "token": None, "name": None, "email": None, "expires_at": 0}


def resolve_gh_env(gh_user: Optional[str]) -> dict[str, str]:
    """Resolve GitHub profile for gh_user and return environment variables.

    Args:
        gh_user: gh CLI에 등록된 GitHub 계정명. None이면 빈 dict 반환.

    Returns:
        GH_TOKEN, GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_NAME, GIT_COMMITTER_EMAIL을 포함한 dict.
        gh_user가 None이면 빈 dict.
    """
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
        print(f"ERROR: gh auth token failed for user '{gh_user}'. Run 'gh auth login' first.")
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
