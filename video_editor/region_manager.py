"""영역 관리 — 마스크 영역 데이터 모델."""

from dataclasses import dataclass, field


@dataclass
class MaskRegion:
    x: int
    y: int
    w: int
    h: int
    kind: str = "blur"  # "blur" | "mosaic" | "fill"
    label: str = ""

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "kind": self.kind}


class RegionManager:
    def __init__(self):
        self.regions: list[MaskRegion] = []
        self.selected_idx: int | None = None
        self._counter = 0

    def add(self, kind: str, box: tuple[int, int, int, int]) -> int:
        """box = (x1, y1, x2, y2). 반환: 인덱스."""
        x1, y1, x2, y2 = box
        self._counter += 1
        region = MaskRegion(
            x=min(x1, x2), y=min(y1, y2),
            w=abs(x2 - x1), h=abs(y2 - y1),
            kind=kind,
            label=f"Region {self._counter}",
        )
        self.regions.append(region)
        return len(self.regions) - 1

    def remove(self, idx: int):
        if 0 <= idx < len(self.regions):
            self.regions.pop(idx)
            if self.selected_idx is not None:
                if self.selected_idx == idx:
                    self.selected_idx = None
                elif self.selected_idx > idx:
                    self.selected_idx -= 1

    def update_box(self, idx: int, box: tuple[int, int, int, int]):
        if 0 <= idx < len(self.regions):
            x1, y1, x2, y2 = box
            r = self.regions[idx]
            r.x, r.y = min(x1, x2), min(y1, y2)
            r.w, r.h = abs(x2 - x1), abs(y2 - y1)

    def update_kind(self, idx: int, kind: str):
        if 0 <= idx < len(self.regions):
            self.regions[idx].kind = kind

    def move(self, idx: int, dx: int, dy: int):
        if 0 <= idx < len(self.regions):
            r = self.regions[idx]
            r.x += dx
            r.y += dy

    def clear_all(self):
        self.regions.clear()
        self.selected_idx = None
        self._counter = 0

    def to_filter_params(self) -> list[dict]:
        return [r.to_dict() for r in self.regions]
