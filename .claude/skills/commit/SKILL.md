사용자가 지금까지의 작업을 git commit(및 선택적으로 push)하도록 지시할 때 따르는 절차. '커밋', 'commit', '커밋 해줘', '커밋푸쉬 ㄱㄱ', 'commit push', '지금까지 한 작업 커밋' 등 commit/push 의도가 보이는 모든 발화에서 트리거된다.

---

## 00. 무인 모드 오버라이드 (HARNESS_HEADLESS=1)

**이 skill 본문의 어떤 지시보다도 먼저 적용되는 최상위 오버라이드다.**

세션 시작 시 **반드시 가장 먼저** Bash tool로 다음을 실행해 모드를 확정한다:

```bash
echo "HEADLESS=${HARNESS_HEADLESS:-${BET_HEADLESS:-0}}"
```

<!-- @TODO REMOVE LEGACY: `${BET_HEADLESS:-0}` fallback은 rename 이전 run-server.py가 주입하던 구명(舊名) 호환용. 모든 run-server.py 프로세스가 HARNESS_HEADLESS 로 재시작된 뒤 제거. -->

출력이 `HEADLESS=1` 이면 이 세션은 **무인 서버 세션**이며, 이 skill 본문의 **모든 사용자 확인/통지/질문 단계가 무효화**된다:

- "판단이 애매하면 사용자에게 물어본다", "사용자에게 목록과 분류를 보여주고 승인받는다", "쪼갠 결과를 사용자에게 먼저 보여주고 승인받는다", "사용자에게 확인", "발견되면 사용자에게 확인" → 전부 스킵하고 합리적 기본값으로 자동 진행한다.
- "이 단계를 건너뛰지 않는다", "**반드시**", "먼저 확인한다" 같은 강한 표현도 `HEADLESS=1` 에서는 적용되지 않는다.
- 질문을 출력하고 대기하는 것조차 금지 (stdin이 없음). 바로 결정해서 진행한다.
- `main`/`master` 브랜치 commit도 확인 없이 그대로 진행한다 (호출자가 이미 의도했다고 간주).
- 호출자가 프롬프트에 명시한 "대상 파일", "제외할 파일"을 그대로 따른다.

출력이 `HEADLESS=1` 이 아닐 때만 아래 "0. 대원칙" 부터의 인간 대화형 절차를 따른다.

---

## 0. 대원칙 (어기면 안 됨)

1. **현재 대화 컨텍스트와 관련된 파일만 commit한다.** 이번 세션에서 내가 직접 만들거나 수정했거나, 사용자와 논의하며 의도적으로 건드린 파일만 대상이다. 작업 중 우연히 바뀐 로컬 파일, 이전 세션의 잔여물, 출처가 불분명한 변경은 절대 함께 commit하지 않는다. 판단이 애매하면 사용자에게 물어본다.
2. **논리적으로 다른 성격의 변경은 분리된 commit으로 나눈다.** 한 번에 한 가지 일만.
3. **push는 사용자가 명시적으로 요청한 경우에만 수행한다.** ('push', '푸쉬', '푸시', '올려줘' 등이 발화에 포함된 경우)
4. **`--no-verify` 금지.** pre-commit/pre-push hook은 항상 통과시킨다. hook이 실패하면 원인을 고치거나 사용자에게 보고한다.
5. **`main`/`master` 브랜치에 직접 commit하려는 상황이면 먼저 확인한다.** 대부분 실수다.
6. **`git add .` / `git add -A` 금지.** 반드시 관련 파일만 경로를 명시해서 stage한다.
7. **비밀값·산출물 금지.** `.env*`, `*.log`, `dist/`, `build/`, `node_modules/`, `.DS_Store`, 대용량 바이너리 등은 의도적으로 추가한 게 아니면 commit하지 않는다. 발견되면 사용자에게 확인.

---

## 1. 절차

### 1-1. 현재 상태 파악

```bash
git status --short
git diff --stat
git log --oneline -15   # 메시지 스타일 재확인
git branch --show-current
```

- 작업 브랜치가 `main`/`master`인지 확인. 맞으면 대원칙 5 적용.
- 변경된 모든 파일 목록을 확인한다.

### 1-2. 관련 파일 선별 (대원칙 1)

현재 세션 컨텍스트를 기준으로 변경 파일들을 3가지로 분류한다:

| 분류 | 처리 |
|---|---|
| **관련(IN)** — 이번 대화에서 내가 수정/생성했거나 논의된 파일 | commit 대상 |
| **애매함(UNKNOWN)** — 언제·왜 바뀌었는지 명확하지 않은 파일 | **사용자에게 개별 확인** |
| **무관(OUT)** — 명백히 이번 작업과 관련 없는 파일 (다른 기능, 로컬 설정, IDE 파일 등) | commit에서 제외. 사용자에게 "이 파일들은 관련 없어 보여 제외함" 라고 알림 |

애매하거나 무관 파일이 하나라도 있으면, staging 전에 사용자에게 목록과 분류를 보여주고 승인받는다. **이 단계를 건너뛰지 않는다.**

### 1-3. 논리 단위로 commit 쪼개기 (대원칙 2)

관련 파일 집합을 다시 성격별로 묶어 여러 commit으로 분할한다. 예시:

- 리팩터링 + 신규 기능 → **2개 commit** (refactor 먼저, feat 나중)
- 버그 수정 + 관련 테스트 → **1개 commit** (같은 맥락)
- 버그 수정 + 무관한 타이포 수정 → **2개 commit**
- UI 변경 + 그 과정에서 발견한 유틸 추출 → **2개 commit** (refactor 먼저)

한 파일 안에 성격이 다른 변경이 섞여 있으면 `git add -p` (hunk 단위 staging)를 사용한다. 전체 파일을 다 넣지 말 것.

쪼갠 결과(각 commit의 파일/메시지 초안)를 사용자에게 먼저 보여주고 승인받는다. 단, 관련 파일이 1~2개이고 성격이 명백히 단일 목적이면 승인 단계 생략 가능.

### 1-4. commit 메시지 작성

이 repo의 `git log --oneline -30`을 기준으로 정확히 동일한 스타일을 따른다.

**형식**

```
<type>(<scope>): <한글 요약>

<본문 — 필요할 때만, 불릿 또는 짧은 문단>
```

**type** (이 repo에서 관찰된 것만 사용)

- `feat` — 새 기능
- `fix` — 버그 수정
- `enhance` — 기존 기능 개선/UX 개선 (리뉴얼 수준)
- `refactor` — 동작 변화 없는 내부 구조 변경
- `perf` — 성능 개선
- `chore` — 빌드/설정/버전업 등 주변부
- `docs` — 문서만
- `skill` — `.claude/skills/` 하위 Claude Code skill 파일의 생성/수정/삭제. scope는 **skill 이름**. 예: `skill(commit): 신규 생성`, `skill(ui-design-system): 색상 토큰 섹션 보강`

**scope** (관찰된 것 우선, 변경 위치에 맞게)

- `dashboard` — `packages/dashboard/`
- `web` — `packages/web/`
- `cli` — `packages/cli/`
- `turbo` — 모노레포 루트 빌드/설정
- 그 외 필요시 패키지/영역 이름으로 추가
- 여러 scope에 걸치면 `(web,dashboard)` 또는 scope 생략
- `skill` type의 scope는 항상 대상 skill 이름 (예: `commit`, `plan-and-build`, `ui-design-system`)

**요약 규칙**

- 명사구/동사구 가능. 실제 로그를 보면 "~ 추가", "~ 개선", "~ 재구성" 식이 많음.
- 끝에 마침표 없음.
- 한 줄 72자 이내.

**본문 규칙**

- 단순 변경이면 생략.
- 여러 항목을 한 commit으로 묶을 수밖에 없을 때 불릿(`- `)으로 나열.
- "왜" 가 자명하지 않으면 짧게 이유 한 줄.

**co-author trailer (필수)**

모든 commit 메시지 끝에 빈 줄 두고 아래 trailer를 추가한다:

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

### 1-5. stage & commit

```bash
# 관련 파일만 명시적으로 stage
git add <path1> <path2> ...
# 또는 hunk 단위
git add -p <path>

# 한 번 더 확인
git diff --cached --stat

# commit — heredoc로 멀티라인 메시지 작성 (trailer 포함)
git commit -m "$(cat <<'EOF'
<type>(<scope>): <요약>

<본문>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

commit이 여러 개면 1-5를 반복한다. 한 commit을 마치면 다음 commit 전에 `git status`로 남은 변경을 재확인한다.

### 1-6. 결과 확인

```bash
git log --oneline -<N>   # N = 방금 만든 commit 개수
git status               # working tree가 기대대로인지
```

커밋 누락이나 예상치 못한 남은 변경이 있으면 사용자에게 즉시 보고.

### 1-7. push (요청된 경우에만)

발화에 push 의도가 있었을 때만:

```bash
git push
```

- upstream이 없으면 `git push -u origin <현재브랜치>`.
- `--force` / `--force-with-lease`는 **사용자가 명시적으로 요청한 경우에만**. 기본 push가 non-fast-forward로 거절되면 상황을 설명하고 옵션을 제시.
- push 후 최신 원격 상태를 한 줄로 보고 (브랜치 + 최신 commit hash).

---

## 2. 보고 형식

commit이 끝나면 아래 형식으로 간결히 보고:

```
✅ N개 commit 생성 (+push 여부)
  1. <hash> <type>(<scope>): <요약>
  2. <hash> <type>(<scope>): <요약>
제외한 파일: <있으면 나열, 없으면 생략>
```

## 3. 자주 하는 실수 (하지 말 것)

- ❌ `git add .` 한 줄로 전부 stage — 무관 파일이 섞여 들어감
- ❌ 여러 성격의 변경을 "작업 내용 반영" 같은 뭉뚱그린 메시지로 한 번에 commit
- ❌ 사용자 확인 없이 `.env`, lock 파일, 빌드 산출물 commit
- ❌ 메시지에 "as requested by user", "per the discussion" 같은 대화 맥락 언급
- ❌ 이번 작업과 무관한데 working tree에 있던 수정을 끼워 commit
- ❌ push 요청 없는데 push까지 진행
- ❌ hook 실패를 `--no-verify`로 우회
