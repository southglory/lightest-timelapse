[English](README.en.md) | [한국어](README.md) | [中文](README.zh.md) | [日本語](README.ja.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Español](README.es.md)

# Lightest Timelapse

Revoyez en 30 secondes tout ce que vous avez fait sur votre écran pendant la journée.

**Un seul clic** pour lancer l'enregistrement. Fermez-le et vous obtenez une vidéo timelapse.

---

## Démarrage rapide

### 1. Téléchargement

Téléchargez `timelapse.exe` depuis les [Releases](https://github.com/southglory/lightest-timelapse/releases/latest). C'est tout.

### 2. Exécution

Double-cliquez sur `timelapse.exe`.

```
캡처 시작 (모니터: 1, 간격: 15초, 품질: 50%)
유사 프레임 건너뛰기: ON (임계값: 1.5)
저장 경로: ./captures
세션 폴더: ./captures/2026-03-17_14-30-00

  [14:30:15] #1 저장: 14-30-15.jpg (스킵:0)
  [14:30:30] #2 저장: 14-30-30.jpg (스킵:0)
  [14:30:45] 건너뜀 (diff=0.42) 저장:2 스킵:1
```

Les images identiques sont automatiquement ignorées. Économie d'espace.

### 3. Arrêt

Fermez la fenêtre ou appuyez sur `Ctrl+C`.

### 4. Création de la vidéo

```
timelapse.exe video latest
```

La session la plus récente est convertie en vidéo MP4. ffmpeg est intégré — aucune installation supplémentaire requise.

---

## Configuration

Placez un fichier `config.yaml` à côté de l'exe et il sera lu automatiquement. Sans ce fichier, les valeurs par défaut sont utilisées.

```yaml
capture:
  monitor: 1          # 0=tous, 1=principal, 2=secondaire...
  interval: 15        # Intervalle de capture (secondes)
  quality: 50         # Qualité JPEG (1-100)
  skip_similar: true  # Ignorer les images sans changement
  diff_threshold: 1.5 # Sensibilité (plus bas = plus sensible)

storage:
  base_path: "D:/timelapse"

video:
  fps: 30             # Vitesse de lecture de la vidéo
  crf: 23             # Qualité vidéo (plus bas = meilleure qualité)
  auto_generate: true # Générer automatiquement la vidéo à l'arrêt
```

Avec `auto_generate: true`, la vidéo est générée automatiquement à la fin de la capture.

---

## Commandes

| Commande | Description |
|------|------|
| `timelapse.exe` | Lancer la capture immédiatement |
| `timelapse.exe monitors` | Afficher la liste des moniteurs |
| `timelapse.exe capture -m 2` | Capturer le moniteur n°2 |
| `timelapse.exe video latest` | Générer la vidéo de la dernière session |
| `timelapse.exe video 2026-03-17_14-30-00` | Générer la vidéo d'une session spécifique |

---

## Espace disque

| Élément | Valeur |
|------|-----|
| 1 capture d'écran | ~150 Ko |
| 8 heures de travail (images sans changement exclues) | **0,2~0,5 Go** |
| 24 heures en continu | ~0,8 Go |

Les images sont ignorées lorsque l'écran ne change pas, donc l'espace réel utilisé est encore moindre.

---

## Reviewer — Outil de vérification des captures

Un outil pour vérifier les images capturées, masquer les informations sensibles et produire des vidéos éditées.

```
reviewer.exe D:\timelapse\2026-03-20_14-30-00
```

- Parcours rapide en grille + suppression
- Masquage par lot des zones récurrentes via des modèles
- Édition par mosaïque/flou/masquage/stylo
- Génération de vidéo avec les modifications appliquées

Pour plus de détails, consultez le [README de Reviewer](reviewer/README.md).

---

## Compilation depuis les sources

```bash
pip install -r requirements.txt
python download_ffmpeg.py       # ffmpeg 다운로드

python build.py                 # timelapse.exe 빌드
python build_reviewer.py        # reviewer.exe 빌드
```

## License

MIT
