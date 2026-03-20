[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

Rewind your entire workday into a 30-second video.

**One click** to start recording. Close it and you get a timelapse video.

---

## Quick Start

### 1. Download

Grab `timelapse.exe` from [Releases](https://github.com/southglory/lightest-timelapse/releases/latest). That's it.

### 2. Run

Double-click `timelapse.exe`.

```
Capture started (monitor: 1, interval: 15s, quality: 50%)
Skip similar frames: ON (threshold: 1.5)
Save path: ./captures
Session folder: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 saved: 14-30-15.jpg (skipped:0)
  [14:30:30] #2 saved: 14-30-30.jpg (skipped:0)
  [14:30:45] skipped (diff=0.42) saved:2 skipped:1
```

If the screen hasn't changed, it's automatically skipped. Saves storage.

### 3. Stop

Close the window or press `Ctrl+C`.

### 4. Create Video

```
timelapse.exe video latest
```

The most recent session is converted to an MP4 video. ffmpeg is built-in — no separate installation required.

---

## Configuration

Place a `config.yaml` next to the exe and it will be loaded automatically. If absent, defaults are used.

```yaml
capture:
  monitor: 1          # 0=all, 1=primary, 2=secondary...
  interval: 15        # capture interval (seconds)
  quality: 50         # JPEG quality (1-100)
  skip_similar: true  # skip unchanged frames
  diff_threshold: 1.5 # sensitivity (lower = more sensitive)

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # video playback speed
  crf: 23             # video quality (lower = higher quality)
  auto_generate: true # auto-generate video on exit
```

With `auto_generate: true`, a video is automatically generated when capture ends.

---

## Commands

| Command | Description |
|---------|-------------|
| `timelapse.exe` | Start capturing immediately |
| `timelapse.exe monitors` | List available monitors |
| `timelapse.exe capture -m 2` | Capture monitor #2 |
| `timelapse.exe video latest` | Generate video from latest session |
| `timelapse.exe video 2026-03-17_14-30-00` | Generate video from a specific session |

---

## Storage

| Item | Size |
|------|------|
| 1 screenshot | ~150KB |
| 8-hour workday (excluding unchanged frames) | **0.2–0.5GB** |
| 24-hour continuous | ~0.8GB |

Unchanged screens are not saved, so actual usage is typically lower.

---

## Reviewer — Capture Review Tool

A tool for reviewing captured images, masking sensitive information, and producing edited videos.

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- Quickly browse and delete in grid view
- Batch-mask recurring areas with templates
- Mosaic / blur / cover / pen editing
- Generate video with edits applied

For detailed usage, see the [Reviewer README](reviewer/README.md).

---

## Building from Source

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # download ffmpeg

python build.py                 # build timelapse.exe
python build_reviewer.py        # build reviewer.exe
```

## License

MIT
