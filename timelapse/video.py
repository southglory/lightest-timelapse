import subprocess
import sys
import tempfile
from pathlib import Path


def _get_ffmpeg() -> str:
    """내장 ffmpeg 경로 반환. 없으면 시스템 PATH의 ffmpeg 사용."""
    if getattr(sys, "frozen", False):
        # PyInstaller exe에서 실행 중
        bundled = Path(sys._MEIPASS) / "ffmpeg.exe"
    else:
        bundled = Path(__file__).parent.parent / "vendor" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"


def generate_video(date_folder: str, output_path: str, fps: int = 30, crf: int = 23):
    """날짜 폴더의 JPEG 이미지들로 타임랩스 영상 생성."""
    folder = Path(date_folder)
    files = sorted(folder.glob("*.jpg"))

    if not files:
        print(f"오류: {folder}에 이미지가 없습니다.")
        return

    # Windows 호환: concat demuxer용 파일 목록 생성
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        list_file = f.name
        for img in files:
            # ffmpeg concat 형식: file 'path'
            f.write(f"file '{img.absolute()}'\n")
            f.write(f"duration {1/fps}\n")

    try:
        cmd = [
            _get_ffmpeg(), "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"영상 생성 완료: {output_path}")
            print(f"  이미지 {len(files)}장 → {fps}fps 영상")
        else:
            print(f"오류: ffmpeg 실행 실패")
            print(result.stderr)
    finally:
        Path(list_file).unlink(missing_ok=True)
