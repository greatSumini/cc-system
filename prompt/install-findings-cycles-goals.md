# install-findings-cycles-goals

> **쓰는 법.** 이 파일 전체 내용을 복사해서 타겟 프로젝트에서 열린 Claude Code 세션에 프롬프트로 붙여넣으면 된다. Claude는 아래 절차대로 [`vibemafiaclub/vooster`](https://github.com/vibemafiaclub/vooster) 의 **findings → cycles → goals (FCG)** 자율 빌드 하네스를 (스택 중립 버전으로) 타겟 프로젝트에 이식한다.
>
> 이 시스템은 루핑 에이전트(codex / Claude)가 사람 개입 없이 매 iteration 동일한 루프 — `diagnose → next-task → TDD → active-check → completion-check` — 를 돌며 미션을 완수하게 한다. 원본 자산은 [`greatSumini/cc-system`](https://github.com/greatSumini/cc-system) 의 `findings-cycles-goals/` 디렉토리에 있고, 이 프롬프트가 그걸 복사해온다. cc-system 쪽은 절대 수정하지 않는다.

---

너(Claude)는 지금 타겟 프로젝트의 레포 루트에서 실행 중이다. 아래 절차를 **순서대로** 수행해라. 먼저 [`greatSumini/cc-system`](https://github.com/greatSumini/cc-system) 의 `findings-cycles-goals/` 디렉토리에 들어있는 설계·규약 문서(`docs/goal-design.md`, `guidelines/goal-iteration.md`, 각 `AGENTS.md`)를 **읽고 이 시스템을 이해한 뒤** 작업한다 — 기계적 복사만 하지 말 것.

---

## 0. 사전 확인

```bash
pwd                                   # 타겟 프로젝트 루트인지
git rev-parse --verify HEAD           # 커밋 1개 이상 (없으면 먼저 초기 커밋 권장)
git status                            # 더티 워킹트리면 사용자에게 정리 요청
# 충돌 가능 경로 확인 (있으면 덮어쓰지 말고 사용자에게 보고)
ls scripts/completion-check.sh goals guidelines cycles docs/findings docs/goal-design.md 2>/dev/null
```

필수 조건(타겟 프로젝트 루트 + git 레포) 불충족이면 사용자에게 보고하고 중단.

임시 작업 디렉토리에 cc-system 얕은 clone:

```bash
CC_SYSTEM=$(mktemp -d)/cc-system
git clone --depth=1 https://github.com/greatSumini/cc-system.git "$CC_SYSTEM"
KIT="$CC_SYSTEM/findings-cycles-goals"
test -d "$KIT" || { echo "kit 디렉토리 없음 — cc-system 구조 확인"; exit 1; }
```

---

## 1. 설계 문서 먼저 읽기 (이해 단계)

복사 전에 아래를 읽어 시스템을 이해한다. 기계적 이식은 금지 — 이 문서들이 **왜** 이렇게 동작하는지 파악해야 뒤의 적응 단계(§4)를 제대로 한다.

```bash
cat "$KIT/README.md"                       # 3-자산 모델 + 경로 매핑 한눈에
cat "$KIT/docs/goal-design.md"             # 핵심 설계 원칙 (§1 universal gate, §1.5 gates≠police, §5 immutable)
cat "$KIT/guidelines/goal-iteration.md"    # 한 iteration 의 흐름
cat "$KIT/goals/AGENTS.md" "$KIT/findings/AGENTS.md" "$KIT/cycles/AGENTS.md"
```

핵심 요약 (반드시 내재화):

- **3-자산**: `docs/findings/` (부채 큐) → `cycles/` (세션 프롬프트) → `goals/` (gate 로 검증되는 영속 invariant). 검증되는 건 goal 뿐, findings/cycles 는 큐/이력.
- **goal = 세 파일**: `<n>-<name>.md` (미션, universal claim) + `.gates.sh` (기계 검증, **"every X" 면 enumerate**) + `.next-task.sh` (advisory hint).
- **active goal = 첫 실패 goal**. `completion-check.sh` 가 `.state/active-goal` 에 기록하고 모든 도구가 그걸 신호로 쓴다.
- **gates ≠ convention police**: 테스트/typecheck/coverage 가 더 정확히 잡는 건 gate 에서 grep 하지 마라.

---

## 2. 파일 복사 (FCG 본체)

아래 매핑대로 타겟 프로젝트에 복사한다. 기존 동명 파일/디렉토리가 있으면 **덮어쓰지 말고** diff 를 보이고 머지 방법을 물어라.

```bash
mkdir -p scripts goals guidelines cycles docs/findings docs prompts

# 2.1 오케스트레이터 (goal-agnostic — 그대로 복사)
cp "$KIT/scripts/_gate-cache.sh"        scripts/
cp "$KIT/scripts/completion-check.sh"   scripts/
cp "$KIT/scripts/active-check.sh"       scripts/
cp "$KIT/scripts/next-task.sh"          scripts/
cp "$KIT/scripts/check-gate-rigor.sh"   scripts/
cp "$KIT/scripts/diagnose.sh"           scripts/
cp "$KIT/scripts/update-state.sh"       scripts/

# 2.2 규약 / 설계 / 가이드
cp "$KIT/guidelines/goal-iteration.md"  guidelines/
cp "$KIT/docs/goal-design.md"           docs/
cp "$KIT/goals/AGENTS.md"               goals/
cp "$KIT/cycles/AGENTS.md"              cycles/
cp "$KIT/findings/AGENTS.md"            docs/findings/
cp "$KIT/prompts/cycle-generate.md"     prompts/

# 2.3 goal 트리오 (스택별 수정 필요 — §4)
cp "$KIT/goals/_meta.md"                goals/
cp "$KIT/goals/_meta.gates.sh"          goals/
cp "$KIT/goals/_meta.next-task.sh"      goals/
cp "$KIT/goals/0-example.md"            goals/
cp "$KIT/goals/0-example.gates.sh"      goals/
cp "$KIT/goals/0-example.next-task.sh"  goals/

# 2.4 (선택) 예제 finding/cycle — 형태 참고용. 원치 않으면 생략.
cp "$KIT/findings/EXAMPLE.md"           docs/findings/   # 선택
cp "$KIT/cycles/EXAMPLE.md"             cycles/          # 선택

# 2.5 실행 권한
chmod +x scripts/*.sh goals/*.gates.sh goals/*.next-task.sh
```

복사 후 체크:

```bash
ls scripts/{_gate-cache,completion-check,active-check,next-task,check-gate-rigor,diagnose,update-state}.sh
ls goals/_meta.md goals/0-example.md guidelines/goal-iteration.md docs/goal-design.md
ls goals/AGENTS.md cycles/AGENTS.md docs/findings/AGENTS.md
```

---

## 3. 환경 설정 (gitignore)

`.state/` 는 런타임 휘발성 상태(active-goal 포인터 + gate 캐시)다. 커밋 대상이 아니다. `.gitignore` 에 없으면 추가:

```bash
grep -qxF '.state/' .gitignore 2>/dev/null || echo '.state/' >> .gitignore
```

---

## 4. 프로젝트 스택에 맞게 적응 (가장 중요)

오케스트레이터는 그대로 동작하지만, **무엇을 검사할지**는 프로젝트마다 다르다. 두 군데를 채운다.

### 4.1 `_meta` — cross-cutting 검사 (lint / typecheck / test / build)

`goals/_meta.gates.sh` 를 열고 두 배열을 타겟 스택에 맞게 채운다. 프로젝트의 `package.json` / `Makefile` / `pyproject.toml` / `Cargo.toml` 등을 읽어 실제 명령을 파악한 뒤 작성한다.

- `META_CHECKS=( "label::command" … )` — 각 명령은 레포 루트에서 실행되고 실패 시 non-zero 여야 한다. 예:
  - Node/pnpm: `"typecheck::pnpm exec tsc --noEmit"`, `"lint::pnpm exec eslint . --max-warnings 0"`, `"test::pnpm exec vitest run --coverage"`, `"build::pnpm -r build"`
  - Python: `"lint::ruff check ."`, `"typecheck::mypy ."`, `"test::pytest -q"`
  - Rust: `"build::cargo build --locked"`, `"test::cargo test"`
  - Go: `"vet::go vet ./..."`, `"test::go test ./..."`
- `GATE_INPUTS=( … )` — 코드/설정이 바뀌면 캐시가 무효화되도록 소스 디렉토리와 설정 파일을 추가한다 (예: `src tests package.json` 또는 `src tests pyproject.toml`). 끝의 세 self-reference(`goals/_meta.gates.sh`, `goals/_meta.md`, `scripts/_gate-cache.sh`)는 남겨둔다.

`META_CHECKS` 를 비워두면 `_meta` 는 "no checks configured" 경고와 함께 vacuously 통과한다 — 반드시 채워라.

`goals/_meta.md` 본문의 "The Goal" 항목도 실제 검사에 맞게 다듬는다 (universal claim 유지 — gate 의 `for` 루프가 그걸 enumerate 한다).

### 4.2 goal 0 — 첫 진짜 미션

`goals/0-example.*` 는 **학습용 예제**(runnable 스크립트의 shebang 검사)다. 패턴을 이해했으면 프로젝트의 실제 첫 미션으로 교체한다:

1. 프로젝트의 spec / README / 이슈를 읽어 "이 단계에서 done 이란?" 을 정의한다.
2. `goals/0-<name>.md` 작성 — `## Mission`, `## Completion Conditions` (universal claim), `## Sources Of Truth` (enumeration 명령), `## Verification`. 제목 바로 아래에 `guidelines/goal-iteration.md` 포인터 한 줄.
3. `goals/0-<name>.gates.sh` 작성 — `_gate-cache.sh` source, `GATE_INPUTS` 선언, **universal claim 을 source-of-truth enumeration 으로 검증**, 끝에 `check-gate-rigor.sh "$ROOT/goals/0-<name>.md"` self-check. (`0-example.gates.sh` 가 레퍼런스.)
4. `goals/0-<name>.next-task.sh` 작성 — gate pass/fail 분기로 "다음 할 일" 출력 ("무엇"만, "어떻게"는 빼라).
5. `chmod +x` 후 `goals/0-example.*` 삭제.

> goal 0 작성을 위해 사용자에게 이 프로젝트의 "첫 출하 기준"을 짧게 물어도 된다. 여러 미션이 필요하면 `1-<name>`, `2-<name>` … 으로 쌓는다 — 번호순으로 active 가 흐른다.

---

## 5. 검증 (철저히)

설치가 실제로 동작하는지 확인한다. 모두 통과해야 한다.

```bash
# 5.1 rigor 정규식 self-test
bash scripts/check-gate-rigor.sh --self-test        # ✓ 기대

# 5.2 전체 체인 — 첫 실패 goal 을 .state/active-goal 에 기록
bash scripts/completion-check.sh; echo "exit=$?"
cat .state/active-goal                              # 활성 goal 경로 또는 ALL_DONE

# 5.3 진단 + 다음 액션
bash scripts/diagnose.sh

# 5.4 active-goal 루프 (active 가 green 이면 자동으로 completion-check 로 전진)
bash scripts/active-check.sh; echo "exit=$?"

# 5.5 캐시 동작 — 두 번째 completion-check 는 [cache hit] 가 보여야 함
bash scripts/completion-check.sh | grep -i 'cache hit' || echo "(첫 실행 후 재실행 시 cache hit 확인)"

# 5.6 상태 파일 생성
bash scripts/update-state.sh
ls docs/state/                                      # progress.md next-task.md blockers.md learnings.md
```

기대 동작:

- `_meta` 를 제대로 채웠고 프로젝트 검사가 통과하면 + goal 0 도 green 이면 → `.state/active-goal == ALL_DONE`.
- goal 0 이 아직 미완이면 → `.state/active-goal` 이 `goals/0-<name>.md`, `diagnose.sh` 의 "Recommended Next Action" 이 그 goal 의 next-task hint 를 출력.
- 둘 중 무엇이든 **에러 없이** 라우팅되면 설치 성공이다.

실패하면 어느 gate 가 빨간지 출력으로 파악하고 `_meta`/goal 0 정의를 고친다 (오케스트레이터 자체를 고치지 말 것 — 거의 항상 검사 정의 문제다).

---

## 6. 정리 + 커밋

```bash
rm -rf "$CC_SYSTEM"
```

타겟 프로젝트 README 에 한 단락 추가: 이 레포가 FCG 하네스를 쓰며, 루프는 `bash scripts/diagnose.sh` 로 시작하고 `bash scripts/completion-check.sh` 가 전체 체인을 검증한다는 것, 그리고 새 작업은 `cycles/` 문서를 `prompts/cycle-generate.md` 로 만들어 루핑 에이전트에 넘긴다는 것.

커밋 제안:

```
chore(harness): findings-cycles-goals 하네스 이식

- scripts/{completion-check,active-check,next-task,check-gate-rigor,diagnose,update-state,_gate-cache}.sh
- goals/{_meta,0-<name>}.{md,gates.sh,next-task.sh}
- guidelines/goal-iteration.md, docs/goal-design.md
- goals/AGENTS.md, cycles/AGENTS.md, docs/findings/AGENTS.md
- prompts/cycle-generate.md
- .gitignore: .state/
- _meta 검사를 <스택> 명령으로 적응
```

---

## 7. 이후 사용 흐름

1. **iteration**: `bash scripts/diagnose.sh` → active goal 의 next-task hint 대로 TDD → `bash scripts/active-check.sh`. (`guidelines/goal-iteration.md` 의 Phase 1–7.)
2. **부채 발견**: out-of-scope 면 `docs/findings/<UTC>-<slug>.md` 에 큐잉 (`docs/findings/AGENTS.md` 규약).
3. **무인 세션**: `prompts/cycle-generate.md` 로 `cycles/<YYMMDD>-NN-<slug>.md` 작성 → 루핑 에이전트에 "이 cycle 을 모두 완수할 때까지 작업해줘" 로 전달.
4. **새 미션**: `goals/<n>-<name>.*` 세 파일 추가 → 다음 completion-check 가 active 로 잡는다.

---

## 자주 하는 실수 (하지 말 것)

- ❌ `_meta` 의 `META_CHECKS` 를 비워둔 채 끝내기 — lint/test 가 아무것도 검증하지 않고 vacuously 통과한다.
- ❌ universal claim ("every X") 을 쓰면서 gate 에 `for`/`while`/`find` 없이 한 예시만 검사 — `check-gate-rigor.sh` 가 막는다. enumerate 하라.
- ❌ 테스트/typecheck/coverage 가 더 정확히 잡는 것을 gate 에서 grep — `docs/goal-design.md §1.5` 위반. gate 는 negative-universal / source-of-truth enumeration / 구조 앵커만.
- ❌ `.state/` 를 gitignore 안 하기 — 휘발성 캐시/포인터가 커밋되어 머지 충돌을 일으킨다.
- ❌ `goals/0-example.*` 를 안 지우고 방치 — 진짜 미션과 섞여 active 라우팅이 헷갈린다.
- ❌ 오케스트레이터 스크립트(`completion-check.sh` 등)를 프로젝트 사정에 맞춘다며 수정 — 거의 항상 `_meta`/goal 정의를 고쳐야 할 문제다. 스크립트는 goal-agnostic 으로 유지.
- ❌ `chmod +x` 누락 — completion-check 가 gate 스크립트를 launch 하지 못한다.
- ❌ 하네스 자산을 개선한 뒤 upstream cc-system 으로 PR 안 보내기 — 개선이 다음 프로젝트로 전파되지 않는다.
