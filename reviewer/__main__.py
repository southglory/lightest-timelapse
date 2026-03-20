import sys
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from .app import App


def main():
    if len(sys.argv) < 2:
        # 인자 없으면 폴더 선택 다이얼로그
        root = tk.Tk()
        root.withdraw()
        folder = filedialog.askdirectory(title="세션 폴더를 선택하세요")
        root.destroy()
        if not folder:
            sys.exit(0)
        arg = folder
    else:
        arg = sys.argv[1]

    if arg == "latest":
        # config.yaml에서 base_path 읽기
        config_path = Path(__file__).parent.parent / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            base = Path(cfg.get("storage", {}).get("base_path", "./captures"))
        else:
            base = Path("./captures")

        folders = sorted([f for f in base.iterdir() if f.is_dir()], reverse=True)
        if not folders:
            print(f"오류: {base}에 세션 폴더가 없습니다.")
            sys.exit(1)
        session_dir = folders[0]
    else:
        session_dir = Path(arg)

    if not session_dir.exists():
        print(f"오류: 폴더가 없습니다: {session_dir}")
        sys.exit(1)

    app = App(session_dir)
    app.run()


if __name__ == "__main__":
    main()
