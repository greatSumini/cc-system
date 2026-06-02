# Goal 시스템 설계 노트

이 레포는 codex / Claude 같은 루핑 에이전트가 자율적으로 빌드하도록
설계된 **autonomous build harness** 의 일부다. 사람이 직접 빌드하기보다
에이전트가 매 iteration 마다 동일한 루프를 돌리도록 디렉토리가
구조화돼 있다.

> **에이전트 작업 프로토콜**: 이 문서는 harness 의 **설계**를 설명한다.
> 한 iteration 안에서 무엇을 어떤 순서로 실행하는지 (Orient → Read Spec →
> Test Plan → TDD → Verify → Record → Commit), `docs/state/*` 를 어떻게
> 다루는지, gate 를 어떻게 설계하는지 같은 **운영 매뉴얼**은
> `guidelines/goal-iteration.md` 에 있다. goal 루프로 작업하는 에이전트는
> 그 파일을 먼저 읽어야 한다.

## 핵심 아이디어

- 미션은 `goals/` 아래의 **버전드 goal 스택**으로 표현된다.
- 각 goal 은 머신이 검증 가능한 **gate 들**의 집합이다.
- 가장 낮은 번호의 실패 goal 이 **active goal** 이 된다. 그 한 파일이
  모든 도구(`diagnose`, `next-task`)의 라우팅 신호다.
- 에이전트는 active goal 의 `next-task.sh` 출력에 따라 TDD 를 진행하고,
  `completion-check.sh` 가 다시 평가한다.

## 세 가지 자산: findings → cycles → goals

| 디렉토리         | 무엇인가                          | 검증     | 수명           |
| ---------------- | --------------------------------- | -------- | -------------- |
| `docs/findings/` | 부채/통찰 **큐** (out-of-scope 발견) | 없음     | promote/close 까지 |
| `cycles/`        | 무한 루프에 넘기는 **세션 프롬프트** | 없음     | 영구 (이력)    |
| `goals/`         | gate 로 검증되는 **영속 invariant** | `.gates.sh` | 영구           |

흐름: iteration 중 발견한 out-of-scope 부채는 `docs/findings/` 에 큐잉
된다. 사람이 `cycles/` 문서를 써서 루핑 에이전트에 넘기면, 에이전트가
finding 들을 우선순위대로 닫는다 — 일부는 `goals/` 로 promote 해 영속
invariant 로 만들고, 나머지는 직접 처리한다. 각 디렉토리의 상세 규약은
그 폴더의 `AGENTS.md` 가 단일 출처다.

### 리뷰는 finding 을 낳는다 (학습 루프를 닫는 출처)

에이전트가 설계·구현을 맡는 흐름에서 **리뷰의 목적은 "검증" 이 아니라
커뮤니케이션·상호학습**이다. 회귀·계약 위반의 기계 검증은 이미 `goals/` 의
gate 가 책임진다 (그래서 리뷰어가 정확성을 한 줄씩 재확인할 필요가 없다).
사람의 리뷰는 그 위에서 (1) 제3자가 이해 가능한 코드인지 점검하고,
(2) 질문·논의로 더 나은 의사결정을 함께 학습하며, (3) 그 변경을 인지한
사람을 1명 이상 늘린다 — 수정 *지시* 가 아니라 *질문* 이 기본 모드다.

그 리뷰 대화에서 나온 통찰·부채는 곧 **finding** 이다. 즉 리뷰는 iteration
중 발견과 **동등한 finding 의 1급 출처**다 (`docs/findings/AGENTS.md` 의
Lifecycle §Create 참조). review → finding → cycle/goal 로 환류할 때 비로소
루프가 닫힌다. 변경이 충분히 단순해 LGTM 가 자명하면 — gate 가 이미 green
이고 변경이 구조 invariant 를 건드리지 않으면 — 복잡도에 따라 리뷰 단계를
생략할 수 있다. 무엇을 검증하느냐가 아니라 **무엇을 함께 학습하느냐**가
리뷰를 둘지 말지를 가른다.

## 디렉토리 역할

### `goals/` — 미션 스택

각 goal 은 **세 파일 한 세트**:

| 파일                      | 역할                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `<n>-<name>.md`           | 미션 선언. "완료" 조건을 자연어로 기술 (universal claim 사용).                             |
| `<n>-<name>.gates.sh`     | 그 조건을 기계적으로 검증. **goal text 가 "every X" 면 gate 는 source-of-truth 에서 X 를 enumerate** 해야 함. |
| `<n>-<name>.next-task.sh` | 워크플로우 state (파일 존재, 단계 진행도) 를 보고 다음 액션 hint 출력 (advisory — 강제 아님). |

`_meta` 는 번호 없는 특수 set 으로, 모든 goal 에 공통인 cross-cutting
universal claim (lint / typecheck / test+coverage / build) 을 한 곳에
모은다. `completion-check.sh` 가 이를 가장 먼저 launch 한다.

### `scripts/` — goal-agnostic 하네스

| 파일                  | 역할                                                                                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| `diagnose.sh`         | 매 iteration 첫 단계. git 상태, active goal, 열린 finding, blocker 를 한 번에 출력 (read-only).        |
| `completion-check.sh` | goal 들을 번호순/병렬로 돌며 각 `<n>-*.gates.sh` 실행. **첫 실패 goal 을 `.state/active-goal` 에 기록**. |
| `active-check.sh`     | active goal 의 gate + rigor sweep 만 (~5–30 s). green 이면 completion-check 로 exec 해 포인터 전진.    |
| `next-task.sh`        | `.state/active-goal` 읽고 해당 goal 의 `next-task.sh` 로 dispatch.                                     |
| `update-state.sh`     | `docs/state/progress.md`, `next-task.md` 를 git + goal 상태로 재생성.                                  |
| `check-gate-rigor.sh` | 메타-검증: universal claim ↔ enumerating gate 일치 여부.                                               |
| `_gate-cache.sh`      | source-only 헬퍼. gate 결과를 input 내용 fingerprint 로 memoize.                                       |

### `.state/` — 하네스의 휘발성 상태 (gitignore)

- `active-goal` — 첫 실패 goal 경로, 또는 `ALL_DONE`.
- `gate-cache/` — goal 별 input fingerprint.

### `docs/state/` — 에이전트의 스크래치패드

- `progress.md`, `next-task.md` — `update-state.sh` 가 자동 생성 (손대지 말 것).
- `blockers.md`, `learnings.md` — append-only.

## 한 iteration 의 흐름

회귀 감지를 세 단계로 나눈 구조다. iteration 중엔 활성 goal 만 빠르게 검사
(~5–30 s), 커밋할 땐 staged 파일의 impact set 만, 푸시/CI/명시적 verify 에서
전체 chain 풀 sweep (~1–3 분) 을 돈다.

```
bash scripts/diagnose.sh              # cheap: .state/active-goal 만 읽고 표시
   └─ next-task.sh
        └─ .state/active-goal 읽음
        └─ goals/<active>.next-task.sh exec → "다음 할 일" 출력

# 에이전트가 출력대로 RED 테스트 → 커밋 → GREEN 코드 → 커밋 (TDD 룰)

bash scripts/update-state.sh          # docs/state/* 갱신
bash scripts/active-check.sh          # 활성 goal 만 검사 + rigor sweep
   └─ rigor 실패 → exit 1 (의미 drift)
   └─ 활성 goal 아직 fail → exit 1, .state/active-goal 유지
   └─ 활성 goal pass → 자동으로 completion-check.sh 로 exec
        └─ 다음 active goal 결정 + 모든 prior goal 회귀 점검

# 푸시/verify 경계
git push           # optional pre-push hook → completion-check.sh
```

비용 모델:

| 명령                  | 범위                      | 비용                  | 호출 시점          |
| --------------------- | ------------------------- | --------------------- | ------------------ |
| `diagnose.sh`         | state 표시만              | sub-sec               | 매 iter 시작       |
| `active-check.sh`     | active goal + rigor sweep | ~5–30 s               | 매 iter 끝         |
| `completion-check.sh` | 모든 goal                 | ~1–3 분 (캐시 의존)   | pre-push, CI, 수동 |

설계 의도: 풀 sweep 이 매 iter 마다 돌면 N 이 커질수록 누적되어 사실상
불가능해진다. 그러나 prior goal 회귀 감지는 포기할 수 없다. 그래서 **자주
일어나는 사건(edit/iterate)** 에서는 가벼운 검사를, **공유/병합
경계(push/CI)** 에서 무거운 검사를 한다.

## 핵심 설계 원칙

### 1. Universal claim ↔ Universal gate

goal 텍스트가 "every entity is persisted" 라고 쓰면 gate 스크립트는 source
of truth 에서 모든 엔티티를 뽑아 루프를 돌려야 한다. 한 예시만 통과시키는
cheat 방지. `scripts/check-gate-rigor.sh` 가 이걸 메타-검증한다.

Sources of truth 와 그 iteration 명령 (스택별로 다름 — 예시):

| 대상       | 명령 (예)                                                  |
| ---------- | ---------------------------------------------------------- |
| 엔티티     | `grep '^model ' prisma/schema.prisma \| awk '{print $2}'`  |
| 유스케이스 | `find docs/usecases -name 'UC-*.md'`                       |
| 라우트     | `find src/http -name '*-routes.ts'`                        |
| 마이그레이션 | `find db/migrations -name '*.sql'`                       |

핵심은 **gate 가 파일시스템/스키마 같은 외부 진실원을 enumerate** 한다는
점이다 — 엔티티 이름을 gate 에 직접 박으면 narrow-gate cheat 를 재현하는
것이다.

### 1.5 Gates 가 _하지 말아야_ 할 것

§1 은 "universal claim 이면 enumerate 하라" 는 positive rule 이다. 그
반대도 똑같이 중요하다 — **다른 도구가 더 정확하게 잡는 invariant 를
gates.sh 가 grep 으로 흉내내지 마라.** 이 trap 에 빠지면 gates 가 구현
형태/심볼 이름에 강결합되어 부풀어오르고, benign refactor 에서 spurious
fail 하며, 정작 보장은 약하다.

gates.sh 가 검사해서는 안 되는 것:

| 안 좋은 gate 패턴                            | 더 적절한 도구           |
| -------------------------------------------- | ------------------------ |
| 함수 본문이 특정 심볼/헬퍼를 호출하는지      | **테스트** (행위 검증)   |
| 타입 선언에 특정 필드가 있는지               | **typecheck**            |
| 테스트 파일에 특정 토큰/제목 문자열이 있는지 | **테스트 실행 (runner)** |
| 특정 경로에 테스트 파일이 존재하는지         | **coverage threshold**   |
| 마크다운 문서에 특정 헤딩/문장이 있는지      | **코드 리뷰**            |
| findings 파일에서 특정 bullet 이 제거됐는지  | **커밋 메시지 / PR**     |

gates.sh 가 _유일하게_ 책임지는 건 세 종류만 남는다:

1. **Rigor 메커니즘** — §1 의 universal claim ↔ enumeration 메타 체크
   (`check-gate-rigor.sh`).
2. **Negative universal invariant** — "codebase 어디에도 패턴 X 가 없다"
   같은 single grep. 행위 테스트는 한 경로만 검증하므로 이건 못 잡음.
3. **구조 앵커** — 후속 goal 이 routing 신호로 쓰는 문서/파일의 존재.

회의적 휴리스틱: **"이 invariant 가 깨지면 어떤 테스트가 빨갛게 되는가?"**
답이 있으면 gates 에서 빼라. 답이 없을 때만 gate 가 적절하다.

### 2. 첫 실패 goal = 작업 대상

`completion-check.sh` 가 goal 들을 번호순으로 돌면서 첫 실패만
`.state/active-goal` 에 쓰고, 이후 모든 도구가 그 한 파일을 신호로 사용.
새 goal 을 추가하면 자동으로 흐름이 거기로 흘러간다.

### 3. 자체 검사만 (회귀는 orchestrator 가 담당)

각 goal 의 `.gates.sh` 는 그 goal 의 **자체** invariant 만 검사한다 —
이전 goal 에 대한 회귀 검사는 `scripts/completion-check.sh` 가 단독으로
책임진다.

- `bash goals/3-foo.gates.sh` 를 단독 실행하면 goal 3 만 검사한다. goal
  0/1/2 가 깨졌는지는 모름.
- "전체 체인 green" 을 보려면 `bash scripts/completion-check.sh` 를
  돌린다. 모든 goal 의 gate 를 병렬로 띄우고 하나라도 fail 이면 첫 실패
  goal 을 `.state/active-goal` 에 기록.

이 분리의 이유:

1. **N² → N**. 각 goal 이 이전 goal 을 재귀 호출하면 nested 호출이
   폭발한다. orchestrator 가 단일 진입점이면 goal 당 정확히 1번 실행.
2. **병렬화 가능**. 각 goal 이 standalone 이므로 동시에 실행 가능.
   `GATES_CONCURRENCY=1` 로 시리얼 회귀.
3. **standalone 의미가 정직해진다**. "이 게이트가 통과하면 이 goal 이
   되는가" 만 검사. "전체 chain 이 healthy 한가" 는 별개 도구가 답한다.

### 4. Orchestrator 가 rigor sweep 도 책임진다

`completion-check.sh` 는 parallel goal 워커를 띄우기 _전에_
`check-gate-rigor.sh --all` 을 한 번 돌린다. 어떤 goal 의 `.md` 본문에
새 universal claim 을 추가했는데 gate 캐시가 hit 한 채로 통과해버리는
leak 을 닫는다. 비용은 grep 한 번이라 사실상 공짜.

한계: rigor 가 잡는 건 "universal claim 이 있는데 iteration 이 아예
없음" 이다. `for` 루프 안에 `continue` 를 끼워 enumeration 을 우회하는
류의 미세 weakening 은 못 잡는다 — 코드 리뷰로 막아야 한다.

### 5. 이전 goal 의 게이트는 immutable 이 기본값

새 goal 이 기존 goal 의 invariant 를 깨뜨릴 수 있다 (기획 변경, 아키텍처
교체, 기능 제거). 무작정 약화·삭제하는 건 금지. 다음 세 케이스만 허용:

| 케이스                                                | 예                                  | 허용된 조치                                                                                  |
| ----------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------- |
| **(a) Retarget** — invariant 그대로, 경로/도구만 변경 | `src/` → `apps/api/src/` 이동       | 같은 goal 작업에서 prior `*.gates.sh` 경로 수정. prior `.md` 는 손대지 않음.                 |
| **(b) Loosen** — 검사 로직 자체가 바뀌어야 함         | "한 파일에 모든 모델" → "여러 파일" | 별도 scoped 커밋. prior `.md` 본문도 같은 커밋에서 수정해 universal claim 과 gate 를 재일치.  |
| **(c) Supersede** — invariant 가 의미 상실            | 프레임워크 교체로 부팅 게이트 무의미| 새 goal `.md` 에 **`## Supersedes`** 섹션으로 "goal N 의 gate X.Y 를 대체" 를 명시 후 교체.  |

금지:

- 커밋 메시지는 retarget 인데 enumeration 로직이 함께 약화되는 것.
- prior `.md` 본문은 그대로 두고 gate 만 느슨하게 만드는 것 (gate 가 더
  이상 `.md` 의 universal claim 을 enforce 하지 않게 됨).
- 새 goal `.md` 의 명시적 선언 없이 prior gate 파일을 삭제하는 것.

#### 케이스 (b) 의 특수형: "Enforcement 이전"

§1.5 에 따라 기존 gate 가 검사하던 항목이 사실은 테스트 / typecheck /
coverage 가 더 정확하게 잡고 있는 것으로 판명될 때 — 즉 gate 의 grep 을
제거해도 동일 invariant 가 다른 도구로 여전히 enforce 될 때 — 이건
형식상 (b) 지만 실질적으로 **invariant 약화가 아니라 enforcement
이전**이다. PR/커밋 메시지에 어떤 도구가 동일 invariant 를 enforce 하는지
명시하고, prior `.md` 본문도 같은 커밋에서 universal phrasing 을 정리해
`check-gate-rigor.sh` 가 일관되게 통과하도록 한다. goal 당 1 PR 원칙을
지켜 리뷰어가 약화 여부를 goal 단위로 확인할 수 있게 한다.

## Gate 실행 최적화

`scripts/completion-check.sh` 는 goal 당 정확히 1번 실행한다. 그 위에:

### 1. Per-goal cache

각 goal 의 gate 스크립트는 `scripts/_gate-cache.sh` 를 source 한다.

- 상단에 `GATE_INPUTS=(...)` 배열을 선언 — 그 게이트가 실제로 의존하는
  파일/디렉터리/글롭 목록.
- 캐시 key = `GATE_INPUTS` 로 결정되는 **파일 내용의 sha256 fingerprint**.
  디렉터리는 재귀 해시 (단 `node_modules`, `dist`, `.git`, `.state`,
  `target`, `__pycache__`, `.venv` 등은 prune). git 상태는 보지 않는다.
- 캐시 hit 이면 gate 즉시 `exit 0`.
- gate 성공 시 fingerprint 를 `.state/gate-cache/<goal-name>` 에 저장.
- **실패하면 캐시를 저장하지 않는다** — 다음 실행에서 반드시 재실행.
- `.state/` 는 `.gitignore` 라 커밋되지 않음.

핵심은 **병렬 작업 안전성**이다. 한 에이전트가 무관한 디렉터리를 편집해도
다른 goal 의 `GATE_INPUTS` 에 없으면 fingerprint 가 동일해 캐시가 hit 한다.
in-scope 파일이 바뀌면 (committed 든 아니든) 자동 invalidate.

수동 무효화:

```
rm -rf .state/gate-cache             # 전체 캐시 버스트
rm    .state/gate-cache/0-init       # 한 goal 만
GATES_NO_CACHE=1 bash goals/0-init.gates.sh   # 일회성 우회
```

### 2. Deep gate split

`completion-check.sh` 는 기본으로 `GATES_SKIP_DEEP=1` 을 설정한다. 반복
개발 체인은 working tree 내부의 deterministic code contract 만 다룬다.
Docker/배포 같은 외부 world-state gate 는 별도 cadence 로 실행한다.

- 스킵된 run 은 **캐시를 저장하지 않거나 별도 shallow key 를 쓴다** —
  partial run 은 authoritative 가 아니므로 다음 full run 을 강제한다.
- 병렬도: `GATES_CONCURRENCY=1` (시리얼) ~ `4` (자원 여유).

## 새 goal 추가하기

`.state/active-goal` 이 `ALL_DONE` 이면 모든 gate 가 통과한 상태. 새
작업이 필요하면 세 파일 세트를 추가한다:

```
goals/4-<name>.md            # 미션
goals/4-<name>.gates.sh      # 머신 검증 (chmod +x)
goals/4-<name>.next-task.sh  # 다음 액션 hint (chmod +x)
```

다음 `completion-check.sh` 실행이 이걸 active 로 잡는다.

### `.md` 본문 컨벤션

새 goal `.md` 의 맨 위(제목 바로 아래)에 한 줄 포인터를 둔다:

```
> 이 goal을 active로 잡은 에이전트는 먼저
> `guidelines/goal-iteration.md`를 읽어 iteration 프로토콜을 확인할 것.
```

active goal 파일은 종종 에이전트가 세션에서 처음 읽는 mission 텍스트다.
거기서 운영 매뉴얼로 한 hop 안에 도달하지 못하면 TDD 단계, state 파일
규칙, gate 설계 원칙을 모른 채 작업을 시작한다.

### 작성 전 self-audit

새 goal `.md` 를 쓰기 전에 원칙 5 의 케이스 분류를 미리 적용한다:

1. 이전 게이트의 **경로/도구**만 바꿔도 통과 가능한가? → 케이스 (a).
   같은 goal 작업에서 retarget.
2. 이전 게이트의 **검사 로직 자체**를 바꿔야 하는가? → 케이스 (b).
   `docs/findings/*.md` 에 큐잉하고 별도 PR 로 분리.
3. 이전 게이트의 **존재 이유 자체가 사라지는가**? → 케이스 (c). `.md`
   상단에 `## Supersedes` 섹션 작성 후에만 prior gate 수정.

이 self-audit 누락 시 `completion-check` 는 초록일 수 있어도 시스템의
의미가 조용히 무너진다 — gate 가 무엇을 약속하는지 아무도 보장하지 않게
된다.

## (선택) Presentation 작업 위임

UI/UX·카피·디자인 같은 presentation 작업은 codex 대신 Claude Code 에
headless 로 위임할 수 있다. goal 의 `.md` 가 `## Delegation` 섹션
(`owner: claude`, `cwd: <dir>`) 을 선언하면 그 goal 은 claude-owned 이
된다. 이때도 완료 검증 경계(gate green + 회귀 점검)는 일반 goal 과
동일하다 — 핸드오프 패킷이 곧 goal trio (`goal.md` 계약 +
`next-task.sh` 현재 step) 다. 위임 dispatcher 는 프로젝트마다 구현이
다르므로 이 번들에는 포함하지 않는다 (확장 포인트).
