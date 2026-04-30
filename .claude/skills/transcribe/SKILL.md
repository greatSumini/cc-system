---
name: transcribe
description: 로컬 오디오 파일(m4a 등)을 한국어로 전사하는 skill. "전사해줘", "받아쓰기", "음성 파일 텍스트로", "transcribe", "음성 받아적어줘", "녹음 파일 변환" 등 오디오 → 텍스트 변환 요청에 트리거된다.
---

# transcribe — 로컬 오디오 전사

Apple Silicon 네이티브 `mlx-whisper`(Whisper large-v3-turbo)로 로컬 오디오 파일을 한국어 텍스트로 전사한다.

## 플로우

### 1. 파일 경로 확인

사용자가 제공한 오디오 파일 경로를 확인한다. 상대경로면 현재 작업 디렉토리 기준 절대경로로 변환한다.

지원 포맷: m4a 기본, mp3/wav/mp4 등 ffmpeg이 디코딩 가능한 포맷 모두 동작.

### 2. 도메인 힌트 구성

현재 대화 맥락에서 다음 카테고리를 적극적으로 끌어모아 한국어 한두 문장으로 조합해 `--initial-prompt`에 넣는다. **맥락이 있으면 가능한 한 풍부하게** 채운다(없는 정보를 지어내지는 않는다).

수집할 카테고리:

- 참석자/화자 이름 (가능하면 전부)
- 회사명·제품명·서비스명
- 자주 쓰일 영문 약어·전문용어의 **한글 표기 예시** (예: "토스페이먼츠를 'TPay'로도 부른다", "API를 '에이피아이'로 발음한다")
- 도메인 키워드 5~20개

예시:

- 대화에서 "최수민, 바이브마피아클럽, 구글, B2B 제안서"가 언급되었다면
  - `--initial-prompt "이 녹음은 바이브마피아클럽 최수민과 구글의 B2B 제안 회의다. 등장 용어: 바이브마피아클럽(VMC), 구글, B2B 제안서, 견적, 라이선스."`

맥락이 전혀 없으면 이 단계는 건너뛴다. 단, 사용자에게 "전사 품질을 올리려면 등장 인물·고유명사를 알려주세요"라고 한 번 권유한다.

### 3. 오디오 전처리

작은 목소리 화자 누락과 볼륨 편차로 인한 환각을 줄이기 위해 `ffmpeg loudnorm`으로 정규화한 뒤 전사한다. 이 단계는 **항상 수행**한다(추가 비용 거의 없음, 효과 큼).

```bash
NORMALIZED="$(mktemp -t transcribe_norm).wav"
ffmpeg -y -i "<AUDIO_PATH>" \
  -af loudnorm=I=-16:TP=-1.5:LRA=11 \
  -ar 16000 -ac 1 \
  "$NORMALIZED"
```

- `-ar 16000 -ac 1`: Whisper 내부 표현(16kHz 모노)에 맞춰 미리 변환. 모델 입력 변환 비용 절감.
- 사용자가 "잡음이 심하다", "BGM 깔려 있다"고 명시한 경우에만 추가로 `demucs`(음성 분리) 또는 `arnndn`(RNNoise) 단계를 적용한다. 기본 플로우에는 넣지 않는다 — 모델 다운로드/실행 비용이 크고 깨끗한 녹음에선 오히려 음성을 깎는다.

### 4. 전사 실행

임시 출력 디렉토리에 `txt` 포맷으로 내보낸다. 환각 방지 플래그를 기본 적용한다.

```bash
OUTDIR="$(mktemp -d -t transcribe)"
ORIG_BASE="$(basename "<AUDIO_PATH>")"; ORIG_BASE="${ORIG_BASE%.*}"
mlx_whisper \
  --model mlx-community/whisper-large-v3-turbo \
  --language ko \
  --output-format txt \
  --output-dir "$OUTDIR" \
  --output-name "$ORIG_BASE" \
  --condition-on-previous-text False \
  --temperature 0 \
  --no-speech-threshold 0.6 \
  --verbose False \
  [--initial-prompt "<DOMAIN_HINT>"] \
  "$NORMALIZED"
```

환각 방지 플래그 의도:

- `--condition-on-previous-text False`: 한 번 잘못 인식한 텍스트가 뒤 구간으로 전염되는 문제 차단. 회의 녹음에선 거의 항상 이득.
- `--temperature 0`: 샘플링 무작위성 제거. 동일 입력에 동일 출력 보장.
- `--no-speech-threshold 0.6`: 무음/BGM 구간에서 "구독과 좋아요 부탁드립니다" 같은 환각 생성 방지. 기본값(0.6)을 명시적으로 박아둔다.

기타:

- 첫 실행 시 모델(~1.5GB)이 HuggingFace에서 자동 다운로드된다. 사용자에게 미리 알린다.
- 60분 오디오 기준 M 시리즈 Mac에서 3~8분 소요 예상.
- 출력 파일명은 `{원본 오디오 basename}.txt` 형태로 `$OUTDIR` 아래에 생성된다 (`--output-name` 덕분에 정규화 임시파일 이름이 새지 않음).

### 5. 결과 미리보기 + 저장 위치 확인

생성된 txt 파일을 읽어 사용자에게 미리보기를 제시한다 (긴 경우 앞/뒤 일부만).

그다음 **저장 위치를 사용자에게 반드시 질의한다**. 저장 위치 후보:

- 원본 오디오 파일과 같은 디렉토리에 `{basename}.txt`
- `logs/transcripts/YYYY-MM-DD_{slug}.md` (frontmatter 포함)
- `meeting-logs/YYMMDD_{title}.md` (전사 후 회의록 가공까지 요청한 경우)
- `projects/{project_id}/meeting-logs/...` (프로젝트 관련 녹음)
- 저장하지 않고 화면 출력만

사용자가 저장 위치를 지정하면 해당 위치로 이동(`mv`) 또는 복사(`cp`)한다. 마크다운으로 저장하는 경우 `## Document Frontmatter` 규칙에 따른 frontmatter를 추가한다.

### 6. 정리

임시 출력 디렉토리(`$OUTDIR`)와 정규화된 임시 오디오 파일(`$NORMALIZED`)은 저장 완료 후 삭제한다.

```bash
rm -rf "$OUTDIR" "$NORMALIZED"
```

## 화자 분리 요청 처리

사용자가 "화자 구분", "누가 말했는지", "speaker diarization" 등을 명시적으로 요청하면:

> 현재 skill은 화자 분리를 지원하지 않습니다. 추가하려면 `pyannote.audio` + HuggingFace 토큰 설정이 필요합니다. 진행하시겠습니까?

라고 안내하고 사용자 결정을 기다린다. 임의로 진행하지 않는다.

## Invariants

- 언어는 **한국어(ko) 고정**. 다른 언어 요청 시 사용자에게 확인 후 `--language` 변경.
- 모델은 기본 `mlx-community/whisper-large-v3-turbo`. 품질 불만 시에만 `whisper-large-v3` (turbo 아님, 더 느리고 품질 살짝 높음) 로 교체.
- 결과 저장 위치는 **항상 사용자에게 확인**한다. 임의로 리포지토리 안에 커밋될 파일을 만들지 않는다.
- 원본 오디오 파일은 절대 수정/삭제하지 않는다.

## 의존성

사전 설치 완료된 상태를 가정한다:

- `mlx_whisper` (`uv tool install mlx-whisper`)
- `ffmpeg` (`brew install ffmpeg`)

둘 중 하나라도 없으면 사용자에게 설치 필요함을 알리고 중단한다.
