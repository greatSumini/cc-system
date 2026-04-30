---
name: discord-message
description: 사용자에게 Discord DM을 전송한다. 메세지 내용을 입력받아 봇을 통해 개인 메세지를 보낸다.
user-invocable: true
argument-hint: "[보낼 메세지 내용]"
allowed-tools: Bash
---

# discord-message Skill

Discord 봇을 통해 사용자에게 DM을 전송하는 스킬이다.

## 파일 경로

- 설정 파일: `.claude/skills/discord-message/config.json`
- 전송 스크립트: `.claude/skills/discord-message/scripts/send_message.py`

## 실행 절차

### Step 1. 메세지 내용 확인

사용자 입력에서 보낼 메세지 내용을 파악한다. 메세지가 없으면 어떤 내용을 보낼지 묻는다.

### Step 2. Discord DM 전송

다음 명령으로 메세지를 전송한다:

```bash
python3 .claude/skills/discord-message/scripts/send_message.py \
  .claude/skills/discord-message/config.json \
  "<메세지 내용>"
```

출력:
```json
{ "success": true, "message_id": "..." }
```

또는 실패 시:
```json
{ "error": "HTTP 401: ..." }
```

### Step 3. 결과 보고

- 성공 시: "Discord DM을 전송했습니다." 라고 간결하게 보고한다.
- 실패 시: error 내용을 사용자에게 알리고 원인을 설명한다.
