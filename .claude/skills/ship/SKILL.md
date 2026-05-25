---
name: ship
description: 지금까지의 작업을 한 번에 출하한다 — 커밋 → push → PR 생성 → squash merge. "commit push pr squash merge", "ship it", "출하해줘", "PR 만들고 머지해줘", "커밋푸시 PR 스쿼시", "변경사항 commit push 후 pr 생성하고 squash merge" 등 commit+push+PR+merge를 한 번에 끝내려는 의도에서 트리거된다. 커밋만/푸시만 원하면 commit skill을 쓴다.
---

# ship

작업을 `main`(기본 브랜치)으로 squash merge 까지 한 번에 출하하는 skill.
사람의 판단이 필요한 **커밋 작성**은 이 본문이 처리하고, **push→PR→merge**
의 결정적 plumbing 은 `scripts/ship.sh` 가 처리한다.

## 안전 규칙 (어기지 말 것)

- **force push 금지**, `--no-verify`/`--no-gpg-sign` 금지. 훅이 실패하면
  우회하지 말고 원인을 고친다.
- 기본 브랜치(`main`/`master`)에 **직접 커밋·머지하지 않는다** — 항상 feature
  브랜치 → PR.
- **검증을 약화시켜 머지하지 않는다.** required check 가 막으면 auto-merge로
  큐잉하거나 통과를 기다린다. check 우회(`--admin`)는 사용자가 명시적으로
  요청했을 때만(`SHIP_ADMIN=1`).
- 시크릿/대용량 산출물을 커밋하지 않는다(commit skill의 secret-scan 준수).

## 워크플로

### 1. 변경 파악 + 커밋

```bash
git status --short && git diff --stat
```

- 커밋할 게 없고 브랜치가 이미 base 보다 앞서 있으면 → 바로 3번(이미 커밋됨).
- 변경이 있으면 커밋한다. **프로젝트에 commit skill 이 있으면 그 규약을
  따른다.** 없으면 Conventional Commits (`feat:`/`fix:`/`docs:`/`refactor:`
  …), 제목은 명령형 한 줄, 본문은 *왜* 를 설명. 관련 변경만 스테이징.

### 2. 브랜치 보장

현재 브랜치가 기본 브랜치면 feature 브랜치를 먼저 만든다(커밋 전에).

```bash
DEF="$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)"
CUR="$(git branch --show-current)"
if [ "$CUR" = "$DEF" ]; then
  git checkout -b <type>/<slug>     # 예: feat/ship-skill — 커밋 주제에서 슬러그 도출
fi
```

이미 feature 브랜치(예: 워크트리 브랜치)면 그대로 둔다.

### 3. push → PR → squash merge

```bash
bash <cc-system>/.claude/skills/ship/scripts/ship.sh
# 또는 제목/본문을 직접 지정:
#   ship.sh --title "feat: …" --body "$(cat <<'EOF'
#   why / what
#   EOF
#   )"
```

`ship.sh` 가 하는 일: 프리플라이트(클린 트리·non-default 브랜치·base 대비
ahead 확인) → `git push -u origin HEAD` → 기존 PR 재사용 또는 `gh pr create`
→ `gh pr merge --squash`. 즉시 머지가 required check 로 막히면 **auto-merge
로 큐잉**하고 그 사실을 정직하게 보고한다. 머지 성공 후 원격 브랜치는 따로
삭제(best-effort)한다.

옵션: `--base <b>`, `--title`, `--body`, `--no-merge`(PR만), `--draft`.

### 4. 결과 보고 (정직하게)

`ship.sh` 의 마지막 출력으로 상태를 그대로 전한다:

- `✅ MERGED` — squash merge 완료.
- `⏳ auto-merge queued` — check 통과 후 자동 머지 예정. **"머지됨"이라고
  말하지 말 것.** check 가 끝나면 머지된다고 안내.
- auto-merge 불가(exit 3) — PR 은 열려 있음. check 통과를 기다렸다가
  (필요시 polling) `gh pr merge <url> --squash` 로 마무리.

## 여러 repo 출하

repo 마다 cwd 를 바꿔(또는 `git -C`) 1~4를 반복한다. `ship.sh` 는 cwd 의
repo 에 대해 동작하므로 repo-agnostic 하다. 한 repo 가 막혀도(검증 대기 등)
다른 repo 출하를 멈추지 말고, 막힌 항목은 상태를 기록하고 끝까지 진행한다.

## worktree 주의

`gh pr merge --delete-branch` 는 머지 후 로컬을 base 브랜치로 전환하려 하는데,
base 가 다른 worktree 에 체크아웃돼 있으면
(`fatal: '<base>' is already used by worktree …`) 실패한다. 그래서 `ship.sh`
는 `--delete-branch` 를 쓰지 않고, 머지 후 **원격 브랜치만 따로** 삭제하며
로컬 브랜치는 건드리지 않는다. 또한 머지 판정을 **exit code 가 아니라
`gh pr view` 의 실제 PR 상태**로 한다 — gh 가 머지 성공 후 로컬 단계에서
non-zero 로 끝나도 머지 실패로 오인하지 않는다.
