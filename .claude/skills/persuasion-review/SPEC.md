---
name: persuasion-review
status: draft
last_updated: 2026-04-22
---

# persuasion-review — 잠재고객 설득력 시뮬레이션 skill 스펙

## 0. 목적

현재 서비스(또는 신규 기능)에 대한 가치제안이 **실제 잠재고객 의사결정 네트워크에서 얼마나 설득력을 갖는지**를, 고객 페르소나 기반 다중 claude headless 세션으로 시뮬레이팅하여 비판적으로 검토한다. 결과를 누적해 향후 실제 고객 피드백과 비교·보정(캘리브레이션)할 기반을 만든다.

핵심 설계 원칙:

- 모든 세션은 **비판적 검토자** 역할. 외부 서비스 도입의 시간/인적 비용, 신뢰도, 가격 리스크를 엄격히 따지며, 기대 효과가 명백히 크지 않으면 쉽게 도입하지 않는다.
- **신뢰관계 점수**가 핵심 변인. salesman↔keyman, keyman↔stakeholder 간 신뢰도가 세션 판단과 재설득 반복 횟수에 영향.
- 고객 실명은 저장하지 않는다. 익명 id + 회사 메타(산업/규모/단계)만 사용.

---

## 1. 디렉토리 구조

```
<repo_root>/
├── .claude/skills/persuasion-review/   # skill 정의 (Claude가 읽음)
│   ├── SKILL.md
│   ├── SPEC.md
│   └── scripts/
│       ├── run_simulation.py           # 메인 오케스트레이터
│       ├── session_runner.py           # claude -p 래퍼
│       └── prompts/                    # 단계별 system prompt 템플릿
│           ├── keyman_initial.md
│           ├── stakeholder_review.md
│           ├── keyman_response.md
│           └── final_analyzer.md
└── persuasion-data/                    # 데이터 (Write 대상 — .claude/ 밖에 둠)
    ├── personas/
    │   └── <persona_id>/
    │       ├── profile.md              # keyman + stakeholders + 경쟁솔루션 + 그래프
    │       └── meta.md                 # 회사 메타, 버전, 생성일
    ├── runs/                           # 실행마다 누적 (gitignore 권장)
    │   └── <run_id>/                   # run_id = <persona_id>_<YYYYMMDD_HHMMSS>
    │       ├── run.md                  # 실행 메타 (대상 페르소나, 가치제안 버전 등)
    │       ├── value_proposition.md    # 이번 실행의 가치제안 문서
    │       ├── 01_keyman_initial.md
    │       ├── 02_stakeholder_<sid>.md
    │       ├── 03_keyman_response_<sid>.md
    │       ├── 04_stakeholder_recheck_<sid>_round<N>.md
    │       ├── 05_staff_<sid>.md       # depth>=2 실무자
    │       └── report.md               # 최종 분석 리포트
    └── feature-ideas.md                # 시뮬에서 발견된 제품 아이디어 백로그
```

**.claude/ 밖에 데이터를 두는 이유**: Claude Code(2.1.x)가 `.claude/` 하위 경로를 sensitive로 분류해 headless 세션의 Write를 차단한다. personas(익명 설계)·feature-ideas는 commit 대상, runs는 per-machine 로컬 출력.

`persona_id`, `stakeholder_id(sid)`는 짧은 슬러그 (예: `fintech-startup-cto-01`, `sh-eng-lead`).

---

## 2. 데이터 모델

### 2.1 페르소나 (`personas/<persona_id>/profile.md`)

YAML frontmatter + markdown 본문. frontmatter에 구조화된 필드, 본문에 자유서술(pain·동기·맥락).

```yaml
---
persona_id: fintech-startup-cto-01
version: 1
created_at: 2026-04-22
updated_at: 2026-04-22
company_meta:
  industry: fintech
  size: 30-50
  stage: series-a
keyman:
  id: km
  role: CTO
  decision_authority: full    # full | partial | none
  budget_range_krw: "월 100만~500만"
  tech_literacy: high
  risk_preference: moderate
  personality_notes: "데이터 근거 중시, ROI 숫자 없으면 쉽게 반응 안 함"
  current_pains:
    - "Claude Code 사용량 폭주하는데 팀별 분배가 불투명"
    - "토큰 한도 관리 수작업"
  existing_alternatives:
    - "자체 대시보드 구축 검토 중"
  buy_triggers:
    - "토큰 한도 초과 이슈 재발"
  reject_triggers:
    - "보안 감사 통과 불확실성"
  communication_style: "기술팀 내부에는 상세히 공유, 경영진에는 요약만"
trust_with_salesman: 55   # 0-100
stakeholders:
  - id: sh-eng-lead
    role: 엔지니어링 리더
    relation_to_keyman: direct   # direct | downstream
    influence: 70
    decision_weight_hint: "keyman이 가장 신뢰하는 실무 의견"
    tech_literacy: high
    personality_notes: "새 툴 도입에 보수적, ROI 데이터 요구"
    trust_with_keyman: 80
    connected_to:
      - { id: sh-dev-a, weight: 60 }
      - { id: sh-dev-b, weight: 50 }
  - id: sh-finance
    role: 재무 담당
    relation_to_keyman: direct
    influence: 40
    trust_with_keyman: 50
    connected_to: []
  - id: sh-dev-a
    role: 시니어 개발자
    relation_to_keyman: downstream
    influence: 20
    trust_with_keyman: unknown
    connected_to: []
  - id: sh-dev-b
    role: 주니어 개발자
    relation_to_keyman: downstream
    influence: 10
    trust_with_keyman: unknown
    connected_to: []
competing_solutions:
  - name: "자체 내부 구축"
    usage: considering          # using | considering | aware
    strengths: ["완전한 커스터마이징", "데이터 외부 유출 없음"]
    weaknesses: ["초기 구축 비용", "유지보수 부담"]
    switching_cost: high
  - name: "AWS Bedrock 모니터링"
    usage: aware
    strengths: ["인프라 통합"]
    weaknesses: ["Claude Code 팀 컨텍스트 부재"]
    switching_cost: low
---

# 회사·키맨 배경 서술

(자유서술. 인터뷰 원본 메모를 요약하여 기록. 시뮬 세션 system prompt에 함께 주입됨.)

## 조직 역학 메모

(keyman이 stakeholder들과 어떤 정치적 맥락에 있는지 등 구조화 필드로 표현 안 되는 정보.)
```

**"unknown" 처리**: `tech_literacy: unknown`, `trust_with_keyman: unknown` 등. 세션 system prompt에 "이 필드는 unknown이므로 가장 비판적/비관적 가정 하에 판단하라"는 지시를 함께 주입.

**decision_authority의 효과**:

- `full`: keyman이 5c에서 stakeholder drop에도 재설득 경향 강함. 최종 리포트에서 "내부 반발 리스크"는 상대적으로 약하게 표기.
- `partial`: 중간.
- `none`: 5c에서 drop 경향 강함. 리포트에 "keyman accept이지만 실제 도입 불확실" 경고 강하게 표기.

경로 자체는 권한과 무관하게 모두 5a→5b→5c→5d를 거친다.

### 2.2 가치제안 문서 (`runs/<run_id>/value_proposition.md`)

```yaml
---
run_id: fintech-startup-cto-01_20260422_153000
persona_id: fintech-startup-cto-01
persona_version: 1
delivery_mode: landing_plus_meeting # landing_only | landing_plus_meeting
created_at: 2026-04-22T15:30:00
---
# 가치제안 요약
...
# 구체적 기능 설명 (미팅 전달 시)
...
# 가격/플랜
...
```

### 2.3 세션 출력 공통 포맷

모든 claude headless 세션의 출력 파일은 아래 frontmatter를 반드시 포함 (system prompt로 강제).

```yaml
---
session_type: keyman_initial | stakeholder_review | keyman_response | staff_review
actor_id: km | sh-eng-lead | ...
run_id: <run_id>
round: 1                     # 재설득 라운드 (해당 시)
decision: drop | convince_stakeholders | accept | reject | critical_accept | positive_accept
confidence: 72               # 0-100
created_at: 2026-04-22T15:31:12
---

## 판단 요지
(1-2문장)

## 구체적 이유
- ...

## 걱정/의문점
- ...

## (재설득인 경우) 다음 행동
- ...
```

---

## 3. 플로우

### 3.A 페르소나 생성 플로우

**트리거**: `"새 고객 프로파일 만들자"` 및 유사 의도 표현.

단계:

1. 사용자에게 "고객 인터뷰 메모나 자유 서술을 편하게 써달라"고 요청 (자유서술 + 추출 방식).
2. 사용자가 덩어리 텍스트 입력.
3. Claude가 스키마에 채운 draft markdown을 생성하여 보여줌. 채우지 못한 필드는 `unknown` 명시.
4. stakeholder 네트워크를 mermaid 다이어그램으로 함께 시각화:
   ```mermaid
   graph TD
     KM[keyman: CTO] -- trust:55 --> SALES[Salesman]
     KM -- trust:80 --> SH1[엔지니어링 리더]
     SH1 -- weight:60 --> SH3[시니어 개발자]
   ```
5. 사용자와 티키타카로 부족·틀린 부분 보정. 특히 `unknown` 필드는 사용자에게 "정말 모름인지, 채울 수 있는지" 확인.
6. 최종 컨펌 후 `personas/<persona_id>/profile.md` 및 `meta.md` 저장.

### 3.B 페르소나 수정/조회 플로우

**트리거**:

- 수정: `"고객 프로파일 수정하자"` + 대상 지정
- 조회: `"고객 프로파일 보여줘"` (목록 또는 특정 id)

수정은 전체 재인터뷰가 아닌 **특정 필드만 패치**. 수정 시 `version`을 1 증가시키고 `updated_at` 갱신. **과거 run 기록은 절대 건드리지 않으며**, 각 run은 자신이 사용한 `persona_version`을 `run.md`에 기록(캘리브레이션 시 추적용).

### 3.C 설득력 검토 (메인) 플로우

**트리거**: `"현재 서비스의 설득력을 검토하고싶어"` 및 유사 의도.

#### 3.C.1 단계 (Claude 대화)

1. **대상 페르소나 선택**: 저장된 페르소나 목록 제시, 복수 선택 가능. 없으면 "새로 만들래?" 제안 (→ 3.A로).
2. **전달 모드 선택**:
   - `landing_only`: 랜딩페이지 카피만 전달
   - `landing_plus_meeting`: 랜딩페이지 + 세일즈미팅 or 미디어 컨텐츠 (랜딩에 없는 구체 기능 설명 포함 가능)
3. **가치제안 문서 작성**: 선택된 전달 모드에 맞춰 Claude가 draft 작성 → 사용자와 티키타카로 컨펌 → `value_proposition.md` 저장.
4. **실행 예고 + 비용 인지**: 예상 세션 수 계산 후 사용자에게 고지.
   - 계산식: `1 (keyman initial) + N_direct + K_drop * (재설득 라운드 M) + N_indirect`
     - `N_direct`: depth 1 stakeholder 수
     - `K_drop`: 평균 drop 비율 추정 (기본 0.5로 추정)
     - `M = clamp(round(trust_with_salesman / 33), 1, 3)`
     - `N_indirect`: depth ≥ 2 stakeholder 수
   - 대략적 토큰 비용도 함께 고지 (세션당 평균 가정 기반).
   - 사용자 최종 confirm 후 python script 실행.

#### 3.C.2 단계 (python script 실행)

`scripts/run_simulation.py`가 아래 단계를 오케스트레이션. **각 단계는 claude headless (`claude -p ... --append-system-prompt ...`) subprocess로 실행**되며, 지정 경로에 지정 포맷(frontmatter 포함)으로 결과 파일을 남기도록 system prompt로 강제.

##### 5a. Keyman 초기 판단

- 입력: 페르소나 profile + 가치제안 문서 + `keyman_initial.md` system prompt
- 출력: `01_keyman_initial.md` (frontmatter: `decision: drop | convince_stakeholders`, `confidence`)
- **판정 규칙**: `confidence <= 75` 또는 `decision == drop` → 즉시 종료, 리포트 생성으로 점프.

##### 5b. 직접 연결 stakeholder 병렬 검토

- 대상: `relation_to_keyman == direct`인 모든 stakeholder
- 입력(공통): 해당 stakeholder profile + 가치제안 문서 + keyman의 5a 결과(요약 + 원문 첨부 방식으로) + trust scores + `stakeholder_review.md` system prompt
- **요약 vs 원문**: keyman의 `communication_style` 필드에 따라 요약 품질이 달라진다고 가정. system prompt에 "keyman의 전달 스타일: {style}" 주입하여 요약 품질이 자연스럽게 반영되도록.
- 병렬 실행, `max_parallel` (기본 4)로 제한.
- 출력: `02_stakeholder_<sid>.md` 각각.
- **판정 규칙**: `confidence > 70` → accept, 이하 → drop. (per-stakeholder 판정)

##### 5c. Keyman 응답 (drop된 stakeholder별 병렬)

- 5b에서 drop인 stakeholder들에 대해서만 실행.
- 입력: keyman profile + 가치제안 문서 + 5a 결과 + 해당 stakeholder의 5b 결과 + trust_with_salesman, trust_with_keyman + `keyman_response.md` system prompt
- 출력: `03_keyman_response_<sid>.md` (frontmatter: `decision: drop | reconvince`)
- **종결 규칙**: keyman이 한 건이라도 `drop`을 내면 **전체 run drop**. 5d로 진행하지 않음.
- 모두 `reconvince`라면 → stakeholder 재검토 라운드 실행.
  - 재검토 라운드는 최대 `M = clamp(round(trust_with_salesman / 33), 1, 3)`번 반복.
  - 매 라운드: stakeholder별 병렬로 `04_stakeholder_recheck_<sid>_round<N>.md` 생성. 해당 stakeholder의 이전 결과 + 지금까지 커뮤니케이션 히스토리 + 갱신된 재설득 의견 주입.
  - 각 라운드 종료 후 여전히 drop인 stakeholder가 있으면 다시 5c를 그 stakeholder들에 대해서만 실행. `M`에 도달할 때까지.
  - `M`번 시도해도 drop이 남아있으면 → 전체 run drop.

##### 5d. 나머지 stakeholder BFS 검토

- 5c까지 drop 없이 통과한 경우에만 진입.
- 대상: `relation_to_keyman == downstream`인 stakeholder들. `connected_to` 그래프 기반 BFS.
- **순서**: depth별 병렬 실행, depth 간 순차. (예: depth 2 모두 병렬 완료 후 depth 3 시작.)
- 입력: 해당 stakeholder profile + 가치제안 문서 + 상위 노드들과 오간 커뮤니케이션 (keyman 5a + 연결 상위 stakeholder의 최종 결과 등) + trust scores + `stakeholder_review.md` (실무자 모드)
- 출력: `05_staff_<sid>.md`
- **판정 (4단계)**:
  - `confidence < 35`: `reject`
  - `35 ≤ confidence < 50`: `critical_accept`
  - `50 ≤ confidence < 75`: `accept`
  - `confidence ≥ 75`: `positive_accept`
- **어떤 결과든 모든 stakeholder에 대해 시뮬 완료**. 거부 나와도 중단하지 않음.

##### 5e. 종료

- 모든 세션 종료 후 `report.md` 생성 단계로.

#### 3.C.3 단계 (Claude 대화, 최종 리포트)

- `final_analyzer.md` system prompt와 함께 모든 run 파일을 읽고 Claude가 분석:
  - **최종 판정**: 계약 성사 / 실패
    - 성사: keyman 5a accept → 5c 통과 (drop 없음)
    - 실패: 그 외
  - **실행 리스크 섹션**:
    - `decision_authority`와 실무자 거부/비판적수용 수를 조합하여 리스크 강도 산출
    - `full` + 실무자 일부 거부 → 중간
    - `none` + 실무자 거부 → 강함 ("keyman accept이지만 실제 도입 불확실")
  - **가치제안 개선 방안**: 각 세션의 "걱정/의문점"을 집계하여 공통 패턴 도출, 어느 카피/기능 설명을 강화·완화할지 제안
  - **페르소나 보정 힌트**: 시뮬 중 "이 판단이 설정된 페르소나 속성과 잘 맞지 않는 것 같음"이라는 단서가 있었다면 표시 (15번 캘리브레이션 플로우는 미구현이지만 힌트는 미리 남김)
- `report.md` 저장하고 사용자에게 요약 브리핑.

---

## 4. Python script 실행 규약

### 4.1 claude headless 호출 템플릿

```bash
claude -p "$(cat <<EOF
{task_instruction}

출력은 반드시 아래 경로에 아래 frontmatter 포맷으로 저장한다:
경로: {output_path}
필수 frontmatter 필드: session_type, actor_id, run_id, decision, confidence, created_at
EOF
)" \
  --append-system-prompt "$(cat prompts/{template}.md)" \
  --allowed-tools "Read Write"
```

`--allowed-tools`를 최소 권한으로 제한. 각 세션은 **자신의 output 파일 쓰기 + 주어진 입력 파일 읽기**만 허용.

### 4.2 동시성 제어

- `max_parallel` 기본 4, `run_simulation.py` 인자로 조정 가능.
- `asyncio` + `asyncio.Semaphore` 또는 `concurrent.futures.ThreadPoolExecutor` 사용.

### 4.3 에러 처리

- subprocess 실패 또는 출력 파일 미생성 시: 해당 세션 결과는 `decision: error, confidence: 0`으로 기록하고 다음 단계 진행. 단, keyman 세션 실패는 전체 중단.
- frontmatter 파싱 실패 시: 결과 파일을 보존한 채 사용자에게 경고 표시.

### 4.4 재실행 정책

- 동일 `run_id`로 재실행 시 기존 run 디렉토리는 건드리지 않고 새 timestamp로 별개 run 생성. (히스토리 보존.)
- 중간 실패한 run을 이어서 돌리는 기능은 미구현.

---

## 5. 미구현 (향후)

- **15번 캘리브레이션 플로우**: 실제 고객 피드백 입력 → 시뮬 diff → 페르소나 보정 제안. MVP 이후 실제 시뮬/실제피드백 데이터가 쌓인 뒤 설계.
- **페르소나 삭제**: 명시적 요청 시 수동으로.
- **중간 실패 run 재개**.

---

## 6. 열려있는 이슈 (구현 전 다시 확인)

- `keyman_initial.md` 등 프롬프트 템플릿의 구체 문구 — 구현 시작 시 별도 컨펌.
- 비용 추정 세션당 토큰 가정값 — 실제 1~2회 돌려본 뒤 보정.
- stakeholder 네트워크가 커질 경우 (> 20명) 현재 BFS 병렬 모델의 비용/시간 — 실제 돌려본 뒤 상한 정책 추가 검토.
