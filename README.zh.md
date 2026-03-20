[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

将一整天的工作画面倒带回放，浓缩成30秒视频。

**只需一键**即可开始录制。关闭后自动生成延时摄影视频。

---

## 快速开始

### 1. 下载

从 [Releases](https://github.com/southglory/lightest-timelapse/releases/latest) 下载 `timelapse.exe` 即可。

### 2. 运行

双击 `timelapse.exe`。

```
캡처 시작 (모니터: 1, 간격: 15초, 품질: 50%)
유사 프레임 건너뛰기: ON (임계값: 1.5)
저장 경로: ./captures
세션 폴더: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 저장: 14-30-15.jpg (스킵:0)
  [14:30:30] #2 저장: 14-30-30.jpg (스킵:0)
  [14:30:45] 건너뜀 (diff=0.42) 저장:2 스킵:1
```

画面没有变化时会自动跳过，节省存储空间。

### 3. 退出

关闭窗口或按 `Ctrl+C`。

### 4. 生成视频

```
timelapse.exe video latest
```

最近一次会话将被转换为 MP4 视频。内置 ffmpeg，无需另行安装。

---

## 配置

在 exe 旁边放置 `config.yaml`，程序会自动读取。没有配置文件则使用默认值。

```yaml
capture:
  monitor: 1          # 0=全部, 1=主显示器, 2=副显示器...
  interval: 15        # 截图间隔（秒）
  quality: 50         # JPEG 质量（1-100）
  skip_similar: true  # 跳过无变化的帧
  diff_threshold: 1.5 # 灵敏度（越低越灵敏）

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # 视频播放速度
  crf: 23             # 视频质量（越低画质越高）
  auto_generate: true # 退出时自动生成视频
```

将 `auto_generate: true` 设置后，截图结束时会自动生成视频。

---

## 命令

| 命令 | 说明 |
|------|------|
| `timelapse.exe` | 直接开始截图 |
| `timelapse.exe monitors` | 查看显示器列表 |
| `timelapse.exe capture -m 2` | 截取第2个显示器 |
| `timelapse.exe video latest` | 生成最近会话的视频 |
| `timelapse.exe video 2026-03-17_14-30-00` | 生成指定会话的视频 |

---

## 存储空间

| 项目 | 大小 |
|------|------|
| 单张截图 | ~150KB |
| 8小时工作（排除无变化帧） | **0.2~0.5GB** |
| 24小时连续 | ~0.8GB |

画面没有变化时不会保存，因此实际占用空间更少。

---

## Reviewer — 截图审查工具

用于审查截取的图片、遮盖敏感信息并生成编辑后视频的工具。

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- 在网格视图中快速浏览并删除
- 使用模板批量遮盖固定位置
- 马赛克/模糊/遮挡/画笔编辑
- 生成应用编辑后的视频

详细使用方法请参阅 [Reviewer README](reviewer/README.md)。

---

## 从源码构建

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # 下载 ffmpeg

python build.py                 # 构建 timelapse.exe
python build_reviewer.py        # 构建 reviewer.exe
```

## License

MIT
