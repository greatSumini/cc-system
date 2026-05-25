# guidelines/goal-iteration.md — Goal-Looping Workflow

이 문서는 `docs/goal-design.md` 의 autonomous build harness 위에서 매
iteration 을 어떻게 돌리는지를 정리한다. 프로젝트의 일반 TDD / 스타일 /
커밋 위생 규약은 여전히 적용되며, 이 문서는 **goal 스택을 사용해 루프
작업을 할 때만** 추가로 참조한다.

> 커밋 메시지 포맷·시크릿 스캔·푸시 정책 등 일반 규약은 프로젝트의 커밋
> 규약 문서(예: `/commit` 스킬 또는 `CONTRIBUTING.md`)가 단일 출처다. 이
> 문서는 iteration 루프 안에서 **언제** 커밋하는지만 보강한다.

## Pre-flight (체크아웃의 첫 iteration)

(선택) commit 경계에서 회귀/시크릿을 막는 pre-commit 훅, push 전 전체
sweep 을 강제하는 pre-push 훅을 설치한다. 훅 스크립트는 프로젝트마다
다르므로 이 번들은 강제하지 않는다 — `completion-check.sh` 를 pre-push
에 연결하는 것을 권장한다.

## Workflow Per Iteration

### Phase 1: Orient (5–10%)

```
bash scripts/diagnose.sh
cat docs/state/next-task.md
```

파악할 것: 무엇이 끝났는지, 무엇이 진행 중인지, 현재 task 가 무엇인지.

### Phase 2: Read Spec (10–15%)

현재 task 의 spec 을 읽는다 (프로젝트의 spec 위치 — 예:
`docs/usecases/`, `docs/specs/`, 이슈 트래커). 식별할 것: 메인 성공
시나리오, 확장 시나리오, 선·후행 조건, 필요한 엔티티와 관계.

### Phase 3: Test Plan (5–10%)

테스트를 쓰기 전에 계획한다. `docs/state/test-plan.md` 에 append:
어떤 테스트가 생길지, 각 setup, 각 assertion.

`test-plan.md` 는 **living queue, 로그가 아니다**: 아직 GREEN 이 아닌
테스트만 담는다. Phase 4 GREEN 에서 해당 섹션을 삭제한다. 커밋된 테스트
파일이 source of truth 이므로 계획이 그걸 중복하면 안 된다.

### Phase 4: TDD Cycles (60–70%)

계획의 각 테스트마다:

1. **RED**: 테스트 작성 → 실패 확인 → 커밋 `red(<id>): <test-name>`.
2. **GREEN**: 최소 production 코드 → 그 테스트 통과 → **전체 테스트**
   통과 확인 → `test-plan.md` 에서 해당 섹션 삭제 → 커밋
   `green(<id>): <description>`.
3. **REFACTOR** (중복/불명확 있을 때만): 개선 → 매 변경 후 전체 테스트
   → 커밋 `refactor(<id>): <description>`.

각 phase 는 **한 커밋**으로 끝낸다. 커밋 메시지에 "and" 가 필요하면 step
이 너무 컸던 것 — 쪼개라. `green:`/`refactor:` 커밋에 실패하는 테스트를
섞지 마라.

### Phase 5: Verify (5–10%)

프로젝트의 테스트 러너 + 린트/타입체크를 돌린다 (이들은 보통 `_meta`
gate 가 enforce 한다). 실패하면 진행 전에 고친다.

### Phase 6: Record (5%)

```
bash scripts/update-state.sh
bash scripts/active-check.sh
```

`active-check.sh` 는 **active goal** 의 gate (~5–30 s) 와 rigor sweep 만
돌린다. active goal 이 green 이 되면 `completion-check.sh` 로 exec 해
포인터를 자동 전진시킨다. prior-goal 회귀는 iteration 레벨에서 검사하지
않는다 — staged impact 는 commit 훅이, 전체 sweep 은 pre-push/CI 가 잡는다.

중요한 걸 발견했으면 `docs/state/learnings.md` 에 한 줄 append.

`docs/state/*` 와 `learnings.md` 변경은 TDD 커밋과 섞지 말고 별도 커밋:
`chore(state): update progress for <id>`.

### Phase 7: Commit (경계 점검)

이 시점에서 작업 트리는 모두 커밋돼 있어야 한다. 빠진 변경이 있는지:

```
git status            # 깨끗해야 함
git log --oneline -5  # 이번 iteration 커밋들이 보여야 함
```

푸시 전: `git diff --cached` 로 시크릿/`.env`/대용량 산출물 미포함 확인,
`.gitignore` 누락 점검, 전체 회귀 필요 시 `bash scripts/completion-check.sh`.
통과하면 매 iteration 끝에 푸시 — 로컬 커밋을 쌓아두지 않는다.

## When You Are Stuck

한 테스트에 3 TDD 사이클 넘게 무진전이면:

1. 멈춘다.
2. `docs/state/blockers.md` 에 append: 하려던 것 / 시도한 것 / 무엇이
   잘못되는지.
3. `scripts/next-task.sh` 로 다른 task 로 이동.
4. fresh context 로 나중에 복귀.

## Working With State Files

`docs/state/*` 는 에이전트 관리 스크래치 공간이다.

- `progress.md` — `update-state.sh` 자동 생성. 손대지 말 것.
- `next-task.md` — 자동 생성. 한 줄 override 노트로만 덮어쓰기 가능.
- `blockers.md` — append-only. 해결된 blocker 는 삭제 대신
  `~~strikethrough~~`.
- `learnings.md` — append-only. 학습당 한 줄. 간결하게.

## Designing Gates

goal 파일은 조건 ("every entity is persisted") 을 선언하고,
`goals/<n>-<name>.gates.sh` 가 그 조건을 기계적으로 검증한다. 한 가지
규칙:

**goal text 가 universality 를 주장하면, gate 는 enumerate 해야 한다.**

- 나쁨: `curl /workspaces/foo` — 한 엔티티만 샘플. 한 예시만 만족시켜도
  통과.
- 좋음: `for m in $(grep '^model ' schema.prisma | awk '{print $2}'); do …`
  — source of truth 를 순회. 모든 모델이 다뤄져야 함.

gate 에 엔티티 이름을 타이핑하고 있다면 narrow-gate cheat 를 재현하는
것 — 멈추고 enumeration 으로 교체하라.

`scripts/check-gate-rigor.sh` 가 모든 goal 에 대해 돌며, markdown 에
"every X" 가 있는데 gate 에 `for`/`while`/`find`/`xargs` 가 없으면
flag 한다. "every" 언어를 지워서 이 검사를 무력화하지 마라 — gate 를
tighten 하거나 goal 을 정직하게 narrow 하라.

### Gates ≠ Convention Police

**다른 도구가 더 정확하게 잡는 invariant 를 gates 에서 grep 으로
흉내내지 마라.** 근거는 `docs/goal-design.md §1.5`. 회의적 휴리스틱:
**"이 invariant 가 깨지면 어떤 테스트가 빨갛게 되는가?"** 답이 있으면
gates 에서 빼라. 답이 없을 때만 gate 가 적절하다 — 보통 (a)
negative universal grep, (b) 외부 source-of-truth 의 enumeration, (c)
후속 goal routing 을 안내하는 문서/파일 존재, 셋 중 하나다.

## Designing next-task hints

`<n>-<name>.next-task.sh` 는 gates.sh 와 역할이 다르다:

| 측면          | `gates.sh`     | `next-task.sh`               |
| ------------- | -------------- | ---------------------------- |
| 역할          | invariant 강제 | 워크플로우 channeling (힌트) |
| 출력          | pass / fail    | text only                    |
| 무시 가능?    | 불가 (CI 차단) | 가능 (그냥 텍스트)           |
| 틀릴 때 비용  | iteration 차단 | stale hint (low)             |

### next-task 가 _해야_ 하는 것

**워크플로우 state detection** — agent 가 multi-iteration 환경에서 "지금
어느 단계인지" 를 외부에서 inspect 해 알려주는 메커니즘. t=0 (테스트 아직
없음) 에서는 next-task 가 _유일하게_ 작동하는 TDD 채널링 도구다. 허용되는
detection 신호: 파일 존재 (`compgen -G "tests/**/*X*"`), negative grep,
gates.sh 의 fail 여부. 이들은 **구현 형태가 아니라 진행 상태에 대한
명제**다.

### next-task 가 _하지 말아야_ 하는 것

**Mechanism prescription** — 어떻게 구현할지 처방. 정확한 함수명/테스트
제목/URL/파일 경로를 박지 마라. agent 가 더 좋은 대안을 찾았을 때 hint
가 막는다. 검증은 어차피 테스트/typecheck 가 한다. 회의적 휴리스틱:
**"이 단어를 hint 에 박으면, agent 가 더 좋은 대안을 찾았을 때 hint 를
같이 고쳐야 하나?"** 그렇다면 그 단어는 mechanism 이다 — 빼라.

## Active Goal Lookup

active goal 은 `<n>-<name>.gates.sh` 가 현재 실패하는, 가장 낮은 번호의
goal 이다. 찾는 법:

```
bash scripts/diagnose.sh        # active goal 경로 출력
cat .state/active-goal          # completion-check.sh 가 기록
```

active goal 파일을 매 iteration 전에 읽고, 그 forbidden-actions 를 지키며,
TDD 로 완료 조건을 만족시킨다. gate 가 통과하면 다음 goal 이 자동으로
active 가 된다.

### Single-goal vs. active-goal vs. full-chain

| 명령                               | 범위                      | 비용         | 시점                      |
| ---------------------------------- | ------------------------- | ------------ | ------------------------- |
| `bash goals/<n>-*.gates.sh`        | 한 goal                   | 초~분        | 한 goal 수동 점검         |
| `bash scripts/active-check.sh`     | active goal + rigor sweep | ~5–30 s      | 매 TDD 사이클 (Phase 6)   |
| `bash scripts/completion-check.sh` | 모든 goal                 | 1–3 분 (캐시)| pre-push, CI, 수동 sweep  |

단일 goal pass 만으로 TDD 사이클을 끝났다고 선언하지 마라 —
orchestrator 가 계약이다.

지금 `bash scripts/diagnose.sh` 를 돌리고 그것이 가리키는 active goal
파일을 읽어라.
