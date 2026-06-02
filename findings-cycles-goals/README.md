# findings-cycles-goals (FCG) kit

[`vibemafiaclub/vooster`](https://github.com/vibemafiaclub/vooster) 가 쓰는
**autonomous build harness** 의 핵심 — findings → cycles → goals 3-자산
시스템 — 을 스택 중립적으로 추출한 이식 키트다. 루핑 에이전트(codex /
Claude)가 사람 개입 없이 매 iteration 동일한 루프를 돌며 미션을 완수하게
한다.

이식은 [`prompt/install-findings-cycles-goals.md`](../prompt/install-findings-cycles-goals.md)
프롬프트를 타겟 프로젝트의 Claude Code 세션에 붙여넣어 진행한다. 이 디렉토리는
그 프롬프트가 복사해갈 **원본 자산**이다.

## 3-자산 모델

| 자산                          | 무엇인가                                   | 검증        | 수명        |
| ----------------------------- | ------------------------------------------ | ----------- | ----------- |
| **findings** (`docs/findings/`) | out-of-scope 발견을 잃지 않는 부채/통찰 **큐** | 없음        | close 까지  |
| **cycles** (`cycles/`)        | 무한 루프에 넘기는 한 세션 **프롬프트**       | 없음        | 영구 (이력) |
| **goals** (`goals/`)          | gate 로 검증되는 **영속 invariant** (세 파일/goal) | `.gates.sh` | 영구        |

흐름: iteration 중 발견한 부채는 **finding** 으로 큐잉 → 사람이 **cycle**
문서를 써서 루핑 에이전트에 전달 → 에이전트가 finding 들을 닫으며 일부를
**goal** 로 promote → goal harness 가 "완료" 를 기계 검증.

**리뷰도 finding 의 1급 출처다.** 에이전트가 설계·구현한 결과를 사람이
리뷰할 때, 목적은 "검증" 이 아니라 커뮤니케이션·상호학습이다 (회귀·계약
위반은 goal gate 가 이미 기계 검증한다). 리뷰 대화에서 나온 통찰·부채가
finding 으로 큐잉돼 다음 cycle/goal 로 환류할 때 루프가 닫힌다. 설계 근거는
`docs/goal-design.md` 의 "리뷰는 finding 을 낳는다" 참조.

## 디렉토리 → 타겟 레포 매핑

```
findings-cycles-goals/                     →  <target repo>
  scripts/                                 →  scripts/        (goal-agnostic 오케스트레이터)
    _gate-cache.sh
    completion-check.sh    active-check.sh
    next-task.sh           check-gate-rigor.sh
    diagnose.sh            update-state.sh
  guidelines/goal-iteration.md             →  guidelines/goal-iteration.md
  goals/                                   →  goals/          (미션 스택)
    AGENTS.md                                              (규약)
    _meta.{md,gates.sh,next-task.sh}                      (cross-cutting — 스택별 수정)
    0-example.{md,gates.sh,next-task.sh}                  (teaching 예제 — 교체/삭제)
  cycles/AGENTS.md  cycles/EXAMPLE.md       →  cycles/        (루프 드라이버 규약)
  findings/AGENTS.md  findings/EXAMPLE.md   →  docs/findings/ (큐 규약)
  docs/goal-design.md                       →  docs/goal-design.md  (설계 노트)
  prompts/cycle-generate.md                 →  prompts/cycle-generate.md (사이클 생성 메타 프롬프트)
```

`.state/` (active-goal 포인터 + gate 캐시) 는 런타임에 생기며 **gitignore**
대상이다.

## 오케스트레이터 한눈에

| 스크립트                | 역할                                                                        | 비용     |
| ----------------------- | --------------------------------------------------------------------------- | -------- |
| `diagnose.sh`           | 매 iter 첫 단계. git/active-goal/열린 finding/blocker read-only 출력         | sub-sec  |
| `next-task.sh`          | active goal 의 `next-task.sh` 로 dispatch (advisory hint)                    | sub-sec  |
| `active-check.sh`       | active goal gate + rigor sweep. green 이면 completion-check 로 exec          | ~5–30 s  |
| `completion-check.sh`   | 모든 goal gate 병렬 실행, 첫 실패를 `.state/active-goal` 에 기록              | ~1–3 분  |
| `check-gate-rigor.sh`   | 메타-검증: universal claim ↔ enumerating gate 일치                           | sub-sec  |
| `_gate-cache.sh`        | source-only. gate 결과를 input fingerprint 로 memoize (병렬 안전)            | —        |
| `update-state.sh`       | `docs/state/{progress,next-task}.md` 재생성                                  | sub-sec  |

## 환경변수

| Env                  | 의미                                                                  | 기본 |
| -------------------- | --------------------------------------------------------------------- | ---- |
| `GATES_CONCURRENCY`  | `completion-check.sh` 병렬 워커 수 (`0` → 시리얼)                      | 4    |
| `GATES_SKIP_DEEP`    | 외부/무거운 deep gate 스킵 (빠른 iteration). completion-check 가 기본 1 | 1    |
| `GATES_NO_CACHE`     | gate 캐시 우회                                                         | —    |
| `GATES_SKIP_META`    | `_meta` goal 을 sweep 에서 제외 (CI 가 이미 lint/test 돌릴 때)         | —    |

## 처음 읽을 문서 순서

1. `docs/goal-design.md` — 왜 이렇게 설계됐는가 (핵심 원칙 §1, §1.5, §5).
2. `guidelines/goal-iteration.md` — 한 iteration 을 어떻게 도는가.
3. 각 폴더의 `AGENTS.md` — findings / cycles / goals 규약.

## 출처

이 키트는 vooster 의 `scripts/`, `goals/`, `cycles/`, `docs/findings/`,
`guidelines/`, `docs/goal-design.md` 를 스택 중립적으로 일반화한 것이다.
프로젝트 고유 부분 (테스트 러너, enumeration source of truth, `_meta`
명령) 은 이식 시 타겟 스택에 맞게 채운다.
