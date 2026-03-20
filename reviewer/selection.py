"""선택 관리 — 편집 요소의 선택, 이동, 리사이즈, 삭제."""

import math
from .editor import Editor

HANDLE_SIZE = 6
HANDLE_HIT = HANDLE_SIZE + 3


class SelectionManager:
    def __init__(self, editor: Editor, canvas, c2i_func, i2c_func):
        self.editor = editor
        self.canvas = canvas
        self.c2i = c2i_func
        self.i2c = i2c_func

        self.selected_idx: int | None = None
        self._overlay_ids: list[int] = []
        self._dragging = False
        self._drag_start: tuple[int, int] | None = None
        self._drag_handle: str | None = None
        self._drag_orig_box: tuple | None = None

    @property
    def _edits(self) -> list[dict]:
        return self.editor._target_list()

    # ==================== 히트 테스트 ====================

    def hit_test(self, ix: int, iy: int) -> int | None:
        """이미지 좌표에서 편집 요소 찾기. 역순 (위에 있는 것 우선)."""
        edits = self._edits
        for i in range(len(edits) - 1, -1, -1):
            edit = edits[i]
            bounds = Editor.get_edit_bounds(edit)
            if edit["type"] in ("mosaic", "blur", "fill"):
                if bounds[0] <= ix <= bounds[2] and bounds[1] <= iy <= bounds[3]:
                    return i
            elif edit["type"] == "pen":
                if self._pen_hit(edit, ix, iy):
                    return i
        return None

    def _pen_hit(self, edit: dict, ix: int, iy: int) -> bool:
        """펜 스트로크 히트 테스트. 각 선분까지의 거리."""
        pts = edit["points"]
        threshold = edit.get("width", 3) + 6
        for j in range(len(pts) - 1):
            dist = self._point_to_seg_dist(ix, iy, pts[j][0], pts[j][1], pts[j+1][0], pts[j+1][1])
            if dist <= threshold:
                return True
        return False

    @staticmethod
    def _point_to_seg_dist(px, py, x1, y1, x2, y2) -> float:
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def hit_handle(self, cx: int, cy: int) -> str | None:
        """Canvas 좌표에서 핸들 히트. 선택된 편집이 있을 때만."""
        if self.selected_idx is None:
            return None
        edits = self._edits
        if self.selected_idx >= len(edits):
            return None
        edit = edits[self.selected_idx]
        if edit["type"] not in ("mosaic", "blur", "fill"):
            return None  # 펜은 리사이즈 불가

        bounds = Editor.get_edit_bounds(edit)
        handles = self._get_handles(bounds)
        for name, (hx, hy) in handles.items():
            if abs(cx - hx) <= HANDLE_HIT and abs(cy - hy) <= HANDLE_HIT:
                return name
        return None

    def _get_handles(self, bounds: tuple) -> dict[str, tuple[float, float]]:
        """바운더리의 4개 모서리 핸들 (Canvas 좌표)."""
        x1, y1, x2, y2 = bounds
        cx1, cy1 = self.i2c(x1, y1)
        cx2, cy2 = self.i2c(x2, y2)
        return {
            "nw": (cx1, cy1), "ne": (cx2, cy1),
            "sw": (cx1, cy2), "se": (cx2, cy2),
        }

    # ==================== 선택 UI ====================

    def select(self, idx: int):
        self.clear_overlay()
        self.selected_idx = idx
        self.draw_overlay()

    def deselect(self):
        self.clear_overlay()
        self.selected_idx = None

    def clear_overlay(self):
        for item_id in self._overlay_ids:
            self.canvas.delete(item_id)
        self._overlay_ids.clear()

    def draw_overlay(self):
        """선택된 편집의 바운더리 + 핸들 그리기."""
        self.clear_overlay()
        if self.selected_idx is None:
            return
        edits = self._edits
        if self.selected_idx >= len(edits):
            self.selected_idx = None
            return

        edit = edits[self.selected_idx]
        bounds = Editor.get_edit_bounds(edit)
        cx1, cy1 = self.i2c(bounds[0], bounds[1])
        cx2, cy2 = self.i2c(bounds[2], bounds[3])

        # 바운더리 점선
        rid = self.canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                            outline="#007acc", dash=(4, 4), width=2)
        self._overlay_ids.append(rid)

        # 핸들 (box 편집만)
        if edit["type"] in ("mosaic", "blur", "fill"):
            handles = self._get_handles(bounds)
            for hx, hy in handles.values():
                h = HANDLE_SIZE
                hid = self.canvas.create_rectangle(hx - h, hy - h, hx + h, hy + h,
                                                    fill="white", outline="#007acc", width=1)
                self._overlay_ids.append(hid)

    # ==================== 드래그 (이동) ====================

    def start_move(self, ix: int, iy: int):
        self._dragging = True
        self._drag_start = (ix, iy)
        self._drag_handle = None

    def start_resize(self, handle: str, ix: int, iy: int):
        self._dragging = True
        self._drag_start = (ix, iy)
        self._drag_handle = handle
        if self.selected_idx is not None and self.selected_idx < len(self._edits):
            self._drag_orig_box = tuple(self._edits[self.selected_idx].get("box", [0,0,0,0]))

    def update_drag(self, ix: int, iy: int, render_func):
        """드래그 중 호출. render_func은 viewer._render."""
        if not self._dragging or self.selected_idx is None or self._drag_start is None:
            return

        if self._drag_handle:
            self._do_resize(ix, iy, render_func)
        else:
            self._do_move(ix, iy, render_func)

    def _do_move(self, ix: int, iy: int, render_func):
        dx = ix - self._drag_start[0]
        dy = iy - self._drag_start[1]
        if dx == 0 and dy == 0:
            return
        self.editor.move_edit(self.selected_idx, dx, dy)
        self._drag_start = (ix, iy)
        render_func()

    def _do_resize(self, ix: int, iy: int, render_func):
        if self._drag_orig_box is None:
            return
        edits = self._edits
        if self.selected_idx >= len(edits):
            return
        edit = edits[self.selected_idx]
        if edit["type"] not in ("mosaic", "blur", "fill"):
            return

        ox1, oy1, ox2, oy2 = self._drag_orig_box
        sx, sy = self._drag_start
        dx, dy = ix - sx, iy - sy

        x1, y1, x2, y2 = ox1, oy1, ox2, oy2
        h = self._drag_handle
        if "w" in h:
            x1 = ox1 + dx
        if "e" in h:
            x2 = ox2 + dx
        if "n" in h:
            y1 = oy1 + dy
        if "s" in h:
            y2 = oy2 + dy

        # 최소 크기
        if x2 - x1 < 10:
            if "w" in h: x1 = x2 - 10
            else: x2 = x1 + 10
        if y2 - y1 < 10:
            if "n" in h: y1 = y2 - 10
            else: y2 = y1 + 10

        self.editor.resize_edit(self.selected_idx, (x1, y1, x2, y2))
        render_func()

    def end_drag(self):
        self._dragging = False
        self._drag_start = None
        self._drag_handle = None
        self._drag_orig_box = None

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    # ==================== 삭제 ====================

    def delete_selected(self) -> bool:
        if self.selected_idx is None:
            return False
        self.editor.delete_edit(self.selected_idx)
        self.deselect()
        return True
