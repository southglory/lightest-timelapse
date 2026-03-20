[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

一日中作業した画面を30秒の動画で巻き戻してみましょう。

**ワンクリック**で録画開始。終了すればタイムラプス動画が生成されます。

---

## クイックスタート

### 1. ダウンロード

[Releases](https://github.com/southglory/lightest-timelapse/releases/latest)から`timelapse.exe`をダウンロードしてください。以上です。

### 2. 実行

`timelapse.exe`をダブルクリック。

```
キャプチャ開始 (モニター: 1, 間隔: 15秒, 品質: 50%)
類似フレームスキップ: ON (しきい値: 1.5)
保存先: ./captures
セッションフォルダ: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 保存: 14-30-15.jpg (スキップ:0)
  [14:30:30] #2 保存: 14-30-30.jpg (スキップ:0)
  [14:30:45] スキップ (diff=0.42) 保存:2 スキップ:1
```

画面に変化がなければ自動的にスキップします。容量の節約になります。

### 3. 終了

ウィンドウを閉じるか`Ctrl+C`。

### 4. 動画の作成

```
timelapse.exe video latest
```

最新のセッションがMP4動画に変換されます。ffmpeg内蔵 — 別途インストール不要。

---

## 設定

exe の隣に`config.yaml`を置くと自動的に読み込まれます。なければデフォルト値で動作します。

```yaml
capture:
  monitor: 1          # 0=全体, 1=メインモニター, 2=サブ...
  interval: 15        # キャプチャ間隔 (秒)
  quality: 50         # JPEG 品質 (1-100)
  skip_similar: true  # 変化のないフレームをスキップ
  diff_threshold: 1.5 # 感度 (低いほど敏感)

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # 動画の再生速度
  crf: 23             # 動画品質 (低いほど高画質)
  auto_generate: true # 終了時に自動で動画を生成
```

`auto_generate: true`に設定すると、キャプチャ終了時に動画まで自動生成されます。

---

## コマンド

| コマンド | 説明 |
|------|------|
| `timelapse.exe` | すぐにキャプチャ開始 |
| `timelapse.exe monitors` | モニター一覧を確認 |
| `timelapse.exe capture -m 2` | モニター2をキャプチャ |
| `timelapse.exe video latest` | 最新セッションの動画を生成 |
| `timelapse.exe video 2026-03-17_14-30-00` | 特定セッションの動画を生成 |

---

## 容量

| 項目 | 値 |
|------|-----|
| スクリーンショット1枚 | ~150KB |
| 8時間作業 (変化のないフレームを除く) | **0.2~0.5GB** |
| 24時間連続 | ~0.8GB |

画面に変化がなければ保存しないため、実際の容量はさらに少なくなります。

---

## Reviewer — キャプチャ検収ツール

キャプチャした画像を検収し、機密情報をマスクし、編集済みの動画を作成するツール。

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- グリッドで素早く確認＋削除
- テンプレートで繰り返し位置を一括マスク
- モザイク/ぼかし/マスク/ペン編集
- 編集を適用した動画を生成

詳しい使い方は[Reviewer README](reviewer/README.md)をご参照ください。

---

## ソースからビルド

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # ffmpeg ダウンロード

python build.py                 # timelapse.exe ビルド
python build_reviewer.py        # reviewer.exe ビルド
```

## License

MIT
