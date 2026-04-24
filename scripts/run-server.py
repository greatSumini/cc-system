#!/usr/bin/env python3
"""
Infinite ideation + build loop server.

Each iteration:
  1. ideation: `claude -p` runs ideation skill → writes
     iterations/{N}-{YYYYMMDD_HHMMSS}/requirement.md
     Retry up to 3 times; fatal exit if still missing.
  2. commit: `claude -p` runs commit skill to commit ideation artifacts.
     Every new commit must contain trailer `iter-id: {N}-{dt}`.
     Fatal exit if verification fails.
  3. build: `claude -p` runs plan-and-build skill to implement.
     The HEAD at the start of this step is remembered so a later rollback
     can restore the repo to exactly this point.
  4. check: `claude -p` inspects the newly created task and the current
     simulation report vs the previous iteration's simulation report,
     writes check-report.json (with `status` and `progress` fields),
     and commits it with the same marker.
  5. If `status == "fail"`: run a `claude -p` rollback session that
     `git reset --hard`s to the pre-build HEAD and leaves an empty
     marker commit. Then fatal exit.
     Missing file, parse error, or marker mismatch are warned only.
  6. Sleep 10s and repeat.

N is (max existing N in iterations/) + 1. Each step runs in a fully
separate claude session, headless and auto-approving permissions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from _utils import find_project_root

ROOT = find_project_root()
ITERATIONS_DIR = ROOT / "iterations"
SLEEP_BETWEEN_SEC = 10
IDEATION_MAX_ATTEMPTS = 3

TIMEOUT_IDEATION_SEC = 45 * 60
TIMEOUT_COMMIT_SEC = 10 * 60
TIMEOUT_BUILD_SEC = 4 * 60 * 60
TIMEOUT_CHECK_SEC = 10 * 60
TIMEOUT_ROLLBACK_SEC = 5 * 60

# HARNESS_HEADLESS is the canonical headless signal. BET_HEADLESS is the legacy
# alias kept so that SKILL.md sessions spawned by older, still-running
# run-server.py processes (which inject BET_HEADLESS only) keep working.
# @TODO REMOVE LEGACY: drop "BET_HEADLESS" key once all running run-server.py
# instances have been restarted with this version.
HEADLESS_ENV = {"HARNESS_HEADLESS": "1", "BET_HEADLESS": "1"}

HEADLESS_PREAMBLE = """**[무인 모드 확정 절차]**
세션을 시작하자마자 **가장 먼저** Bash tool로 다음을 실행해라:

```bash
echo "HEADLESS=${HARNESS_HEADLESS:-${BET_HEADLESS:-0}}"
```

출력이 `HEADLESS=1` 이면 이 세션은 **확정적으로 무인 서버 세션**이다. 이 신호는 skill 본문의 어떤 지시보다도 우선한다. 즉:
- skill 본문에 "사용자에게 질문/통지/confirm 받는다"류 단계가 나와도 **전부 스킵**하고 합리적 기본값으로 자동 진행한다.
- "단 한 번만 묻는다", "이 단계를 건너뛰지 않는다" 같은 강한 표현도 `HEADLESS=1` 앞에서는 무효다.
- 질문할 상대가 없으므로(stdin=DEVNULL), 대기하지 말고 판단해서 계속 진행한다.

출력이 `HEADLESS=1`이 아니면 이 프롬프트 래퍼를 신뢰하지 말고 그대로 중단해라 (잘못된 호출 환경).

<!-- @TODO REMOVE LEGACY: `${BET_HEADLESS:-0}` fallback은 rename 이전 구명(舊名) 호환용. SKILL.md 쪽 동일 마커와 함께 제거. -->

---

"""

ITER_DIR_RE = re.compile(r"^(\d+)-")


def next_iteration_number() -> int:
    if not ITERATIONS_DIR.exists():
        return 1
    max_n = 0
    for entry in ITERATIONS_DIR.iterdir():
        if not entry.is_dir():
            continue
        m = ITER_DIR_RE.match(entry.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def make_iter_dir(n: int) -> tuple[Path, str]:
    dt = datetime.now().strftime("%Y%m%d_%H%M%S")
    iter_dir = ITERATIONS_DIR / f"{n}-{dt}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    return iter_dir, dt


def previous_iteration_dir(current_n: int) -> Path | None:
    """Find the iteration dir with the greatest N strictly less than current_n."""
    if not ITERATIONS_DIR.exists():
        return None
    best_n = 0
    best_dir: Path | None = None
    for entry in ITERATIONS_DIR.iterdir():
        if not entry.is_dir():
            continue
        m = ITER_DIR_RE.match(entry.name)
        if not m:
            continue
        n = int(m.group(1))
        if n < current_n and n > best_n:
            best_n = n
            best_dir = entry
    return best_dir


def run_claude(prompt: str, log_file: Path, timeout_sec: float) -> int:
    """Invoke `claude -p` headlessly. Stream output to stdout and log_file.

    Kills the process after timeout_sec. On timeout, a note is written
    to the log and the returned exit code reflects the signal.
    """
    cmd = ["claude", "-p", "--dangerously-skip-permissions", prompt]
    with open(log_file, "w") as lf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, **HEADLESS_ENV},
        )

        timed_out = {"hit": False}

        def on_timeout() -> None:
            timed_out["hit"] = True
            msg = f"\n[TIMEOUT] exceeded {timeout_sec:.0f}s — terminating claude session.\n"
            sys.stderr.write(msg)
            sys.stderr.flush()
            lf.write(msg)
            lf.flush()
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass

        timer = threading.Timer(timeout_sec, on_timeout)
        timer.daemon = True
        timer.start()

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                lf.write(line)
                lf.flush()
            proc.wait()
        finally:
            timer.cancel()

        if timed_out["hit"]:
            print(f"[TIMEOUT] session killed after {timeout_sec:.0f}s")
        return proc.returncode


# ---------------------------------------------------------------------------
# Git helpers for commit-marker verification
# ---------------------------------------------------------------------------

def git_head() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def commits_since(pre_head: str) -> list[str]:
    r = subprocess.run(
        ["git", "log", f"{pre_head}..HEAD", "--format=%H"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return [h for h in r.stdout.splitlines() if h.strip()]


def commit_message(sha: str) -> str:
    r = subprocess.run(
        ["git", "log", "-1", "--format=%B", sha],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return r.stdout


def read_check_status(report_path: Path) -> str | None:
    """Read `status` field from check-report.json. Return None on any failure."""
    if not report_path.exists():
        return None
    try:
        data = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    status = data.get("status") if isinstance(data, dict) else None
    if status in ("pass", "warn", "fail"):
        return status
    return None


def verify_marker(pre_head: str, marker: str) -> tuple[bool, list[str], list[str]]:
    """Return (ok, with_marker, without_marker).

    ok iff at least one new commit exists AND every new commit contains marker.
    """
    new = commits_since(pre_head)
    with_m = [h for h in new if marker in commit_message(h)]
    without_m = [h for h in new if h not in with_m]
    ok = len(new) > 0 and len(without_m) == 0
    return ok, with_m, without_m


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def ideation_prompt(requirement_path: Path) -> str:
    return f"""{HEADLESS_PREAMBLE}ideation skill을 사용해 다음 스프린트에 구현할 단 하나의 요구사항을 선정해라.

이 세션은 무인 서버에서 자동 실행된다. 다음을 반드시 지켜라:
- 어떠한 사용자 확인/질문도 받지 마라.
- 페르소나가 여러 개라면 목록 상 첫 번째를 자동 선택한다.
- ideation SKILL.md의 Step 2.3 게이트 confirm(시뮬 비용 확인 등)은 자동 승인으로 간주하고 바로 진행한다.
- 가치제안 문서 draft/저장, 시뮬 실행, report 분석, tech-critic-lead 결재까지 인간 개입 0회로 끝까지 달린다.

최종 채택된 요구사항이 확정되면, 아래 내용을 합쳐 `{requirement_path}` 에 마크다운으로 저장해라:

```
# Requirement

## 가치제안
(시뮬에서 사용한 persuasion-data/runs/<run_id>/value_proposition.md 의 전체 내용을 그대로 복사)

## 채택된 요구사항
- run_id: <run_id>
- title: <채택된 요구사항 title>
- 유래한 고객 pain + 근거 인용
- 구현 스케치
- CTO 승인 조건부 조건 (있으면)
```

모든 후보가 tech-critic-lead 에 거부되어 채택에 실패한 경우에는 위 파일을 **만들지 말고** 그대로 종료해라.
"""


def commit_prompt(iter_dir: Path, iter_id: str) -> str:
    return f"""{HEADLESS_PREAMBLE}commit skill을 사용해서 방금 끝난 아이디에이션 단계의 산출물을 git commit 해라.

이 세션은 무인 서버에서 자동 실행된다. 다음을 반드시 지켜라:
- 어떠한 사용자 확인/승인도 받지 마라. 파일 분류/쪼개기/메시지 초안을 네가 판단해서 바로 진행한다.
- 현재 브랜치는 `main` 이고 이 프로젝트는 main에서 직접 작업한다. main commit 확인 질문은 스킵.
- push 금지. commit 까지만.
- 대상 파일: 이번 iteration 디렉토리(`{iter_dir}`) 하위의 `requirement.md`, 그리고 아이디에이션 과정에서 생성/수정된 `persuasion-data/` 하위 파일(예: `runs/<run_id>/*`).
- **제외할 파일: `iterations/**/*.log` 은 이번 commit에 포함하지 마라.** (세션 로그는 iteration 내내 계속 커지므로 커밋 대상 아님.) 무관한 작업 중 파일도 당연히 제외.

**매우 중요 — 반드시 지켜라:**
이 단계에서 만드는 **모든 commit**의 메시지 본문 하단 trailer에 아래 줄을 **정확히** 포함시켜라 (`Co-Authored-By`와 함께):

    iter-id: {iter_id}

예시:
```
feat(ideation): iter {iter_id} requirement 확정

...본문...

iter-id: {iter_id}
Co-Authored-By: Claude <noreply@anthropic.com>
```

이 trailer가 없는 commit이 하나라도 있으면 서버가 검증 실패로 간주해 프로세스를 종료한다.
"""


def build_prompt(requirement_path: Path) -> str:
    return f"""{HEADLESS_PREAMBLE}`{requirement_path}` 를 읽고 이번 iteration의 요구사항을 파악한 다음, plan-and-build skill을 사용해 현재 구현 상태와 맞지 않는 부분을 전부 구현해라.

- plan-and-build skill의 절차(docs 파악 → tech-critic-lead 논의 → 구현 계획 → 테스트 논의 → task/phase 생성 → `scripts/run-phases.py` 실행)를 그대로 따른다.
- 이 세션은 무인 서버에서 자동 실행된다. 사용자 확인을 일체 받지 말고 끝까지 진행해라.
"""


def check_prompt(
    iter_dir: Path,
    iter_id: str,
    report_path: Path,
    prev_iter_dir: Path | None,
) -> str:
    if prev_iter_dir is None:
        prev_block = (
            "이번이 첫 iteration이므로 직전 iteration이 없다. `progress.signal`은 "
            '`"no_prior_run"`, `previous_iter_id`와 `previous_run_id`는 `null`로 기록한다.'
        )
    else:
        prev_block = f"""직전 iteration 디렉토리: `{prev_iter_dir}`
거기의 `requirement.md` 를 Read로 읽어 `run_id`를 추출한다. 추출한 run_id로 `persuasion-data/runs/<prev_run_id>/report.md` 를 읽는다. (존재하지 않으면 `progress.signal`을 `"inconclusive"`로, summary에 "직전 run report 없음" 기록)"""

    return f"""{HEADLESS_PREAMBLE}직전 plan-and-build 세션이 생성한 task가 정상 완료되었는지, 그리고 이번 iteration이 직전 iteration 대비 고객 pain을 줄였는지 확인하고, 결과를 **JSON**으로 저장한 뒤 commit 하라.

이 세션은 무인 서버에서 자동 실행된다. 사용자 확인 일체 금지.

## 절차

### A. build 결과 점검

1. `tasks/index.json` 을 읽어 가장 최근(`created_at` 최대)에 생성된 task를 찾는다. 이 task가 이번 iteration에서 plan-and-build가 처리한 대상이다. 이번 iteration 시작 이후 생성된 task가 전혀 없다면 plan-and-build가 중간에 실패한 것이므로 `status: "fail"`로 기록한다.
2. 해당 task 디렉토리의 `index.json` 에서 각 phase의 `status`, `started_at`, `completed_at`, `failed_at`, `error_message`를 확인한다.
3. 각 phase의 `phase{{N}}-output.json` 이 있으면 `exitCode`, `stderr` 요약을 본다.

### B. 진척도(progress) 측정 — 직전 iteration 대비

4. 이번 iteration의 `{iter_dir / "requirement.md"}` 를 Read로 읽어 `run_id` (current_run_id)를 추출하고, `persuasion-data/runs/<current_run_id>/report.md` 를 읽는다.
5. {prev_block}
6. 두 report.md를 비교해 다음을 판정:
   - 직전 iteration에서 제기된 핵심 pain/우려/거부 사유 중 이번 iteration의 구현으로 해소된 것이 있는가?
   - 새로 발견된 pain이 있는가?
   - 페르소나의 최종 판정(성사/실패)이 개선되었는가?
7. 판정 결과를 `progress.signal`에 하나로 집약:
   - `"improved"` — 직전 대비 pain 감소 또는 판정 호전이 명확
   - `"regressed"` — 직전 대비 pain 증가 또는 판정 악화
   - `"inconclusive"` — 비교 가능하지만 delta가 미미/혼재
   - `"no_prior_run"` — 직전 iteration/run이 없음 (첫 iteration)

### C. 리포트 저장

8. `{report_path}` 에 아래 **정확한 JSON 스키마**로 저장한다. 스키마 바꾸지 말 것, `status`/`progress` 필드는 반드시 존재해야 한다:

```json
{{
  "iter_id": "{iter_id}",
  "status": "pass" | "warn" | "fail",
  "task": {{
    "dir": "tasks/<task_dir_name>",
    "name": "<task name>",
    "overall_status": "completed" | "error" | "incomplete" | "not_created"
  }},
  "phases": [
    {{
      "phase": 0,
      "name": "<phase name>",
      "status": "completed" | "error" | "pending",
      "duration_sec": <숫자 또는 null>,
      "notes": "<간단 메모 또는 빈 문자열>"
    }}
  ],
  "issues": [
    "<실패/미완 phase, error_message 요약 또는 의심 사항>"
  ],
  "conclusion": "<결론 한 줄 요약>",
  "carry_over": [
    "<다음 iteration으로 이월할 사항>"
  ],
  "progress": {{
    "previous_iter_id": "<N-1 기반 iter_id>" | null,
    "previous_run_id": "<prev run_id>" | null,
    "current_run_id": "<current run_id>",
    "signal": "improved" | "regressed" | "inconclusive" | "no_prior_run",
    "summary": "<2-3줄 — 무엇이 좋아졌고 무엇이 남아있는가>"
  }}
}}
```

`status` 판정 규칙:
- `"pass"` — 모든 phase가 completed이고 의심 사항 없음
- `"warn"` — 모두 completed이지만 확인 필요
- `"fail"` — 실패한 phase 존재 / task 미생성 / plan-and-build 중도 종료

task 정보가 없으면 `task.dir` / `task.name`을 `null`로 둔다. null이 아닌 경우 값만 채운다. JSON이 유효해야 한다 (서버가 파싱해서 읽는다). 주석(`//`) 남기지 말 것.

### D. commit

9. 저장한 뒤 **해당 파일만** `git add`해서 commit 하나를 만든다 (무관한 파일 staging 금지). 메시지 예시:

```
chore(iteration): iter {iter_id} build check report

<결론 + progress.signal 한 줄>

iter-id: {iter_id}
Co-Authored-By: Claude <noreply@anthropic.com>
```

trailer의 `iter-id: {iter_id}` 반드시 포함. push 금지. `*.log` 등 다른 파일 staging 금지.
"""


def rollback_prompt(iter_dir: Path, iter_id: str, pre_build_head: str) -> str:
    return f"""{HEADLESS_PREAMBLE}이번 iteration의 plan-and-build가 check 단계에서 `status: "fail"` 판정되었다. build 세션 이후의 모든 git 변경을 원복해라.

이 세션은 무인 서버에서 자동 실행된다. 사용자 확인 일체 금지. 개입도 금지.

## 절차

1. 현재 상태 확인:
   ```bash
   git log --oneline -10
   git status --short
   git branch --show-current
   ```
2. build 세션 시작 직전의 HEAD(= 복구 기준점): `{pre_build_head}`
   이 commit 이후 생성된 모든 commit을 원복한다.
   ```bash
   git reset --hard {pre_build_head}
   ```
3. reset 후 검증:
   ```bash
   git log --oneline -5
   git status --short
   ```
   HEAD가 `{pre_build_head}` 이면 성공.
4. rollback 흔적을 남기기 위해 **빈 commit** 하나 생성:

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore(iteration): iter {iter_id} build rolled back

check 단계에서 status=fail 판정되어 build 결과를 {pre_build_head[:10]} 시점으로 원복함.
상세는 iterations/{iter_dir.name}/check.log 참조 (로컬 gitignored).

iter-id: {iter_id}
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

5. 최종 확인:
   ```bash
   git log --oneline -3
   ```

- push 절대 금지. 로컬 reset + 빈 commit만.
- 중간에 에러가 나면 에러 메시지를 출력하고 그대로 종료해라. 추가 복구 시도 금지.
- reflog가 남아있으므로 실제로는 되돌릴 수 있다. 호출자가 후속 조치한다.
"""


# ---------------------------------------------------------------------------
# Iteration
# ---------------------------------------------------------------------------

def run_iteration(n: int) -> None:
    iter_dir, dt_str = make_iter_dir(n)
    iter_id = f"{n}-{dt_str}"
    marker = f"iter-id: {iter_id}"
    requirement_path = iter_dir / "requirement.md"
    report_path = iter_dir / "check-report.json"

    print(f"\n{'=' * 60}")
    print(f"  Iteration {iter_id}")
    print(f"{'=' * 60}")

    # 1) ideation (retry 3x on missing requirement.md)
    for attempt in range(1, IDEATION_MAX_ATTEMPTS + 1):
        print(f"\n[ideation] attempt {attempt}/{IDEATION_MAX_ATTEMPTS}")
        rc = run_claude(
            ideation_prompt(requirement_path),
            iter_dir / f"ideation-{attempt}.log",
            TIMEOUT_IDEATION_SEC,
        )
        print(f"[ideation] claude exit {rc}")
        if requirement_path.exists():
            print(f"[ideation] ✓ {requirement_path.relative_to(ROOT)} created")
            break
        print(f"[ideation] ✗ requirement.md not created")
    else:
        print(
            f"\n[fatal] ideation failed {IDEATION_MAX_ATTEMPTS} times — stopping server."
        )
        sys.exit(1)

    # 2) commit ideation artifacts + verify marker (fatal on fail)
    print(f"\n[commit] committing ideation artifacts")
    pre_head = git_head()
    run_claude(
        commit_prompt(iter_dir, iter_id),
        iter_dir / "commit.log",
        TIMEOUT_COMMIT_SEC,
    )
    ok, with_m, without_m = verify_marker(pre_head, marker)
    new_total = len(with_m) + len(without_m)
    if not ok:
        print(f"[commit] ✗ marker verification failed")
        print(f"  new commits since pre-session: {new_total}")
        print(f"  with marker:    {len(with_m)}")
        print(f"  without marker: {len(without_m)}")
        for h in without_m:
            print(f"    missing marker → {h[:10]}")
        print(f"[fatal] stopping server.")
        sys.exit(1)
    print(f"[commit] ✓ {len(with_m)} commit(s) carry marker")

    # 3) build — capture pre-build HEAD so we can rollback if check fails
    pre_build_head = git_head()
    print(f"\n[build] starting plan-and-build (pre_head={pre_build_head[:10]})")
    rc = run_claude(
        build_prompt(requirement_path),
        iter_dir / "build.log",
        TIMEOUT_BUILD_SEC,
    )
    print(f"[build] claude exit {rc}")
    if rc != 0:
        print(f"[build] ✗ non-zero exit — continuing to check anyway")
    else:
        print(f"[build] ✓ done")

    # 4) check build result + progress measurement + commit report
    prev_iter = previous_iteration_dir(n)
    print(f"\n[check] running post-build check (prev_iter={prev_iter})")
    pre_head = git_head()
    run_claude(
        check_prompt(iter_dir, iter_id, report_path, prev_iter),
        iter_dir / "check.log",
        TIMEOUT_CHECK_SEC,
    )

    ok, with_m, without_m = verify_marker(pre_head, marker)
    new_total = len(with_m) + len(without_m)
    if not ok:
        print(f"[check] ✗ marker verification failed (warn only)")
        print(f"  new commits since pre-session: {new_total}")
        print(f"  with marker:    {len(with_m)}")
        print(f"  without marker: {len(without_m)}")
        for h in without_m:
            print(f"    missing marker → {h[:10]}")
    else:
        print(f"[check] ✓ {len(with_m)} commit(s) carry marker")

    status = read_check_status(report_path)
    if status is None:
        print(
            f"[check] ✗ could not read status from {report_path.name} "
            f"(missing or invalid JSON) — warn, continuing"
        )
    else:
        print(f"[check] status={status}")
        if status == "fail":
            # 5) rollback before fatal exit
            print(
                f"\n[rollback] check=fail → reverting build to {pre_build_head[:10]}"
            )
            run_claude(
                rollback_prompt(iter_dir, iter_id, pre_build_head),
                iter_dir / "rollback.log",
                TIMEOUT_ROLLBACK_SEC,
            )
            new_head = git_head()
            if new_head == pre_build_head:
                print(f"[rollback] ✓ HEAD reset to {new_head[:10]} (empty marker commit pending or applied)")
            else:
                # rollback's empty commit moves HEAD forward by 1. Verify parent.
                parent = subprocess.run(
                    ["git", "rev-parse", f"{new_head}^"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                if parent == pre_build_head:
                    print(f"[rollback] ✓ HEAD={new_head[:10]} (parent = pre_build_head, empty marker commit applied)")
                else:
                    print(
                        f"[rollback] ✗ unexpected HEAD={new_head[:10]}, "
                        f"parent={parent[:10]}, expected pre_build_head={pre_build_head[:10]}"
                    )
            print(
                f"\n[fatal] check reported status='fail' — stopping server."
            )
            sys.exit(1)


def main() -> None:
    ITERATIONS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            n = next_iteration_number()
            run_iteration(n)
            print(f"\nSleeping {SLEEP_BETWEEN_SEC}s before next iteration...")
            time.sleep(SLEEP_BETWEEN_SEC)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
