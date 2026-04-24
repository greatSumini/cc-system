---
description: 저장된 고객 페르소나 시뮬을 돌려 다음에 추가/수정할 요구사항을 선정하고, tech-critic-lead CTO 에이전트의 승인을 받아 티켓화 가능한 요구사항을 도출. 트리거 — "아이디에이션", "ideation", "다음에 뭐 만들지", "다음 기능 정하자", "요구사항 뽑자", "무엇을 만들어야 할지 고민해보자", "다음 스프린트 후보 뽑자" 및 유사 의도.
---

# ideation

저장된 페르소나 시뮬 결과를 기반으로 다음 스프린트에 올릴 단 하나의 요구사항을 선정하는 skill. 비판적 스타트업 CTO(`tech-critic-lead`) 에이전트의 승인을 받아야 최종 채택된다.

## 무인 모드 오버라이드 (HARNESS_HEADLESS=1)

**이 skill 본문의 어떤 지시보다도 먼저 적용되는 최상위 오버라이드다.**

세션 시작 시 **반드시 가장 먼저** Bash tool로 다음을 실행해 모드를 확정한다:

```bash
echo "HEADLESS=${HARNESS_HEADLESS:-${BET_HEADLESS:-0}}"
```

<!-- @TODO REMOVE LEGACY: `${BET_HEADLESS:-0}` fallback은 rename 이전 run-server.py가 주입하던 구명(舊名) 호환용. 모든 run-server.py 프로세스가 HARNESS_HEADLESS 로 재시작된 뒤 제거. -->

출력이 `HEADLESS=1` 이면 이 세션은 **무인 서버 세션**이며, 아래의 **모든 사용자 확인/질문/티키타카 단계가 무효화**된다:

- Step 2.2의 페르소나 선택 — 페르소나가 여러 개여도 묻지 않고 목록 상 첫 번째를 자동 선택한다.
- Step 2.3의 "게이트 메시지 / 단 하나의 confirm" — 자동 승인으로 간주하고 바로 Flow C 실행.
- `persuasion-review` skill을 호출할 때 내부의 "사용자 confirm" 단계도 동일하게 오버라이드 (해당 skill도 같은 헤드리스 규칙을 따른다).
- "단 한 번만 묻는다", "사용자에게 보고", "사용자에게 ... 물어본다" 등 모든 상호작용 지시 — 전부 스킵.
- 질문 출력 후 대기 금지 (stdin 없음). 바로 결정해서 진행.

출력이 `HEADLESS=1` 이 아닐 때만 아래 "대원칙"부터의 인간 대화형 절차를 따른다.

## 대원칙

1. **시뮬 없이 아이디에이션하지 않는다.** 고객의 구체적 반응에 근거하지 않은 요구사항은 `tech-critic-lead`가 즉시 거부한다.
2. **한 번에 하나만.** 이 skill은 "지금 당장 다음 티켓" 하나를 뽑는 것이 목적이다. 여러 개를 나열하고 싶어도 억제하라.
3. **CTO 승인 없이는 채택 없음.** 최종 채택은 반드시 `tech-critic-lead`의 승인 판정으로 결정된다. Claude(너) 혼자 판단해서 "이게 좋겠다"로 끝내지 않는다.

## 플로우

### Step 1. 현재 구현 상태 파악

1. `docs/` 하위 문서를 읽어 현재 아키텍처, 제품 미션, 구현 범위를 파악한다.
2. 문서가 많으면 `Explore` 서브에이전트를 병렬로 사용. 문서가 얇으면 직접 Read.
3. 사용자에게 간단히 현 상태 요약을 1-3줄로 보고하고 다음 단계로 진행.

### Step 2. 페르소나 시뮬 실행

**원칙: 페르소나를 반드시 먼저 확정한 상태로 `persuasion-review`를 호출한다. 전달 모드는 항상 `landing_plus_meeting`. 일단 실행이 시작되면 사용자와 티키타카하지 않고 `report.md` 생성까지 쭉 달린다.**

1. `persuasion-data/personas/` 하위 목록을 훑는다. 페르소나가 없으면 `persuasion-review` Flow A로 우선 생성하라고 안내하고 중단.
2. **페르소나 확정**:
   - 페르소나가 1개면 그것으로 자동 확정. 사용자에게 묻지 않는다.
   - 2개 이상이면 **단 한 번만** 사용자에게 어느 페르소나로 시뮬할지 묻는다. 선택을 받으면 그 뒤로는 추가 질문 없이 진행.
3. **게이트 메시지**: 사용자에게 다음을 한 번에 통지하고 단 하나의 confirm만 받는다 (페르소나 1개라서 묻지 않은 경우에도 여기서는 실행 confirm을 받는다 — 시뮬은 API 비용이 드는 작업이므로):
   - 확정된 `persona_id`
   - 모드: `landing_plus_meeting` (고정)
   - 예상 세션 수 + 대략 토큰 비용 추정 (`persuasion-review` SKILL.md §C-4 공식 사용)
   - "이대로 진행합니다 — 시뮬 완료까지 추가 질문 없이 쭉 달립니다"
4. confirm을 받으면 `persuasion-review` skill **Flow C** 를 다음 조건으로 수행한다. Skill tool로 `skill="persuasion-review"` 호출 시 **프롬프트에 다음을 명시**해 내부 티키타카를 차단한다:
   - 페르소나: `<확정된 persona_id>` (선택 단계 스킵)
   - 전달 모드: `landing_plus_meeting` (질문 스킵)
   - 가치제안 문서는 **사용자 확인 없이 바로 draft → 저장 → 실행**. docs/(특히 `mission.md`) + 현재 구현 상태를 근거로 Claude가 self-contained 하게 작성하고 즉시 `runs/<run_id>/value_proposition.md`에 저장.
   - 비용 confirm은 Step 2.3에서 이미 받았으므로 스킵.
   - `run_simulation.py` 실행 → `report.md` 생성까지 인간 개입 0회.
5. 시뮬 실행이 완료되면 `persuasion-data/runs/<run_id>/report.md`를 Read로 읽는다. 사용자에게는 실행 완료 + `run_id`만 짧게 보고하고 Step 3으로 곧장 진행.

### Step 3. 요구사항 후보 도출 및 우선순위

1. `report.md`의 우려 패턴, 실행 리스크, 가치제안 개선 제안, 페르소나 보정 힌트를 모두 훑는다.
2. 이를 근거로 **추가/수정 요구사항 후보 3-5개**를 도출한다. 각 후보는 다음 구조로 메모:
   - `title`: 한 줄 요약
   - `source`: report.md의 어느 부분에서 유래했는지 (섹션/인용)
   - `affected_persona_pain`: 어느 페르소나의 어떤 pain이 해소되는지
   - `sketch`: 구현 스케치 3-5줄. 인간 개입 지점이 있다면 반드시 명시.
   - `cheaper_alternative_considered`: 더 싼 대안을 검토했는지, 왜 이걸 택했는지
3. 후보들을 **우선순위 순으로 정렬**. 우선순위 기준:
   - 시뮬에서 드러난 pain의 심각도 (성사/실패 판정에 직접 영향)
   - 구현 비용 (AI 에이전트가 CLI에서 끝낼 수 있는가)
   - 증거 강도 (여러 stakeholder에서 반복 등장한 우려인가)
4. 이 리스트는 내부 메모로만 쓴다. 사용자에게 전체 나열할 필요 없음.

### Step 4-5. CTO 결재 루프

우선순위 1위부터 순서대로 `tech-critic-lead` 서브에이전트에게 결재를 요청한다.

**각 후보마다:**

1. `Agent` tool을 `subagent_type="tech-critic-lead"`로 호출. 프롬프트에 다음을 **자체완결적으로** 담아 전달:
   - 요구사항 제안 (title, 왜 필요한지, 어느 고객 pain에서 유래했는지)
   - 현재 구현 상태 요약 (Step 1에서 파악한 것 중 관련 부분)
   - 제안자 구현 스케치 + 인간 개입 지점
   - 근거 인용 (report.md의 해당 대목 발췌, 가능하면 파일 경로 + 섹션까지)
   - 검토한 더 싼 대안들
2. 반환된 판정 파싱:
   - **승인**: 이 후보를 최종 채택으로 확정하고 루프 종료. Step 6으로.
   - **거부**: `거부 사유 유형` 확인:
     - `insufficient_evidence`, `value_unclear`, `cheaper_alternative_exists`, `scope_too_large` → **보강 재제안 가능**. report.md에서 더 강한 근거를 뽑거나, scope를 쪼개거나, 더 싼 구현으로 재스케치 후 같은 후보를 **최대 1회** 재제출. 재거부 시 다음 후보로.
     - `requires_human_intervention`, `not_urgent` → 보통 보강이 어렵다. 바로 다음 후보로.
     - `개선 가이드`에 "재제안 불가"가 명시된 경우 → 즉시 다음 후보.
3. 모든 후보가 거부되면 사용자에게 "현재 시뮬 결과만으로는 `tech-critic-lead`를 설득할 만한 요구사항이 없다"고 보고하고, 다음 행동 옵션(페르소나 추가/수정, 가치제안 변경 후 재시뮬, 수동 후보 추가)을 제시.

**재제안 시 주의**: 같은 후보를 무한 반복하지 않는다. 1회 보강 후에도 거부되면 다음 후보로 넘어간다. CTO가 "쉽게 승인 안 하는 사람"임을 기억하고, 거부 사유를 설득하려 억지 근거를 만들지 말라.

### Step 6. 채택 요구사항 제시

1. 채택된 요구사항을 사용자에게 다음 형식으로 보고:
   - 요구사항 title
   - 유래한 고객 pain + 근거 인용
   - 구현 스케치
   - CTO 승인 조건부 조건 (있으면)
   - 시뮬 `run_id`
2. 사용자에게 다음 행동을 제안: "`plan-and-build` skill로 바로 구현 계획 작성으로 넘어갈까요?"

## 호출 규칙 요약

- `persuasion-review` 실행 → `Skill` tool(`skill="persuasion-review"`) 또는 그 SKILL.md 절차를 직접 수행. **호출 시 페르소나와 `landing_plus_meeting` 모드를 반드시 프롬프트에 명시해 내부 선택 단계를 스킵시킨다.**
- `tech-critic-lead` 결재 → `Agent` tool(`subagent_type="tech-critic-lead"`). 프롬프트는 서브에이전트가 이전 대화를 못 본다는 전제로 자체완결.
- 문서 탐색은 필요시 `Explore` 서브에이전트 병렬.

## 하지 말 것

- 시뮬을 건너뛰고 Claude 혼자 요구사항을 상상해내지 말 것.
- 페르소나 미확정 상태로 `persuasion-review`를 호출하지 말 것. 반드시 `persona_id`를 먼저 확정하고 들어간다.
- 전달 모드를 `landing_plus_meeting` 외로 바꾸지 말 것. 사용자가 명시적으로 요청해도, 이 skill 맥락에서는 고정.
- Step 2.3의 단일 confirm 이후에는 **사용자에게 다시 묻지 말 것**. 가치제안 문서 초안 확인, 중간 점검, 비용 재confirm 등 일체의 중간 상호작용 금지. report.md 생성 후 Step 3으로 바로 진행.
- CTO 거부를 뚫기 위해 `report.md`에 없는 근거를 지어내지 말 것.
- 여러 요구사항을 한꺼번에 채택하지 말 것. 스프린트에 올릴 단 하나만.
- `tech-critic-lead`의 거부를 사용자에게 숨기지 말 것. 어떤 후보가 왜 거부됐는지 간단히 함께 보고.
