"""CLI 진입점 — python -m video_editor [file.mp4]"""

import sys

from .app import App


def main():
    video_path = sys.argv[1] if len(sys.argv) >= 2 else None
    app = App(video_path)
    app.run()


if __name__ == "__main__":
    main()
