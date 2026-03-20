[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

Spulen Sie Ihren ganztägigen Bildschirm in einem 30-Sekunden-Video zurück.

**Ein Klick** startet die Aufnahme. Beim Beenden wird ein Zeitraffer-Video erstellt.

---

## Schnellstart

### 1. Herunterladen

Laden Sie `timelapse.exe` von den [Releases](https://github.com/southglory/lightest-timelapse/releases/latest) herunter. Das war's.

### 2. Ausführen

Doppelklick auf `timelapse.exe`.

```
캡처 시작 (모니터: 1, 간격: 15초, 품질: 50%)
유사 프레임 건너뛰기: ON (임계값: 1.5)
저장 경로: ./captures
세션 폴더: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 저장: 14-30-15.jpg (스킵:0)
  [14:30:30] #2 저장: 14-30-30.jpg (스킵:0)
  [14:30:45] 건너뜀 (diff=0.42) 저장:2 스킵:1
```

Wenn sich der Bildschirm nicht ändert, wird automatisch übersprungen. Spart Speicherplatz.

### 3. Beenden

Schließen Sie das Fenster oder drücken Sie `Ctrl+C`.

### 4. Video erstellen

```
timelapse.exe video latest
```

Die letzte Sitzung wird in ein MP4-Video umgewandelt. ffmpeg ist integriert — keine separate Installation erforderlich.

---

## Konfiguration

Legen Sie eine `config.yaml` neben die exe-Datei — sie wird automatisch geladen. Ohne Datei werden Standardwerte verwendet.

```yaml
capture:
  monitor: 1          # 0=alle, 1=Hauptmonitor, 2=Zweitmonitor...
  interval: 15        # Aufnahmeintervall (Sekunden)
  quality: 50         # JPEG-Qualität (1-100)
  skip_similar: true  # Unveränderte Frames überspringen
  diff_threshold: 1.5 # Empfindlichkeit (niedriger = empfindlicher)

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # Video-Wiedergabegeschwindigkeit
  crf: 23             # Videoqualität (niedriger = höhere Qualität)
  auto_generate: true # Video automatisch beim Beenden erstellen
```

Mit `auto_generate: true` wird beim Beenden der Aufnahme automatisch ein Video erstellt.

---

## Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `timelapse.exe` | Aufnahme sofort starten |
| `timelapse.exe monitors` | Monitorliste anzeigen |
| `timelapse.exe capture -m 2` | Monitor 2 aufnehmen |
| `timelapse.exe video latest` | Video der letzten Sitzung erstellen |
| `timelapse.exe video 2026-03-17_14-30-00` | Video einer bestimmten Sitzung erstellen |

---

## Speicherverbrauch

| Element | Wert |
|---------|------|
| 1 Screenshot | ~150KB |
| 8 Stunden Arbeit (ohne unveränderte Frames) | **0,2~0,5GB** |
| 24 Stunden durchgehend | ~0,8GB |

Da unveränderte Bildschirminhalte nicht gespeichert werden, ist der tatsächliche Verbrauch geringer.

---

## Reviewer — Werkzeug zur Aufnahmeprüfung

Ein Werkzeug zum Überprüfen aufgenommener Bilder, Verdecken sensibler Informationen und Erstellen bearbeiteter Videos.

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- Schnelles Durchsehen im Raster + Löschen
- Vorlagen für wiederkehrende Maskierungsbereiche
- Mosaik/Weichzeichner/Abdeckung/Stift-Bearbeitung
- Videoerzeugung mit angewandten Bearbeitungen

Detaillierte Anweisungen finden Sie in der [Reviewer README](reviewer/README.md).

---

## Aus dem Quellcode bauen

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # ffmpeg herunterladen

python build.py                 # timelapse.exe bauen
python build_reviewer.py        # reviewer.exe bauen
```

## License

MIT
