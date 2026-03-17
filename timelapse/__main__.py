import argparse
import sys
from datetime import datetime
from pathlib import Path

from .config import load_config
from .capture import run_capture
from .monitor import print_monitors
from .video import generate_video


def main():
    parser = argparse.ArgumentParser(
        prog="timelapse",
        description="개발 작업 타임랩스 녹화 도구",
    )
    parser.add_argument("--config", "-c", help="설정 파일 경로")

    sub = parser.add_subparsers(dest="command")

    # monitors
    sub.add_parser("monitors", help="연결된 모니터 목록 확인")

    # capture
    cap = sub.add_parser("capture", help="스크린 캡처 시작")
    cap.add_argument("--monitor", "-m", type=int, help="모니터 번호 (config 오버라이드)")

    # video
    vid = sub.add_parser("video", help="타임랩스 영상 생성")
    vid.add_argument("folder", help="세션 폴더명 (예: 2026-03-17_14-30-00) 또는 latest")

    args = parser.parse_args()

    config = load_config(args.config)

    if not args.command:
        # 인자 없이 실행하면 바로 캡처 시작
        run_capture(config)
        return

    if args.command == "monitors":
        print_monitors()

    elif args.command == "capture":
        if args.monitor is not None:
            config.capture.monitor = args.monitor
        run_capture(config)

    elif args.command == "video":
        base = Path(config.storage.base_path)
        if args.folder == "latest":
            # 가장 최근 세션 폴더
            folders = sorted([f for f in base.iterdir() if f.is_dir()], reverse=True)
            if not folders:
                print(f"오류: {base}에 세션 폴더가 없습니다.")
                sys.exit(1)
            folder = folders[0]
        else:
            folder = base / args.folder

        if not folder.exists():
            print(f"오류: 폴더가 없습니다: {folder}")
            sys.exit(1)

        output = folder.parent / f"{folder.name}.mp4"
        generate_video(str(folder), str(output), config.video.fps, config.video.crf)


if __name__ == "__main__":
    main()
