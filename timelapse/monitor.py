import mss


def list_monitors() -> list[dict]:
    """연결된 모니터 목록과 해상도 반환."""
    with mss.mss() as sct:
        monitors = []
        for i, m in enumerate(sct.monitors):
            monitors.append({
                "index": i,
                "left": m["left"],
                "top": m["top"],
                "width": m["width"],
                "height": m["height"],
            })
        return monitors


def print_monitors():
    """모니터 목록을 출력."""
    monitors = list_monitors()
    print(f"모니터 {len(monitors) - 1}개 감지 (0번은 전체 화면)\n")
    for m in monitors:
        label = "전체" if m["index"] == 0 else f"모니터 {m['index']}"
        print(f"  [{m['index']}] {label}: {m['width']}x{m['height']} (위치: {m['left']}, {m['top']})")


def validate_monitor(index: int) -> bool:
    """모니터 번호가 유효한지 확인."""
    with mss.mss() as sct:
        return 0 <= index < len(sct.monitors)
