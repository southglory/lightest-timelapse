"""캔버스 뷰 — 프레임 표시, 줌, 영역 그리기/선택/이동/리사이즈."""

import tkinter as tk
from PIL import Image, ImageTk, ImageFilter, ImageDraw

from .region_manager import RegionManager

BG_MAIN = "#1e1e1e"
ACCENT = "#007acc"
HANDLE_SIZE = 6
HANDLE_HIT = HANDLE_SIZE + 3


class CanvasView(tk.Frame):
    def __init__(self, master, region_mgr: RegionManager, on_change=None):
        super().__init__(master, bg=BG_MAIN)
        self.region_mgr = region_mgr
        self.on_change = on_change  # 영역 변경 시 콜백

        self.pil_orig: Image.Image | None = None
        self.tk_img: ImageTk.PhotoImage | None = None
        self.zoom = 1.0
        self.fit_mode = True
        self.current_tool: str | None = None  # "blur" | "mosaic" | "fill" | None

        self._drag_start = None
        self._rect_id = None
        self._sel_dragging = False
        self._sel_drag_start = None
        self._sel_drag_handle: str | None = None
        self._sel_orig_box = None
        self._resize_after_id = None

        self.canvas = tk.Canvas(self, bg=BG_MAIN, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def load_frame(self, img: Image.Image):
        self.pil_orig = img
        self.fit_mode = True
        self.render()

    def render(self):
        if not self.pil_orig:
            return

        # 미리보기: 모든 영역에 PIL 기반 효과 적용
        img = self._apply_preview()

        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10:
            cw = 800
        if ch < 10:
            ch = 600

        if self.fit_mode:
            self.zoom = min(cw / img.width, ch / img.height)

        dw = max(1, int(img.width * self.zoom))
        dh = max(1, int(img.height * self.zoom))
        disp = img.resize((dw, dh), Image.LANCZOS) if self.zoom != 1.0 else img

        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.tk_img, anchor=tk.CENTER)

        # 영역 오버레이 그리기
        self._draw_overlays()

    def _apply_preview(self) -> Image.Image:
        """PIL 기반으로 모든 영역의 효과를 미리보기."""
        if not self.region_mgr.regions:
            return self.pil_orig

        img = self.pil_orig.copy()
        for r in self.region_mgr.regions:
            box = r.box
            # 이미지 범위 클램핑
            box = (
                max(0, box[0]), max(0, box[1]),
                min(img.width, box[2]), min(img.height, box[3]),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                continue

            if r.kind == "crop":
                # 크롭: 바깥 영역을 반투명 어둡게
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 150))
                # 크롭 영역을 투명하게
                draw_ov = ImageDraw.Draw(overlay)
                draw_ov.rectangle(box, fill=(0, 0, 0, 0))
                img = img.convert("RGBA")
                img = Image.alpha_composite(img, overlay)
                img = img.convert("RGB")
                continue
            elif r.kind == "mosaic":
                region = img.crop(box)
                block = 16
                small = region.resize(
                    (max(1, region.width // block), max(1, region.height // block)),
                    Image.NEAREST)
                img.paste(small.resize(region.size, Image.NEAREST), box)
            elif r.kind == "blur":
                region = img.crop(box)
                img.paste(region.filter(ImageFilter.GaussianBlur(radius=20)), box)
            elif r.kind == "fill":
                ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))
        return img

    def get_edited_frame(self) -> Image.Image | None:
        """편집이 적용된 현재 프레임 반환. 크롭 영역이 있으면 잘라낸다."""
        if not self.pil_orig:
            return None

        img = self.pil_orig.copy()
        crop_box = None

        for r in self.region_mgr.regions:
            box = (
                max(0, r.box[0]), max(0, r.box[1]),
                min(img.width, r.box[2]), min(img.height, r.box[3]),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                continue

            if r.kind == "crop":
                crop_box = box
            elif r.kind == "mosaic":
                region = img.crop(box)
                block = 16
                small = region.resize(
                    (max(1, region.width // block), max(1, region.height // block)),
                    Image.NEAREST)
                img.paste(small.resize(region.size, Image.NEAREST), box)
            elif r.kind == "blur":
                region = img.crop(box)
                img.paste(region.filter(ImageFilter.GaussianBlur(radius=20)), box)
            elif r.kind == "fill":
                ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))

        if crop_box:
            img = img.crop(crop_box)

        return img

    def _draw_overlays(self):
        """각 영역의 테두리, 선택된 영역은 핸들 포함."""
        for i, r in enumerate(self.region_mgr.regions):
            cx1, cy1 = self._i2c(r.x, r.y)
            cx2, cy2 = self._i2c(r.x + r.w, r.y + r.h)

            is_selected = i == self.region_mgr.selected_idx
            color = ACCENT if is_selected else "#ffcc00"
            width = 2 if is_selected else 1

            self.canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                         outline=color, dash=(4, 4), width=width)

            # 라벨
            kind_label = {"blur": "B", "mosaic": "M", "fill": "F", "crop": "C"}.get(r.kind, "?")
            self.canvas.create_text(cx1 + 4, cy1 + 2, text=f"{i+1}:{kind_label}",
                                    anchor=tk.NW, fill=color, font=("Segoe UI", 8, "bold"))

            # 선택된 영역의 핸들
            if is_selected:
                for hx, hy in [(cx1, cy1), (cx2, cy1), (cx1, cy2), (cx2, cy2)]:
                    h = HANDLE_SIZE
                    self.canvas.create_rectangle(hx - h, hy - h, hx + h, hy + h,
                                                 fill="white", outline=ACCENT, width=1)

    # ==================== 좌표 변환 ====================

    def _c2i(self, cx, cy):
        """Canvas 좌표 → 이미지 좌표."""
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        dw = self.pil_orig.width * self.zoom
        dh = self.pil_orig.height * self.zoom
        ix = int((cx - (cw - dw) / 2) / self.zoom)
        iy = int((cy - (ch - dh) / 2) / self.zoom)
        return ix, iy

    def _i2c(self, ix, iy):
        """이미지 좌표 → Canvas 좌표."""
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        dw = self.pil_orig.width * self.zoom
        dh = self.pil_orig.height * self.zoom
        cx = ix * self.zoom + (cw - dw) / 2
        cy = iy * self.zoom + (ch - dh) / 2
        return cx, cy

    # ==================== 히트 테스트 ====================

    def _hit_test(self, ix: int, iy: int) -> int | None:
        """이미지 좌표에서 영역 찾기 (역순)."""
        for i in range(len(self.region_mgr.regions) - 1, -1, -1):
            r = self.region_mgr.regions[i]
            if r.x <= ix <= r.x + r.w and r.y <= iy <= r.y + r.h:
                return i
        return None

    def _hit_handle(self, cx: int, cy: int) -> str | None:
        """선택된 영역의 핸들 히트 테스트."""
        idx = self.region_mgr.selected_idx
        if idx is None or idx >= len(self.region_mgr.regions):
            return None
        r = self.region_mgr.regions[idx]
        handles = {
            "nw": self._i2c(r.x, r.y),
            "ne": self._i2c(r.x + r.w, r.y),
            "sw": self._i2c(r.x, r.y + r.h),
            "se": self._i2c(r.x + r.w, r.y + r.h),
        }
        for name, (hx, hy) in handles.items():
            if abs(cx - hx) <= HANDLE_HIT and abs(cy - hy) <= HANDLE_HIT:
                return name
        return None

    # ==================== 마우스 이벤트 ====================

    def _on_press(self, event):
        if not self.pil_orig:
            return

        if self.current_tool:
            # 도구 모드: 새 영역 그리기 시작
            self.region_mgr.selected_idx = None
            self._drag_start = (event.x, event.y)
        else:
            # 선택 모드
            handle = self._hit_handle(event.x, event.y)
            if handle:
                ix, iy = self._c2i(event.x, event.y)
                self._start_resize(handle, ix, iy)
            else:
                ix, iy = self._c2i(event.x, event.y)
                idx = self._hit_test(ix, iy)
                if idx is not None:
                    self.region_mgr.selected_idx = idx
                    self._start_move(ix, iy)
                    self._notify_change()
                else:
                    self.region_mgr.selected_idx = None
                    self._notify_change()
            self.render()

    def _on_drag(self, event):
        if not self.pil_orig:
            return

        if self.current_tool and self._drag_start:
            # 도구 모드: 사각형 미리보기
            if self._rect_id:
                self.canvas.delete(self._rect_id)
            self._rect_id = self.canvas.create_rectangle(
                self._drag_start[0], self._drag_start[1], event.x, event.y,
                outline="#ffcc00", dash=(4, 4))
        elif self._sel_dragging:
            ix, iy = self._c2i(event.x, event.y)
            self._update_sel_drag(ix, iy)

    def _on_release(self, event):
        if not self.pil_orig:
            return

        if self.current_tool and self._drag_start:
            if self._rect_id:
                self.canvas.delete(self._rect_id)
                self._rect_id = None
            x1, y1 = self._c2i(*self._drag_start)
            x2, y2 = self._c2i(event.x, event.y)
            box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if box[2] - box[0] > 2 and box[3] - box[1] > 2:
                idx = self.region_mgr.add(self.current_tool, box)
                self.region_mgr.selected_idx = idx
                self._notify_change()
            self._drag_start = None
            self.render()
        elif self._sel_dragging:
            self._sel_dragging = False
            self._sel_drag_start = None
            self._sel_drag_handle = None
            self._sel_orig_box = None

    def _on_wheel(self, event):
        if not self.pil_orig:
            return
        self.zoom *= 1.1 if event.delta > 0 else 1 / 1.1
        self.zoom = max(0.1, min(self.zoom, 5.0))
        self.fit_mode = False
        self.render()

    def _on_canvas_resize(self, event):
        if not self.pil_orig:
            return
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(200, self._do_resize_fit)

    def _do_resize_fit(self):
        self._resize_after_id = None
        if self.pil_orig:
            self.fit_mode = True
            self.render()

    # ==================== 이동/리사이즈 ====================

    def _start_move(self, ix: int, iy: int):
        self._sel_dragging = True
        self._sel_drag_start = (ix, iy)
        self._sel_drag_handle = None

    def _start_resize(self, handle: str, ix: int, iy: int):
        self._sel_dragging = True
        self._sel_drag_start = (ix, iy)
        self._sel_drag_handle = handle
        idx = self.region_mgr.selected_idx
        if idx is not None and idx < len(self.region_mgr.regions):
            r = self.region_mgr.regions[idx]
            self._sel_orig_box = (r.x, r.y, r.x + r.w, r.y + r.h)

    def _update_sel_drag(self, ix: int, iy: int):
        if not self._sel_dragging or self._sel_drag_start is None:
            return
        idx = self.region_mgr.selected_idx
        if idx is None or idx >= len(self.region_mgr.regions):
            return

        if self._sel_drag_handle:
            self._do_resize(ix, iy)
        else:
            dx = ix - self._sel_drag_start[0]
            dy = iy - self._sel_drag_start[1]
            if dx != 0 or dy != 0:
                self.region_mgr.move(idx, dx, dy)
                self._sel_drag_start = (ix, iy)
                self.render()
                self._notify_change()

    def _do_resize(self, ix: int, iy: int):
        if self._sel_orig_box is None:
            return
        idx = self.region_mgr.selected_idx
        if idx is None:
            return

        ox1, oy1, ox2, oy2 = self._sel_orig_box
        sx, sy = self._sel_drag_start
        dx, dy = ix - sx, iy - sy

        x1, y1, x2, y2 = ox1, oy1, ox2, oy2
        h = self._sel_drag_handle
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
            if "w" in h:
                x1 = x2 - 10
            else:
                x2 = x1 + 10
        if y2 - y1 < 10:
            if "n" in h:
                y1 = y2 - 10
            else:
                y2 = y1 + 10

        self.region_mgr.update_box(idx, (x1, y1, x2, y2))
        self.render()
        self._notify_change()

    def _notify_change(self):
        if self.on_change:
            self.on_change()
