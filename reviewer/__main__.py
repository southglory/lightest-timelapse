import sys
from pathlib import Path

from .app import App


def main():
    if len(sys.argv) < 2:
        print("사용법: python -m reviewer <세션폴더 경로 또는 latest>")
        sys.exit(1)

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
