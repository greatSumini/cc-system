---
cycle: 260526-01
title: (example) overnight findings sweep
authored_at: 2026-05-26T01:03:39+09:00
started_at:
completed_at:
status: draft
---

# 260526-01 — (example) overnight findings sweep

> **This is a template/example cycle.** Copy the shape, not the content.
> Real cycles are named `cycles/<YYMMDD>-<NN>-<slug>.md`. Author yours with
> `prompts/cycle-generate.md` and delete this file.

**목표**: 2026-05-26 시점 `docs/findings/` 의 미해결(`false`) + 부분
해결(`partial`) finding 을 우선순위/의존성 순서대로 닫는다. 일부는 goal
promote, 대부분 직접 작업. 매 작업 단위 완료 시 commit + push.

이 문서를 에이전트에게 **무한 루프 모드**로 넘긴다:
`cycles/<this-file>.md 의 내용을 모두 완수할 때까지 작업해줘.`

**시작 상태**: chain GREEN (`.state/active-goal == ALL_DONE`), 최고 goal
번호 `<N>` → 다음 빈 번호 `<N+1>`. 작업 브랜치 `<branch>`.

---

## 루프 알고리즘

```
step 0 — 최초 1회: 이 문서 frontmatter 갱신 (started_at, status: running) → commit.

LOOP:
  step 1 — chain 상태:  bash scripts/completion-check.sh
    exit 0 (ALL_DONE)  → step 2
    else               → .state/active-goal 의 goal 을 TDD 로 GREEN (goal-iteration.md Phase 4)
                         → commit + push → step 1
  step 2 — finding 진행: target 리스트 첫 unresolved 선택
    없음               → TERMINATE
    있음               → "Finding 처리 절차" → frontmatter 갱신 → commit + push → step 1
```

종료 조건 (셋 다): (1) 모든 in-scope target 이 `resolved: true` 또는 명시
`partial`, (2) `completion-check.sh` exit 0, (3) `git status` clean +
push 완료. 종료 시 frontmatter `completed_at`/`status` 갱신 +
`learnings.md` 한 줄.

**막혀도 종료하지 마라.** stuck → blocker 기록 → 다음 target.

---

## Target findings (실행 순서)

### Tier 1 — 높은 가치, 먼저

1. `docs/findings/<UTC>-login-rate-limit.md` (P1) — `/login` rate-limit.
   직접 작업. Acceptance signal: `tests/e2e/login-rate-limit.test.ts` 가
   `429` 를 검증.

### Tier 2 — 깊은 안전 큐 (밤을 채움)

2. `docs/findings/<UTC>-<slug>.md` (partial, P2) — per-file 마이그레이션
   같은 안전한 무한 필러. 닫은 파일 수를 status_notes 에 카운트.

---

## Reference snapshots — 작업 대상 아님 (force-close 금지)

`kind: snapshot`/`append-only-log` finding (감사·perf 로그) 은 resolve
대상이 아니다. 자식 work item 으로만 닫는다.

## Out of scope

- 대형 구조 리팩터 (반쯤 하다 두면 chain 이 깨짐) — dedicated cycle.
- 설계 결정/유료 에이전트 필요 항목 — 발견해도 등록만.

## Finding 처리 절차

각 finding: 읽기 → promote/direct 판단 → RED/GREEN/REFACTOR → Acceptance
signal 검증 → frontmatter (`resolved: true` + `resolved_by`) + 본문 끝
`## Resolution` → commit + push.

## Forbidden actions (HARD STOP — blocker 기록 후 다음으로)

1. Prior goal invariant 무단 약화 (§5 케이스 미준수).
2. Hook 우회 (`--no-verify` 등).
3. 테스트/lint 비활성화 (`.skip`, `eslint-disable` 추가).
4. Coverage threshold 인하.
5. 3 사이클 무진전 → blocker → 다음 target.
6. Destructive git (`push --force`, `reset --hard`).
7. `.env`/credential/대용량 산출물 커밋.

## Commit / push 프로토콜

TDD 각 phase 한 커밋. finding 완료 후 마무리 커밋 + push. 브랜치 유지.

## 검증 — 진짜 끝났는지

```bash
bash scripts/completion-check.sh; echo "exit: $?"   # 0
git status --short                                  # 비어야 함
git log @{u}..HEAD --oneline                        # 비어야 함
```

TERMINATE.
