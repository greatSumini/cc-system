# prompts/cycle-generate.md — 사이클 문서 작성 메타 프롬프트

> 이 파일은 새 `cycles/<YYMMDD>-<NN>-<slug>.md` 문서를 **작성하도록**
> Claude/codex 에게 시키는 메타 프롬프트다. 그대로 붙여넣거나 상황에 맞게
> 채워서 쓴다.

---

오케이, 난 이제 에이전트에게 goal 루프를 돌려놓고 자리를 비우고 싶다.

이 goal 루프 기능은 정해진 프롬프트를 **조건이 충족될 때까지 무한 반복**
실행한다. 잘 쓰기 위해 `cycles/` 폴더에 `YYMMDD-NN-<slug>.md` (예:
`cycles/260523-01-overnight-findings-closure.md`) 사이클 구동 문서를
만들어두고, 에이전트에게 `cycles/<file>.md 의 내용을 모두 완수할 때까지
작업해줘` 라고 지시할 것이다. 컨벤션은 `cycles/AGENTS.md` 를 따른다.
이를 위한 사이클 문서를 작성하자.

작성 전 반드시 읽을 것:

- `cycles/AGENTS.md` — 파일명/frontmatter/필수 섹션 규약 (단일 출처)
- `docs/goal-design.md` — harness 설계 (특히 §1.5 minimal gates, §5
  prior-gate 케이스 분류)
- `guidelines/goal-iteration.md` — iteration 프로토콜 (TDD, commit cadence)
- `docs/findings/AGENTS.md` — finding frontmatter schema
- 프로젝트의 커밋 규약

문서에 **반드시** 포함할 것:

1. **frontmatter** — `cycle` / `title` / `authored_at` / `started_at`
   (공란) / `completed_at` (공란) / `status: draft`.
2. **목표 + Target findings** — 닫을 finding 목록과 그들 간 순서/의존성.
   우선순위(P0→P2)와 가치/위험으로 tier 를 나눈다. 시작 상태(현재 chain
   green 여부, 최고 goal 번호, 작업 브랜치)를 명시.
3. **루프 알고리즘** — 대략:
   1. 미완료 goal 이 있는지 확인. 있으면 TDD 로 완수.
   2. 모든 goal 이 green 이면, target findings 중 미해결 첫 항목을
      처리(promote/delegate/direct).
   3. 모든 target 이 닫혔고 chain 이 green 이면 종료.
   - 무진전(3 사이클) 시 blocker 기록 후 다음 target — **조기 종료 금지**.
     promote 한 goal 이 막히면 promotion back-out 으로 chain 을 green 복귀.
4. **Finding 처리 절차** — 읽기 / promote·delegate·direct 판단 / 실행
   (TDD) / 검증(Acceptance signal) / 마무리(frontmatter + `## Resolution`).
5. **Goal 화 시 주의점** — minimal gates (rigor + negative universal +
   구조 앵커만), prior-gate 수정은 §5 케이스 (a)/(b)/(c) 준수.
6. **Out of scope** — 손대지 않을 항목 (대형 리팩터, 설계 결정 필요,
   유료/위험 작업). 발견해도 등록만.
7. **Reference snapshots** — `kind: snapshot`/`append-only-log` finding
   (force-close 금지).
8. **Forbidden actions** — HARD STOP 규칙 (hook 우회 금지, 테스트/lint
   비활성화 금지, coverage threshold 인하 금지, prior invariant 무단
   약화 금지, destructive git 금지, `.env`/credential 커밋 금지 등).
9. **Commit / push 프로토콜** — 브랜치, 메시지 포맷, push 실패 대응.
10. **종료 / 검증** — 진짜 끝났는지 확인하는 명령들 (target finding 상태
    점검 + `bash scripts/completion-check.sh` exit 0 + `git status` clean +
    push 완료). 종료 시 frontmatter `completed_at`/`status` 갱신 +
    `learnings.md` 한 줄.

모호하거나 논의할 점 있으면 작성 전에 제안해라.
