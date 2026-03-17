"""ffmpeg essentials 빌드를 vendor/ 폴더에 다운로드합니다."""
import io
import zipfile
import urllib.request
from pathlib import Path

URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
VENDOR = Path(__file__).parent / "vendor"


def main():
    VENDOR.mkdir(exist_ok=True)
    dest = VENDOR / "ffmpeg.exe"

    if dest.exists():
        print(f"이미 존재합니다: {dest}")
        return

    print(f"다운로드 중: {URL}")
    data = urllib.request.urlopen(URL).read()
    print(f"다운로드 완료 ({len(data) // 1024 // 1024}MB), 압축 해제 중...")

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith("bin/ffmpeg.exe"):
                with z.open(name) as src:
                    dest.write_bytes(src.read())
                print(f"완료: {dest}")
                return

    print("오류: ffmpeg.exe를 찾을 수 없습니다.")


if __name__ == "__main__":
    main()
