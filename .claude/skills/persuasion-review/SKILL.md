---
description: 잠재고객 페르소나 기반으로 현재 서비스/신규 기능의 설득력을 다중 claude headless 세션으로 비판적 시뮬레이팅. 트리거 — "현재 서비스의 설득력을 검토하고싶어", "설득력 검토", "고객 시뮬", "시뮬 돌려줘", "새 고객 프로파일 만들자", "페르소나 만들자", "고객 프로파일 수정하자", "고객 프로파일 보여줘", "페르소나 목록" 및 유사 의도.
---

# persuasion-review

잠재고객 페르소나 기반 설득력 시뮬레이션 skill. 상세 설계는 `SPEC.md` 참조.

## 무인 모드 오버라이드 (HARNESS_HEADLESS=1)

**이 skill 본문의 어떤 지시보다도 먼저 적용되는 최상위 오버라이드다.**

세션 시작 시 **반드시 가장 먼저** Bash tool로 다음을 실행해 모드를 확정한다:

```bash
echo "HEADLESS=${HARNESS_HEADLESS:-${BET_HEADLESS:-0}}"
```

<!-- @TODO REMOVE LEGACY: `${BET_HEADLESS:-0}` fallback은 rename 이전 run-server.py가 주입하던 구명(舊名) 호환용. 모든 run-server.py 프로세스가 HARNESS_HEADLESS 로 재시작된 뒤 제거. -->

출력이 `HEADLESS=1` 이면 이 세션은 **무인 서버 세션**이며, 다음 상호작용 지점이 모두 무효화된다:

- **Flow A** (페르소나 생성): 사용자 서술/티키타카가 필수이므로 무인 모드에서는 **절대 호출되어서는 안 된다**. 호출자(ideation 등)가 실수로 Flow A로 유도하면 그대로 중단하고 에러 메시지를 출력한다.
- **Flow C**의 C-1(페르소나 복수 선택) — 호출자가 프롬프트로 `persona_id`를 명시한 경우 그것만 사용. 명시 없으면 `persuasion-data/personas/` 목록 상 첫 번째.
- **Flow C**의 C-2(전달 모드 선택) — 호출자가 명시한 모드 사용. 명시 없으면 `landing_plus_meeting`.
- **Flow C**의 C-3(가치제안 문서 draft 후 사용자 확인) — 확인 없이 바로 저장 + 실행.
- **Flow C**의 C-4(비용 confirm) — 비용은 stderr/stdout로만 보고하고 자동 진행 (confirm 없음).
- **Flow C**의 C-6(사용자 브리핑) — 최종 요약은 report.md 안에 남기는 것으로 충분. 별도의 "사용자에게 브리핑" 출력은 간결히.
- "대원칙 3. 비용 고지 - 실행 전 ... confirm 받는다" 는 무인 모드에서는 **비용 로깅만 하고 confirm 생략**.

출력이 `HEADLESS=1` 이 아닐 때만 아래 "대원칙"부터의 인간 대화형 절차를 따른다.

## 대원칙

1. **익명성**. 실제 고객명/회사명을 그대로 저장하지 않는다. 익명 `persona_id` + 회사 메타(산업/규모/단계)만.
2. **비판적 태도**. 모든 세션은 외부 SaaS 도입의 시간·인적·가격·신뢰도 비용을 엄격히 따진다. 기대 효과가 명백히 크지 않으면 쉽게 받아들이지 않는다.
3. **비용 고지**. 시뮬은 API 비용을 쓴다. 실행 전 예상 세션 수를 사용자에게 반드시 고지하고 confirm 받는다.
4. **버전 보존**. 페르소나 수정 시 `version`을 +1, `updated_at` 갱신. 과거 run 기록은 절대 건드리지 않는다. 각 run은 `persona_version`을 `run.md`에 기록.
5. **경로**. skill 정의(SKILL.md / SPEC.md / scripts/)는 `.claude/skills/persuasion-review/`에, 데이터(`personas/`, `runs/`, `feature-ideas.md`)는 레포 루트 `persuasion-data/`에 둔다. Claude Code가 `.claude/` 경로를 sensitive로 분류해 headless 세션 Write를 차단하기 때문. 아래 언급되는 `personas/` · `runs/` 경로는 모두 `persuasion-data/` 기준.

## 트리거 → 플로우 매핑

| 트리거 예시                                                         | 플로우          |
| ------------------------------------------------------------------- | --------------- |
| "새 고객 프로파일 만들자", "페르소나 만들자"                        | **Flow A**      |
| "고객 프로파일 수정하자", "페르소나 수정"                           | **Flow B-edit** |
| "고객 프로파일 보여줘", "페르소나 목록"                             | **Flow B-view** |
| "현재 서비스의 설득력을 검토하고싶어", "설득력 검토", "시뮬 돌려줘" | **Flow C**      |

---

## Flow A: 페르소나 생성

1. 사용자에게 "고객 인터뷰 메모나 자유서술을 편하게 써달라"고 요청. 필요 시 주요 필드 목록을 먼저 제시 (keyman의 역할/권한/예산/pain, stakeholder 네트워크, 경쟁솔루션).
2. 사용자 서술을 받아 `profile.md` draft 작성. 채우지 못한 필드는 `unknown`으로 명시.
3. stakeholder 네트워크를 mermaid로 시각화:
   ```mermaid
   graph TD
     KM[keyman: CTO] -- trust:55 --> SALES[Salesman]
     KM -- trust:80 --> SH1[엔지니어링 리더]
     SH1 -- weight:60 --> SH3[시니어 개발자]
   ```
4. 사용자와 티키타카로 보정. 특히 확인할 것:
   - `unknown` 필드 — 정말 모름인지, 채울 수 있는지
   - `trust_with_salesman`, `trust_with_keyman` — 초깃값 직접 지정 요청
   - `decision_authority` — full/partial/none 중 확정
5. 최종 컨펌 후 저장:
   - `personas/<persona_id>/profile.md`
   - `personas/<persona_id>/meta.md` (company_meta, version=1, created_at)
6. `persona_id`는 익명 슬러그 (예: `fintech-startup-cto-01`).

페르소나 스키마 전문은 `SPEC.md §2.1`.

## Flow B-edit: 페르소나 수정

1. 대상 `persona_id` 확인. 없으면 목록 제시.
2. 전체 재인터뷰가 아닌 **특정 필드만 패치**. 어떤 필드를 바꿀지 먼저 질문.
3. 변경 후 `version` +1, `updated_at` 갱신. 과거 run 기록 유지.

## Flow B-view: 페르소나 조회

- 인자 없음 → `personas/` 하위 목록 + 각 요약(keyman role, company_meta) 제시.
- `persona_id` 지정 → `profile.md` 내용 + mermaid 네트워크 다이어그램 렌더링.

---

## Flow C: 설득력 검토 (메인)

### C-1. 대상 페르소나 선택

- `personas/` 목록을 제시하고 복수 선택 허용.
- 페르소나가 없거나 추가 필요 → Flow A로 유도.

### C-2. 전달 모드 선택

사용자에게 물어봄:

- `landing_only` — 랜딩페이지 카피만 전달
- `landing_plus_meeting` — 랜딩페이지 + 세일즈 미팅/미디어 컨텐츠 (랜딩에 없는 구체 기능 설명 포함 가능)

### C-3. 가치제안 문서 작성

- 전달 모드에 맞춰 Claude가 draft 작성. 랜딩 카피, 기능 설명, 가격 플랜 등.
- `runs/<run_id>/value_proposition.md`로 저장 (run_id는 C-5에서 확정되므로 실행 직전 경로 확정).

### C-4. 비용 인지 + 실행 confirm

선택된 **페르소나별로** 예상 세션 수 계산:

```
세션 수 ≈ 1 (keyman initial)
         + N_direct                           # 5b
         + K_drop * N_direct * M              # 5c 재설득 (K_drop≈0.5 추정)
         + N_indirect                         # 5d BFS
         + 1 (report)
```

- `M = clamp(round(trust_with_salesman / 33), 1, 3)`
- `N_direct`: `relation_to_keyman == direct` stakeholder 수
- `N_indirect`: `downstream` stakeholder 수

여러 페르소나 합산 세션 수 + 대략 토큰 비용(세션당 평균 가정치)을 고지 바로 다음단계 진행.

### C-5. Python script 실행

페르소나별로 **순차** 실행 (페르소나 간 병렬 X, 로그/비용 추적 단순화).

```bash
# repo root에서 실행
uv run --with pyyaml python .claude/skills/persuasion-review/scripts/run_simulation.py \
  --persona-id <persona_id> \
  --value-prop persuasion-data/runs/<run_id>/value_proposition.md \
  --run-id <run_id> \
  --max-parallel 4 \
  [--enable-ux-probe]                        # 5a0 활성화 (프로젝트 어댑터 있을 때만)
```

`--enable-ux-probe`는 5a(문서 기반 판단) 앞에 5a0(실제 서비스 조작 probe)을 끼워 넣는다. 상세는 §4.5.

`run_id` 형식: `<persona_id>_<YYYYMMDD_HHMMSS>`.

스크립트는 `runs/<run_id>/` 하위에 모든 세션 출력 + `report.md`를 생성한다.

### 4.5 (opt-in) 5a0 — keyman UX probe

`--enable-ux-probe`로 활성화. keyman이 **value_proposition.md만 읽은 상태**에서 실제 서비스를 직접 조작하며 UX를 점검하는 단계. 5a(문서 기반 판단)의 입력에 probe 리포트 + 스크린샷을 추가해, "프로덕트 성숙도"라는 신뢰도 비용 축을 평가 기준에 포함시킨다.

- 프롬프트: `scripts/prompts/keyman_ux_probe.md`
- 브라우저 조작: `scripts/ux_probe.py` (Playwright CLI 래퍼, 프로젝트 독립)
- **프로젝트 어댑터**: `persuasion-data/ux_probe_adapter.py`. skill은 프로젝트별 서비스 기동 방법을 모르므로 이 파일이 필요하다. 계약:

```python
def start(run_dir: pathlib.Path) -> dict:
    # 서비스 기동 + (필요 시) seed. 반환 dict 필수 키:
    #   base_url: str          실행 중인 서비스 루트 URL
    #   python_bin: str        playwright 설치된 python 경로
    #   credentials: dict      페르소나가 로그인 시 쓸 자격 (자유 형식)
    #   context: dict          템플릿 컨텍스트 (자유 형식, ex: entity ids)
    #   tasks_markdown: str    프로젝트별 Task 목록 (markdown, T1, T2, …)
    # side effect: teardown 정보(pidfile 등)를 run_dir 하위에 직접 저장.
    ...

def stop(run_dir: pathlib.Path) -> None:
    # start가 띄운 서비스 종료. 실패해도 raise 하지 말 것.
    ...
```

- 어댑터가 없으면 5a0은 조용히 스킵되고 run은 5a부터 진행. 5a 프롬프트의 "프로덕트 성숙도 루브릭"은 "증거 부재"를 신뢰도 감점 사유로 처리.
- 출력: `runs/<run_id>/00_keyman_ux_probe.md` + `runs/<run_id>/ui_screenshots/*.png`
- 비용: Task 1개 ≈ Bash 호출 4~8회. Task 4개 시 세션당 추가 \$0.5~1.5 예상.

### C-6. 결과 브리핑

1. 스크립트 실행 완료 후 `runs/<run_id>/report.md`를 읽는다.
2. 사용자에게 요약 브리핑:
   - 페르소나별 **최종 판정** (성사 / 실패)
   - **실행 리스크** (keyman decision_authority + 실무자 반응 기반)
   - **가치제안 개선 제안** (공통 우려 패턴)
   - **페르소나 보정 힌트** (시뮬 중 프로파일과 어긋나 보인 판단)
3. 복수 페르소나의 경우 표로 정리.

---

## 출력 frontmatter 규약

모든 세션 출력 파일은 아래 frontmatter를 **반드시** 포함 (system prompt로 강제):

```yaml
---
session_type: keyman_initial | stakeholder_review | keyman_response | staff_review
actor_id: <keyman id 또는 stakeholder id>
run_id: <run_id>
round: 1 # 재설득 라운드 번호. 해당 없으면 1.
decision: drop | convince_stakeholders | accept | reject | critical_accept | positive_accept | reconvince
confidence: 0-100
created_at: <ISO8601>
---
```

본문 섹션: **판단 요지**, **구체적 이유**, **걱정/의문점**, (해당 시) **다음 행동**.

## Python 의존성

```bash
pip install pyyaml
```

`claude` CLI는 시스템에 설치되어 있다고 가정.
