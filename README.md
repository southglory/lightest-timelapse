[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

![GitHub stars](https://img.shields.io/github/stars/southglory/lightest-timelapse?style=social)
![GitHub forks](https://img.shields.io/github/forks/southglory/lightest-timelapse?style=social)
![GitHub license](https://img.shields.io/github/license/southglory/lightest-timelapse)

하루 종일 작업한 화면을 30초 영상으로 되감아 보세요.

**클릭 한 번**이면 녹화 시작. 끄면 타임랩스 영상이 생깁니다.

---

## 빠른 시작

### 1. 다운로드

[Releases](https://github.com/southglory/lightest-timelapse/releases/latest)에서 exe를 받으세요.

| 파일 | 용도 |
|------|------|
| `timelapse.exe` | 화면 캡처 |
| `reviewer.exe` | 캡처 검수 + 영상 생성 |
| `video_editor.exe` | 영상 후처리 (블러/크롭 등) |

### 2. 실행

`timelapse.exe` 더블클릭.

```
캡처 시작 (모니터: 1, 간격: 15초, 품질: 50%)
유사 프레임 건너뛰기: ON (임계값: 1.5)
저장 경로: ./captures
세션 폴더: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 저장: 14-30-15.jpg (스킵:0)
  [14:30:30] #2 저장: 14-30-30.jpg (스킵:0)
  [14:30:45] 건너뜀 (diff=0.42) 저장:2 스킵:1
```

화면이 안 바뀌면 자동으로 건너뜁니다. 용량 절약.

### 3. 종료

창을 닫거나 `Ctrl+C`.

### 4. 영상 만들기

```
timelapse.exe video latest
```

가장 최근 세션이 MP4 영상으로 변환됩니다. ffmpeg 내장 — 별도 설치 불필요.

---

## 설정

exe 옆에 `config.yaml`을 두면 자동으로 읽습니다. 없으면 기본값으로 동작.

```yaml
capture:
  monitor: 1          # 0=전체, 1=주모니터, 2=보조...
  interval: 15        # 캡처 간격 (초)
  quality: 50         # JPEG 품질 (1-100)
  skip_similar: true  # 변화 없는 프레임 건너뛰기
  diff_threshold: 1.5 # 민감도 (낮을수록 민감)

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # 영상 재생 속도
  crf: 23             # 영상 품질 (낮을수록 고화질)
  auto_generate: true # 종료 시 자동으로 영상 생성
```

`auto_generate: true`로 설정하면 캡처 종료 시 영상까지 자동 생성됩니다.

---

## 명령어

| 명령 | 설명 |
|------|------|
| `timelapse.exe` | 바로 캡처 시작 |
| `timelapse.exe monitors` | 모니터 목록 확인 |
| `timelapse.exe capture -m 2` | 2번 모니터 캡처 |
| `timelapse.exe video latest` | 최근 세션 영상 생성 |
| `timelapse.exe video 2026-03-17_14-30-00` | 특정 세션 영상 생성 |

---

## 용량

| 항목 | 값 |
|------|-----|
| 스크린샷 1장 | ~150KB |
| 8시간 작업 (변화 없는 프레임 제외) | **0.2~0.5GB** |
| 24시간 연속 | ~0.8GB |

화면 변화가 없으면 저장하지 않으므로, 실제 용량은 더 적습니다.

---

## Reviewer — 캡처 검수 도구

캡처한 이미지를 검수하고, 민감 정보를 가리고, 편집된 영상을 만드는 도구.

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- 그리드에서 빠르게 훑어보기 + 삭제
- 템플릿으로 반복 위치 일괄 마스킹
- 모자이크/블러/가리기/펜 편집
- 편집 적용된 영상 생성

자세한 사용법은 [Reviewer README](reviewer/README.md)를 참고하세요.

---

## Video Editor — 영상 후처리 도구

이미 생성된 MP4 영상에서 특정 영역을 블러/모자이크/가리기/크롭 처리하는 도구.

```
video_editor.exe video.mp4
```

- 첫 프레임에서 영역 지정 (드래그로 사각형 추가)
- 블러 / 모자이크 / 채우기(검정) / 크롭 선택
- 타임라인 슬라이더로 프레임 확인
- 영역 이동, 리사이즈, 삭제
- ffmpeg 기반 인코딩으로 새 MP4 저장

---

## 소스에서 빌드

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # ffmpeg 다운로드

python build.py                 # timelapse.exe 빌드
python build_reviewer.py        # reviewer.exe 빌드
python build_editor.py          # video_editor.exe 빌드
```

## Support

이 프로젝트가 도움이 되셨다면 star를 남겨주세요!

## License

MIT

## Star History

<a href="https://star-history.com/#southglory/lightest-timelapse&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=southglory/lightest-timelapse&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=southglory/lightest-timelapse&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=southglory/lightest-timelapse&type=Date" />
 </picture>
</a>
