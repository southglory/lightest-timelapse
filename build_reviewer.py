"""Reviewer exe 빌드 스크립트. PyInstaller 사용."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent
vendor_ffmpeg = root / "vendor" / "ffmpeg.exe"

args = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", "reviewer",
    "--console",
    "--add-data", f"{root / 'config.yaml'};.",
]

if vendor_ffmpeg.exists():
    args.extend(["--add-binary", f"{vendor_ffmpeg};."])
    print(f"ffmpeg 내장: {vendor_ffmpeg}")
else:
    print("ffmpeg 미포함 (vendor/ffmpeg.exe 없음). 시스템 PATH의 ffmpeg을 사용합니다.")

args.append(str(root / "reviewer" / "run.py"))

print("빌드 시작...")
print(" ".join(args))
result = subprocess.run(args, cwd=str(root))
if result.returncode == 0:
    print(f"\n빌드 완료: {root / 'dist' / 'reviewer.exe'}")
else:
    print("\n빌드 실패")
    sys.exit(1)
