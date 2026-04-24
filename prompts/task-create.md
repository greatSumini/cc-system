# Task Creation Prompt

이 프롬프트는 구현 계획이 컨텍스트에 존재하는 상태에서, 직렬 phase 실행을 위한 태스크 파일들을 생성한다.

---

## 지시사항

컨텍스트에 존재하는 구현 계획(phase 목록, 각 phase의 작업 내용, 의존성, AC 등)을 기반으로 아래 산출물을 생성하라.

### 0. task ID와 이름 결정

- 사용자가 지정하지 않았다면, `/tasks/index.json`의 `tasks` 배열에서 마지막 `id + 1`을 새 ID로 사용.
- 이름은 kebab-case slug. 해당 task의 핵심 목적을 한 단어~두 단어로 표현.
- 디렉토리명: `{id}-{name}` (예: `1-auth`, `2-billing`)

### 1. `/tasks/index.json` (top-level task index)

이미 존재하면 `tasks` 배열에 새 항목을 추가한다. 없으면 새로 생성.

```json
{
  "tasks": [
    {
      "id": 0,
      "name": "mvp",
      "dir": "0-mvp",
      "status": "completed",
      "created_at": "...",
      "completed_at": "..."
    },
    {
      "id": 1,
      "name": "<task-name>",
      "dir": "1-<task-name>",
      "status": "pending",
      "created_at": "..."
    }
  ]
}
```

- `status`는 모든 phase가 완료되면 `"completed"`, 하나라도 실패하면 `"error"`, 그 외 `"pending"`.
- 타임스탬프: `created_at`은 task 생성 시, `completed_at`은 전체 완료 시, `failed_at`은 실패 시. ISO 8601 형식 (예: `2026-03-19T01:55:23+0900`).
- `created_at`만 생성 시 기록. `completed_at`, `failed_at`은 `scripts/run-phases.py`가 자동 기록.

### 2. `/tasks/{id}-{name}/index.json` (task-level phase index)

```json
{
  "project": "<프로젝트명>",
  "task": "<task-name>",
  "prompt": "<사용자가 이 task 논의를 시작할 때 입력한 최초 프롬프트 원문>",
  "totalPhases": <N>,
  "created_at": "...",
  "phases": [
    { "phase": 0, "name": "<phase-slug>", "status": "pending" },
    ...
  ]
}
```

- `prompt`: 사용자가 해당 task 논의를 요청할 때 최초로 입력한 프롬프트 원문. task의 맥락과 의도를 기록하기 위한 필드.
- `name`은 kebab-case slug. 해당 phase의 핵심 모듈/작업을 한 단어~두 단어로 표현.
- 모든 phase의 초기 status는 `"pending"`.
- 타임스탬프: task-level `created_at`은 생성 시 기록. `completed_at`은 전체 완료 시 `scripts/run-phases.py`가 기록.
- phase-level 타임스탬프(`started_at`, `completed_at`, `failed_at`)는 `scripts/run-phases.py`가 실행 시 자동 기록. 생성 시 넣지 않는다.

### 3. `/tasks/{id}-{name}/docs-diff.md` (문서 변경 기록)

Phase 0 완료 후 `scripts/run-phases.py`가 `scripts/gen-docs-diff.py`를 자동 호출하여 생성한다.
Phase 0 시작 전 HEAD를 baseline으로 기록하고, Phase 0 완료 후 `git diff {baseline} -- docs/`를 실행하여 실제 diff를 추출한다.

**에이전트가 직접 작성하지 않는다.** Phase 0는 문서 업데이트만 수행하면 된다.

생성되는 형식:

```markdown
# docs-diff: {task-name}

Baseline: `a1b2c3d`

## `docs/spec.md`

\`\`\`diff
@@ -45,6 +45,18 @@

### `cc-company agent list`

+### `cc-company run <agent-name>`
+...
\`\`\`
```

- 이후 구현 phase들의 "사전 준비" 섹션에서 이 파일을 참조하도록 한다.

### 4. `/tasks/{id}-{name}/phase{N}.md` (각 phase마다 1개)

각 파일은 **독립적인 claude session이 이 파일 하나만 보고 작업을 완수할 수 있을 정도로** 자기완결적이어야 한다.
phase 실행은 별도의 claude session이 진행한다는 점을 명심하라. 우리의 의도가 정확히 반영될 수 있도록 구체적이어야한다.

반드시 아래 구조를 따르라:

```markdown
# Phase {N}: {Phase 이름}

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 완전히 이해하라:

- {관련 문서 경로 나열 — spec, architecture, ADR 등}
- `/tasks/{id}-{name}/docs-diff.md` (이번 task의 문서 변경 기록)

그리고 이전 phase의 작업물을 반드시 확인하라:

- {이전 phase에서 생성/수정된 파일 경로 나열}

이전 phase에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업 내용

{구체적인 구현 지시. 파일 경로, 클래스/함수 시그니처, 로직 설명을 포함.
코드 스니펫은 인터페이스/시그니처 수준만 제시하고, 구현체는 에이전트에게 맡겨라.
단, 설계 의도에서 벗어나면 안 되는 핵심 규칙은 명확히 박아넣어라.}

## Acceptance Criteria

{구체적인 검증 커맨드. 예:}
\`\`\`bash
npm run build # 컴파일 에러 없음
npm test # 모든 테스트 통과
\`\`\`

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/{id}-{name}/index.json`의 phase {N} status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- {이 phase에서 하지 말아야 할 것, 엣지 케이스, 호환성 주의사항 등}
- 기존 테스트를 깨뜨리지 마라.
```

#### phase 파일 작성 원칙

1. **Phase 0는 문서 업데이트**: 첫 번째 phase는 반드시 관련 문서(spec, architecture, ADR 등)를 업데이트한다. `docs-diff.md`는 Phase 0 완료 후 `scripts/gen-docs-diff.py`가 자동 생성하므로, 에이전트가 직접 작성하지 않는다.
2. **자기완결성**: 각 phase 파일은 독립 session에서 실행된다. "이전 대화에서 논의한 바와 같이" 같은 참조 금지. 필요한 정보는 전부 파일 안에 적어라.
3. **사전 준비 필수**: 관련 문서 경로 + `docs-diff.md` + 이전 phase 산출물 경로를 명시. session이 코드를 읽고 맥락을 파악한 뒤 작업하도록 강제.
4. **시그니처 수준 지시**: 함수/클래스의 인터페이스만 제시. 내부 구현은 에이전트 재량. 단, 핵심 비즈니스 규칙(멱등성, 보안, 데이터 무결성 등)은 반드시 명시.
5. **AC는 실행 가능한 커맨드로**: "~가 동작해야 한다" 같은 추상적 서술 금지. `npm run build && npm test` 같은 실행 가능한 커맨드.
6. **scope 최소화**: 하나의 phase에서 하나의 레이어/모듈만 다룬다. 여러 모듈을 동시에 수정해야 하면 phase를 쪼개라.
7. **주의사항은 구체적으로**: "조심해라" 대신 "X를 하지 마라. 이유: Y" 형식.

### 5. `/scripts/run-phases.py` (runner script)

이미 존재하면 덮어쓰지 않는다. 없으면 아래 동작을 하는 Python 스크립트를 생성:

1. CLI 인자로 task 디렉토리명을 받는다 (예: `python3 scripts/run-phases.py 0-mvp`).
2. `tasks/{task-dir}/index.json`을 읽고, 다음 `"pending"` phase를 찾는다.
3. 해당 `phase{N}.md`의 내용을 읽어 공통 프리앰블과 합쳐 프롬프트를 구성한다.
   - **프롬프트에 파일 경로를 넘기지 말고, 파일 내용 자체를 프롬프트에 임베딩한다.**
4. `claude -p --dangerously-skip-permissions --output-format json "{prompt}"` 로 실행.
5. stdout/stderr를 `tasks/{task-dir}/phase{N}-output.json`에 저장.
6. 실행 후 `{task-dir}/index.json`을 다시 읽어 status 확인:
   - `"completed"` → 다음 phase로 진행
   - `"error"` → 에러 메시지 출력 후 종료
   - `"pending"` (변경 안 됨) → error로 마킹 후 종료
7. 모든 phase가 완료되면 `/tasks/index.json`의 해당 task status를 `"completed"`로 업데이트 후 종료.

공통 프리앰블:

```
당신은 {프로젝트명} 프로젝트의 개발자입니다. 아래 phase의 작업을 수행하세요.

중요한 규칙:
1. 작업 전에 반드시 문서를 읽고 전체 설계를 이해하세요.
2. 이전 phase에서 작성된 코드를 꼼꼼히 읽고, 기존 코드와의 일관성을 유지하세요.
3. AC 검증을 직접 수행하고, 통과/실패에 따라 /tasks/{task-dir}/index.json을 업데이트하세요.
4. 불필요한 파일이나 코드를 추가하지 마세요. phase에 명시된 것만 작업하세요.
5. 기존 테스트를 깨뜨리지 마세요.
6. AC 통과 후, index.json 업데이트까지 완료했다면, 모든 변경사항을 아래 형식으로 커밋하세요:
   feat({task-name}): phase {N} — {phase-name}

아래는 이번 phase의 상세 내용입니다:
```

---

## 실행 예시

```bash
# 태스크 생성 후
python3 scripts/run-phases.py 0-mvp

# 특정 phase에서 에러 발생 시: task의 index.json 수정 후 재실행
# → error phase의 status를 "pending"으로 변경
python3 scripts/run-phases.py 0-mvp
```

### scripts/run-phases.py 자동 동작

- `feat-{task-name}` 브랜치를 자동 생성/체크아웃 (이미 존재하면 resume)
- 각 phase 완료 후 2단계 커밋:
  1. **Claude fallback 커밋**: `feat({task-name}): phase {N} — {phase-name}` — Claude가 직접 커밋하지 않은 코드 변경이 있을 때만 수행
  2. **Runner housekeeping 커밋**: `chore({task-name}): phase {N} output + timestamps` — phase-output.json 저장 및 index.json timestamp 업데이트를 별도 커밋
  - 커밋 메시지 템플릿은 `scripts/run-phases.py`의 `COMMIT_MSG_TEMPLATE`, `RUNNER_COMMIT_MSG_TEMPLATE` 상수로 관리
- 스피너 + 진행상황 표시 (현재 phase / 전체 phase / 경과시간)
