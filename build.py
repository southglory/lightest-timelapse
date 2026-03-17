"""타임랩스 도구 exe 빌드 스크립트. PyInstaller 사용."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent
vendor_ffmpeg = root / "vendor" / "ffmpeg.exe"

if not vendor_ffmpeg.exists():
    print(f"오류: {vendor_ffmpeg} 파일이 없습니다.")
    sys.exit(1)

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", "timelapse",
    "--console",
    "--add-binary", f"{vendor_ffmpeg};.",
    "--add-data", f"{root / 'config.yaml'};.",
    str(root / "run.py"),
]

print("빌드 시작...")
print(" ".join(cmd))
result = subprocess.run(cmd, cwd=str(root))
if result.returncode == 0:
    print(f"\n빌드 완료: {root / 'dist' / 'timelapse.exe'}")
else:
    print("\n빌드 실패")
    sys.exit(1)
