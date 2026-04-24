# install-persuasion-review

> **쓰는 법.** 이 파일 전체 내용을 복사해서 타겟 프로젝트에서 열린 Claude Code 세션에 프롬프트로 붙여넣으면 된다. Claude는 아래 절차대로 `persuasion-review` skill + 보조 파일들을 해당 프로젝트에 이식한다.

---

너(Claude)는 지금 타겟 프로젝트의 레포 루트에서 실행 중이다. 아래 절차를 **순서대로** 수행해 `persuasion-review` skill 과 부속 자산을 이 프로젝트에 설치해라. 자료는 [`greatSumini/cc-system`](https://github.com/greatSumini/cc-system) 레포에서 가져온다.

---

## 0. 사전 확인

```bash
pwd                     # 타겟 프로젝트 루트여야 한다
git status              # 더티 워킹트리면 사용자에게 먼저 commit 하자고 제안
ls .claude 2>/dev/null  # 이미 .claude 가 있으면 기존 파일과 충돌하지 않는지 확인
```

그리고 `cc-system` 레포를 로컬 작업 디렉토리로 **얕은 clone** 한다 (임시 디렉토리):

```bash
CC_SYSTEM=$(mktemp -d)/cc-system
git clone --depth=1 https://github.com/greatSumini/cc-system.git "$CC_SYSTEM"
```

clone 실패 시 사용자에게 network 이슈 가능성을 보고하고 중단.

---

## 1. 파일 복사

아래 표의 **From → To** 로 정확히 복사한다. `$CC_SYSTEM`은 위에서 clone 한 경로, 그 외 경로는 전부 타겟 프로젝트 루트 기준.

| From (cc-system 내)                  | To (타겟 프로젝트)                   | 비고                                                                           |
| ------------------------------------ | ------------------------------------ | ------------------------------------------------------------------------------ |
| `.claude/skills/persuasion-review/`  | `.claude/skills/persuasion-review/`  | skill 본체 + SPEC + scripts 통째                                               |
| `.claude/agents/tech-critic-lead.md` | `.claude/agents/tech-critic-lead.md` | 자율 루프·ideation 이식 시에만 필요. persuasion-review 단독 사용이면 생략 가능 |

```bash
mkdir -p .claude/skills .claude/agents persuasion-data
cp -R "$CC_SYSTEM/.claude/skills/persuasion-review" .claude/skills/
# (선택) ideation/tech-critic-lead 도 함께 이식할 때만:
# cp "$CC_SYSTEM/.claude/agents/tech-critic-lead.md" .claude/agents/
```

목적지에 같은 이름 파일/디렉토리가 이미 있으면 **덮어쓰지 말고** 사용자에게 diff 를 보여주고 어떻게 머지할지 물어라.

---

## 2. 데이터 디렉토리 스캐폴드

`persuasion-review` 는 레포 루트의 `persuasion-data/` 를 규약으로 쓴다. Claude Code가 `.claude/` 경로를 sensitive 로 분류해 headless 세션에서 Write 를 막기 때문에 데이터는 반드시 이 위치여야 한다.

```
persuasion-data/
  personas/                # Flow A 로 생성할 페르소나 (초기엔 비어있음)
  runs/                    # 시뮬 결과물 (자동 생성)
  probe_tasks.md           # 페르소나가 UX probe 중 수행할 task 목록
  ux_probe_adapter.py      # 프로젝트별 서비스 기동 어댑터 (뒤 Step 3 에서 작성)
```

`personas/`, `runs/` 빈 디렉토리만 만들고 `.gitkeep` 은 선택.

---

## 3. `ux_probe_adapter.py` 작성 — **가장 중요한 단계**

이게 프로젝트별로 유일하게 직접 작성해야 할 파일이다. 계약:

```python
def start(run_dir: pathlib.Path) -> dict:
    """서비스 기동 (필요 시 데이터 seed). 반환 dict 필수 키:
      - base_url: str          서비스 루트 URL
      - python_bin: str        ux_probe.py 를 실행할 python 경로 (playwright 설치 필수)
      - credentials: dict      페르소나가 로그인 시 쓸 자격 (자유 형식)
      - context: dict          템플릿 컨텍스트 (자유 형식, 예: entity ids)
      - tasks_markdown: str    페르소나에게 줄 Task 목록 (probe_tasks.md 를 포맷팅한 결과)
    side effect: 서버 pid 등 teardown 에 필요한 상태를 run_dir 하위에 보존.
    """

def stop(run_dir: pathlib.Path) -> None:
    """start 가 띄운 서비스를 종료. 실패해도 예외를 던지지 않는다."""
```

### 3.1 타겟 프로젝트 조사

adapter 작성 전에 다음을 반드시 파악해라. 모르는 항목이 있으면 **사용자에게 물어라** (추측 금지):

1. **서비스 기동 커맨드**. 예: `uvicorn app.main:app`, `npm run dev`, `python manage.py runserver`. 포트는 고정인지 자유인지.
2. **필수 환경변수**. DB 경로, 세션 시크릿, 어드민 자격 등. fail-fast 하는 env 가 있는지.
3. **Ready endpoint**. `GET` 했을 때 200/3xx 로 응답하는 경로. 로그인 페이지가 일반적.
4. **Seed 스크립트**가 있는지. 없으면 사용자에게 만들어야 할지 물어라. 있으면 마지막 줄에 JSON 한 줄 (`{"foo": 1, "bar": [2,3]}`) 을 찍도록 개조한다 — 어댑터가 `probe_harness.load_seed_result()` 로 파싱.
5. **DB 초기화 전략**. SQLite 파일 삭제, `createdb && migrate`, 컨테이너 기동 등.
6. **페르소나가 실행할 Task 목록**. 프로젝트 도메인에 맞게 `probe_tasks.md` 를 작성한다.

조사 결과를 **한 번만** 요약해서 사용자에게 확인받고, 승인 후 어댑터를 작성한다.

### 3.2 어댑터 작성 — 공용 유틸 적극 사용

`persuasion-review` skill 에는 공용 plumbing 이 들어있다 (`.claude/skills/persuasion-review/scripts/probe_harness.py`). `run_simulation.py` 가 어댑터를 동적 로드할 때 해당 경로를 `sys.path` 에 주입해주므로 어댑터에서는 그냥 `from probe_harness import ...` 로 쓰면 된다.

제공 API:

```python
from probe_harness import (
    free_port,                 # () -> int                    자유 로컬 포트
    wait_http_ready,           # (url, timeout_sec) -> bool
    spawn_and_wait_ready,      # (cmd, *, env, cwd, ready_url, timeout_sec, pidfile) -> Popen
    stop_by_pidfile,           # (pidfile) -> None            프로세스 그룹까지 kill
    load_seed_result,          # (stdout) -> dict             seed stdout 마지막 JSON 줄 파싱
)
```

**Python 웹앱 템플릿** (대부분의 FastAPI/Django/Flask 프로젝트에서 몇 줄만 고치면 된다):

```python
"""persuasion-review 5a0 UX probe 어댑터 (이 프로젝트 전용)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from probe_harness import (
    free_port,
    load_seed_result,
    spawn_and_wait_ready,
    stop_by_pidfile,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = REPO_ROOT / "persuasion-data" / "probe_tasks.md"
READY_TIMEOUT_SEC = 15
PROBE_USERNAME = "probeadmin"
PROBE_PASSWORD = "probepw"


def start(run_dir: Path) -> dict:
    probe_dir = run_dir / "probe"
    probe_dir.mkdir(parents=True, exist_ok=True)

    # 1) DB 초기화 (프로젝트별)
    db_path = probe_dir / "app.db"
    if db_path.exists():
        db_path.unlink()

    # 2) env (프로젝트별)
    port = free_port()
    env = {
        **os.environ,
        "DATABASE_PATH": str(db_path),
        # ... 프로젝트 필수 env ...
    }

    # 3) seed (프로젝트별) — 마지막 줄에 JSON 출력 필요
    seed = subprocess.run(
        [sys.executable, "scripts/seed.py"],
        env=env, cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=60,
    )
    if seed.returncode != 0:
        raise RuntimeError(f"seed failed: {seed.stderr[-500:]}")
    seed_result = load_seed_result(seed.stdout)

    # 4) 서버 기동 (프로젝트별 cmd, ready path)
    base_url = f"http://127.0.0.1:{port}"
    spawn_and_wait_ready(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, cwd=str(REPO_ROOT),
        ready_url=base_url + "/login",
        timeout_sec=READY_TIMEOUT_SEC,
        pidfile=probe_dir / "server.pid",
    )

    # 5) tasks_markdown 렌더
    tasks_markdown = TASKS_PATH.read_text(encoding="utf-8").format(
        base_url=base_url,
        username=PROBE_USERNAME,
        password=PROBE_PASSWORD,
        **seed_result,          # seed 가 반환한 ids 등을 그대로 템플릿 변수로
    )

    return {
        "base_url": base_url,
        "python_bin": sys.executable,
        "credentials": {"username": PROBE_USERNAME, "password": PROBE_PASSWORD},
        "context": seed_result,
        "tasks_markdown": tasks_markdown,
    }


def stop(run_dir: Path) -> None:
    stop_by_pidfile(run_dir / "probe" / "server.pid")
```

**Node 프로젝트** 라면 `[sys.executable, "-m", "uvicorn", ...]` 자리를 `["npm", "run", "dev", "--", "--port", str(port)]` 등으로 바꾸고, seed 가 node script 면 `["node", "scripts/seed.js"]` 로. `python_bin` 은 playwright 실행에 쓰이므로 로컬 `python3` 경로가 맞으면 그대로 두면 된다.

### 3.3 `probe_tasks.md` 작성

페르소나가 **로그인 → 주요 기능 1~3개 → 종합 소감** 까지 수행할 Task 리스트를 마크다운으로 작성. `{base_url}`, `{username}` 등 `str.format` placeholder 를 자유롭게 써라. 어댑터의 `start()` 마지막에서 포맷팅해 tasks_markdown 으로 반환한다.

끝 부분에 "이 서비스를 {핵심 이해관계자} 입장에서 자신있게 보여줄 수 있겠는가?" 같은 개방형 질문 한 줄을 반드시 넣어라. 시뮬 결과의 질을 좌우한다.

---

## 4. 페르소나 만들기

`persuasion-review` 는 페르소나 없이는 시뮬을 돌릴 수 없다. 사용자에게 대상 고객 1명을 구체적으로 서술해달라고 요청하고, skill 의 **Flow A** 로 페르소나를 생성한다 (대화형이므로 무인 모드에서는 불가능).

---

## 5. 설치 확인

1. `.claude/skills/persuasion-review/SKILL.md` Read → 첫 문단 렌더 확인.
2. `persuasion-data/` 트리 확인.
3. 사용자에게 `persuasion-review` 를 트리거해보라고 제안 (예: "설득력 검토").

---

## 6. 정리

```bash
rm -rf "$CC_SYSTEM"
```

커밋 제안:

```
chore(persuasion-review): cc-system 에서 skill 이식

- .claude/skills/persuasion-review/ 추가
- persuasion-data/{personas,runs,probe_tasks.md,ux_probe_adapter.py} 스캐폴드
- ux_probe_adapter 는 이 프로젝트의 <기동 커맨드>/<seed>/<ready endpoint> 기준
```

---

## 자주 하는 실수 (하지 말 것)

- ❌ `persuasion-data/` 를 `.claude/` 밑에 만들기 — Write 차단됨.
- ❌ `start()` 가 동기적으로 바로 Popen 리턴 — ready-poll 안 하면 첫 페이지 로드 실패로 probe 전체 불발.
- ❌ 어댑터에 프로덕션 DB 붙이기 — 반드시 run_dir 하위 임시 DB.
- ❌ 비밀 값을 어댑터 소스에 하드코딩 — 테스트용 자격은 OK, 프로덕션 시크릿은 안 됨.
- ❌ `probe_tasks.md` 를 영문으로만 쓰기 — 페르소나 언어와 맞춰라.
- ❌ seed 스크립트 stdout 마지막 줄이 JSON 이 아닌 상태로 방치 — `load_seed_result()` 가 터진다.
