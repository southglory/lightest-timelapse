[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

Rebobina en un vídeo de 30 segundos todo lo que trabajaste en la pantalla durante el día.

Con **un solo clic** empiezas a grabar. Al cerrar, se genera el vídeo timelapse.

---

## Inicio rápido

### 1. Descarga

Descarga `timelapse.exe` desde [Releases](https://github.com/southglory/lightest-timelapse/releases/latest). Eso es todo.

### 2. Ejecución

Haz doble clic en `timelapse.exe`.

```
캡처 시작 (모니터: 1, 간격: 15초, 품질: 50%)
유사 프레임 건너뛰기: ON (임계값: 1.5)
저장 경로: ./captures
세션 폴더: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 저장: 14-30-15.jpg (스킵:0)
  [14:30:30] #2 저장: 14-30-30.jpg (스킵:0)
  [14:30:45] 건너뜀 (diff=0.42) 저장:2 스킵:1
```

Si la pantalla no cambia, se omite automáticamente. Ahorro de espacio.

### 3. Finalización

Cierra la ventana o pulsa `Ctrl+C`.

### 4. Crear vídeo

```
timelapse.exe video latest
```

La sesión más reciente se convierte en un vídeo MP4. ffmpeg viene integrado — no requiere instalación adicional.

---

## Configuración

Coloca un archivo `config.yaml` junto al exe y se leerá automáticamente. Si no existe, se usarán los valores predeterminados.

```yaml
capture:
  monitor: 1          # 0=todos, 1=principal, 2=secundario...
  interval: 15        # Intervalo de captura (segundos)
  quality: 50         # Calidad JPEG (1-100)
  skip_similar: true  # Omitir fotogramas sin cambios
  diff_threshold: 1.5 # Sensibilidad (menor = más sensible)

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # Velocidad de reproducción del vídeo
  crf: 23             # Calidad del vídeo (menor = mayor calidad)
  auto_generate: true # Generar vídeo automáticamente al finalizar
```

Si configuras `auto_generate: true`, el vídeo se generará automáticamente al terminar la captura.

---

## Comandos

| Comando | Descripción |
|------|------|
| `timelapse.exe` | Iniciar captura directamente |
| `timelapse.exe monitors` | Ver lista de monitores |
| `timelapse.exe capture -m 2` | Capturar el monitor 2 |
| `timelapse.exe video latest` | Generar vídeo de la sesión más reciente |
| `timelapse.exe video 2026-03-17_14-30-00` | Generar vídeo de una sesión específica |

---

## Espacio en disco

| Elemento | Valor |
|------|-----|
| 1 captura de pantalla | ~150KB |
| 8 horas de trabajo (excluyendo fotogramas sin cambios) | **0.2~0.5GB** |
| 24 horas continuas | ~0.8GB |

Como no se guardan los fotogramas sin cambios en la pantalla, el espacio real utilizado es menor.

---

## Reviewer — Herramienta de revisión de capturas

Herramienta para revisar las imágenes capturadas, ocultar información sensible y crear vídeos editados.

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- Vista rápida en cuadrícula + eliminación
- Enmascaramiento por lotes de posiciones repetidas con plantillas
- Edición con mosaico/desenfoque/ocultación/lápiz
- Generación de vídeo con las ediciones aplicadas

Para instrucciones detalladas, consulta el [README de Reviewer](reviewer/README.md).

---

## Compilar desde el código fuente

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # Descargar ffmpeg

python build.py                 # Compilar timelapse.exe
python build_reviewer.py        # Compilar reviewer.exe
```

## License

MIT
