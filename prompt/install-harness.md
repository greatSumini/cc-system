# install-harness

> **쓰는 법.** 이 파일 전체 내용을 복사해서 타겟 프로젝트에서 열린 Claude Code 세션에 프롬프트로 붙여넣으면 된다. Claude는 아래 절차대로 자율 주행 하네스(ideation → commit → build → check → rollback 무한 루프)를 타겟 프로젝트에 이식한다.
>
> persuasion-review 만 단독으로 쓰고 싶다면 이 프롬프트 대신 [`install-persuasion-review.md`](install-persuasion-review.md) 를 써라.

---

너(Claude)는 지금 타겟 프로젝트의 레포 루트에서 실행 중이다. 아래 절차를 **순서대로** 수행해 [`greatSumini/cc-system`](https://github.com/greatSumini/cc-system) 의 자율 주행 하네스를 설치해라. cc-system 쪽은 절대 수정하지 않는다.

---

## 0. 사전 확인

```bash
pwd                                   # 타겟 프로젝트 루트
git rev-parse --verify HEAD           # 커밋 1개 이상 있어야 rollback 타겟 존재 (없으면 먼저 초기 커밋)
git status                            # 더티 워킹트리면 사용자에게 정리 요청
command -v claude                     # claude CLI 필요
ls .claude 2>/dev/null                # 기존 .claude 와 충돌 여부
```

필요 조건 하나라도 불충족이면 사용자에게 보고하고 중단.

임시 작업 디렉토리에 cc-system 얕은 clone:

```bash
CC_SYSTEM=$(mktemp -d)/cc-system
git clone --depth=1 https://github.com/greatSumini/cc-system.git "$CC_SYSTEM"
```

---

## 1. 파일 복사 (하네스 본체)

아래 전부를 타겟 프로젝트 루트에 복사한다. 기존 동명 파일/디렉토리가 있으면 **덮어쓰지 말고** 사용자에게 diff 를 보이고 머지 방법을 물어라.

```bash
mkdir -p .claude/skills .claude/agents scripts prompts

# Skills (4종)
cp -R "$CC_SYSTEM/.claude/skills/persuasion-review"  .claude/skills/
cp -R "$CC_SYSTEM/.claude/skills/ideation"            .claude/skills/
cp -R "$CC_SYSTEM/.claude/skills/plan-and-build"      .claude/skills/
cp -R "$CC_SYSTEM/.claude/skills/commit"              .claude/skills/

# Sub-agent
cp "$CC_SYSTEM/.claude/agents/tech-critic-lead.md"    .claude/agents/

# Scripts (runner + 보조)
cp "$CC_SYSTEM/scripts/run-server.py"                 scripts/
cp "$CC_SYSTEM/scripts/run-phases.py"                 scripts/
cp "$CC_SYSTEM/scripts/gen-docs-diff.py"              scripts/
cp "$CC_SYSTEM/scripts/_utils.py"                     scripts/

# Task 규격
cp "$CC_SYSTEM/prompts/task-create.md"                prompts/
```

복사 후 체크:

```bash
ls .claude/skills .claude/agents scripts prompts
test -f scripts/run-server.py
test -f scripts/run-phases.py
test -f scripts/gen-docs-diff.py
test -f scripts/_utils.py
test -f prompts/task-create.md
test -f .claude/agents/tech-critic-lead.md
```

---

## 2. 타겟 프로젝트가 직접 만들어야 하는 것

하네스 실행에 필수인 **프로젝트 컨텍스트 파일들** 이다. 없으면 skill 들이 작동하지 않는다. 각 파일에 대해, 이미 유사 문서가 있는지 레포를 살피고, 없으면 프로젝트 특성에 맞게 초안을 작성한다. 작성 전 사용자에게 해당 프로젝트의 현재 상태(비전 / 스택 / 테스트 정책 / 운영 개입 포인트)를 짧게 물어라.

| 파일                         | 용도                                                               |
| ---------------------------- | ------------------------------------------------------------------ |
| `docs/mission.md`            | 제품 비전 · 가치제안 · BM. ideation/tech-critic-lead 가 읽는 기반. |
| `docs/spec.md`               | 라우트 · 데이터 모델 · API 계약. plan-and-build 의 주 참고서.      |
| `docs/testing.md`            | 테스트 정책 (mock 금지 / 실제 DB / AC 검증 방식 등).               |
| `docs/user-intervention.md`  | 인간 개입이 필요한 운영 절차 기록처.                               |
| `persuasion-data/personas/`  | 빈 디렉토리로 시작. 최소 1명의 페르소나 필요 (ideation 필수).      |
| `persuasion-data/runs/`      | 빈 디렉토리로 시작. 시뮬 결과가 여기 쌓임.                         |
| `persuasion-data/probe_tasks.md` | (웹 스택만) UX probe task 목록. `install-persuasion-review.md` 의 3.5 참조. |
| `persuasion-data/ux_probe_adapter.py` | (웹 스택만) 서비스 기동 어댑터. `install-persuasion-review.md` 의 3.0~3.4 참조. |
| `iterations/`                | 빈 디렉토리로 시작. run-server 가 이터레이션별 산출물 저장.        |
| `tasks/`                     | 빈 디렉토리로 시작. plan-and-build 가 task/phase 생성.             |

**페르소나 생성**과 **ux_probe_adapter 작성**은 대화형이므로 이 두 단계에서는 사용자에게 질문해도 된다. 나머지는 프로젝트 코드와 기존 README 를 읽어 추론한 뒤 한 번에 요약 보여주고 확인받는다.

**스택별 주의**. `ux_probe_adapter.py` 와 `probe_tasks.md` 는 **HTTP 로 접근 가능한 웹 스택일 때만** 만든다. iOS/Android 네이티브 · Flutter 모바일 · React Native · CLI 는 5a0 UX probe 가 적용되지 않는다 (어댑터 없으면 자동 skip). 프로젝트에 이미 `npm run dev` / `make dev` / `docker compose up` 같은 dev 진입점이 있으면 그걸 그대로 subprocess 로 감싸라 — 재발명하지 말 것. 자세한 스택 분기는 [`install-persuasion-review.md`](install-persuasion-review.md) Step 3.0 참조.

---

## 3. 환경 설정

### 3.1 gitignore

다음이 gitignore 에 없으면 추가:

```
iterations/*/*.log
```

세션 로그는 계속 커지므로 커밋 대상 제외. 단 iterations 디렉토리 자체 및 하위 `requirement.md`, `check-report.json` 등은 커밋되어야 하니 와일드카드 범위를 신중히.

### 3.2 Headless 환경변수

run-server.py 가 spawn 하는 claude 세션에 `HARNESS_HEADLESS=1` 을 자동 주입한다. SKILL.md 들은 이를 감지해 사용자 확인/질문 단계를 모두 자동 승인한다. 별도 export 불필요.

---

## 4. 첫 실행 (검증)

```bash
python3 scripts/run-server.py
```

처음 1 이터레이션이 성공적으로 돌면:

- `iterations/1-<timestamp>/` 생성
- `iterations/1-<timestamp>/requirement.md` 생성 (ideation 결과)
- `iterations/1-<timestamp>/check-report.json` 생성
- `iter-id: 1-<timestamp>` trailer 가 붙은 commit 여러 개가 git log 에 생김

실패하면 `iterations/1-<timestamp>/*.log` 를 읽어 stage 별 원인 파악.

로컬에서 짧게만 검증하고 Ctrl-C 로 중단해도 된다. 다시 실행하면 이어서 N+1 이터레이션이 돈다.

---

## 5. 정리

```bash
rm -rf "$CC_SYSTEM"
```

---

## 6. 문서에 하네스 섹션 추가

타겟 프로젝트 README 에 "자율 주행 하네스" 섹션을 한 단락 추가하자. 이 프로젝트가 왜 이 하네스를 쓰는지, 누가 어떻게 트리거하는지, Headless 변수 이름(`HARNESS_HEADLESS`)만 명시하면 충분.

커밋 제안:

```
chore(harness): cc-system 자율 주행 하네스 이식

- .claude/skills/{persuasion-review,ideation,plan-and-build,commit}/
- .claude/agents/tech-critic-lead.md
- scripts/{run-server,run-phases,gen-docs-diff,_utils}.py
- prompts/task-create.md
- docs/{mission,spec,testing,user-intervention}.md 초안
- persuasion-data/ 스캐폴드 + ux_probe_adapter
- README 에 하네스 섹션 추가
```

---

## 자주 하는 실수 (하지 말 것)

- ❌ 초기 커밋 없는 레포에서 `run-server.py` 실행 — 첫 iteration rollback 타겟 없어 터진다.
- ❌ `docs/` 를 비워둔 채로 실행 — plan-and-build 가 컨텍스트 없이 헛돈다.
- ❌ 페르소나 0개로 실행 — ideation 이 즉시 중단.
- ❌ `persuasion-data/` 를 `.claude/` 밑에 두기 — headless Write 차단 당한다.
- ❌ `scripts/gen-docs-diff.py` 누락 — phase 0 직후 run-phases 가 터진다.
- ❌ `HARNESS_HEADLESS` 를 쉘에서 직접 export — 인터랙티브 세션도 무인 모드로 튀어 질문이 봉인된다. 오직 run-server.py 가 spawn 하는 서브 세션에만 주입되도록 두라.
- ❌ 하네스 스크립트를 수정한 뒤 upstream cc-system 으로 PR 을 안 보내기 — 개선 사항이 다음 프로젝트로 전파되지 않는다.
