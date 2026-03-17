import sys
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class CaptureConfig:
    monitor: int = 1
    interval: int = 15
    quality: int = 50
    skip_similar: bool = True       # 변화 없는 프레임 건너뛰기
    diff_threshold: float = 1.5     # 픽셀 차이 평균 임계값 (0-255)


@dataclass
class StorageConfig:
    base_path: str = "./captures"


@dataclass
class VideoConfig:
    fps: int = 30
    crf: int = 23
    auto_generate: bool = False


@dataclass
class Config:
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    video: VideoConfig = field(default_factory=VideoConfig)


def load_config(config_path: str | None = None) -> Config:
    """YAML 설정 파일 로드. 파일이 없으면 기본값 사용."""
    if config_path is None:
        if getattr(sys, "frozen", False):
            # PyInstaller exe: exe 옆의 config.yaml → 내장 config.yaml 순서로 탐색
            exe_dir = Path(sys.executable).parent
            config_path = exe_dir / "config.yaml"
            if not config_path.exists():
                config_path = Path(sys._MEIPASS) / "config.yaml"
        else:
            config_path = Path(__file__).parent.parent / "config.yaml"
    else:
        config_path = Path(config_path)

    config = Config()

    if not config_path.exists():
        return config

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if "capture" in data:
        for k, v in data["capture"].items():
            if hasattr(config.capture, k):
                setattr(config.capture, k, v)

    if "storage" in data:
        for k, v in data["storage"].items():
            if hasattr(config.storage, k):
                setattr(config.storage, k, v)

    if "video" in data:
        for k, v in data["video"].items():
            if hasattr(config.video, k):
                setattr(config.video, k, v)

    return config
