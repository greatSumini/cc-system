# cc-system

Claude Code 용 skill · sub-agent · harness 자산 모음. 프로젝트마다 필요한 조각만 골라 이식한다.

## 디렉토리

```
.claude/
  skills/
    persuasion-review/   잠재고객 페르소나 시뮬 (설득력 검토)
    ideation/            페르소나 시뮬 결과로 다음 요구사항 1개를 도출 + tech-critic-lead 결재
    plan-and-build/      task/phase 분해 → run-phases.py 실행까지 자동화
    commit/              대화 컨텍스트 기반 정교한 git commit/push
    skill-creator/       skill 생성 도우미
    slash-command-creator/
    subagent-creator/
    hook-creator/
    gmail/ · google-calendar/ · youtube-collector/
  agents/
    tech-critic-lead.md   "기능은 비용" 전제의 비판적 CTO 서브에이전트
    brand-logo-finder.md

scripts/
  run-server.py          사람 개입 0회 자율 주행 루프 (ideation→commit→build→check→rollback)
  run-phases.py          plan-and-build 이 만든 task/phase 를 순차 실행
  _utils.py

prompts/
  task-create.md         plan-and-build 이 따르는 task/phase 파일 규격

prompt/
  install-persuasion-review.md   ← persuasion-review 를 타겟 프로젝트에 이식하는 프롬프트
  crystalize-prompt.md
  design-pipeline.md

docs/
  cc/                    Claude Code hook / slash-command / sub-agent 참고 문서
```

## 이식

### persuasion-review 단일 이식

[`prompt/install-persuasion-review.md`](prompt/install-persuasion-review.md) 의 내용을 타겟 프로젝트에서 연 Claude Code 세션에 그대로 붙여넣는다. Claude 가 이 레포를 얕은 clone 해서 필요한 파일을 복사하고, 프로젝트의 기동 방식에 맞춘 `ux_probe_adapter.py` 까지 써준다.

### 자율 주행 하네스 전체 이식

자율 루프(`scripts/run-server.py`)까지 쓰려면 추가로 아래를 함께 이식:

- `.claude/skills/ideation/`, `.claude/skills/plan-and-build/`, `.claude/skills/commit/`
- `.claude/agents/tech-critic-lead.md`
- `scripts/run-server.py`, `scripts/run-phases.py`, `scripts/_utils.py`
- `prompts/task-create.md`
- 프로젝트 쪽에 `docs/{mission,spec,testing,user-intervention}.md`, `persuasion-data/personas/<1명 이상>`, `persuasion-data/ux_probe_adapter.py` 준비

`HARNESS_HEADLESS=1` 이 무인 모드 시그널이다. (레거시로 `BET_HEADLESS` 도 fallback 으로 수용됨 — 추후 제거 예정.)
