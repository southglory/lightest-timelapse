import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk

from .editor import Editor, Layer
from .file_manager import FileManager


SHORTCUTS_TEXT = """단축키 목록

← / A : 이전 이미지
→ / D : 다음 이미지
1 : 모자이크
2 : 블러
3 : 가리기
4 : 펜
Ctrl+Z : 실행취소
Ctrl+Y : 재실행
Ctrl+S : 수동 저장
Delete : 이미지 삭제
Space : 화면 맞춤 토글
Escape : 도구 해제 / 그리드 복귀
"""


class Viewer(tk.Frame):
    def __init__(self, master, fm: FileManager, on_back):
        super().__init__(master)
        self.fm = fm
        self.on_back = on_back
        self.editor = Editor()
        self.images: list[Path] = []
        self.index = 0
        self.pil_orig: Image.Image | None = None
        self.tk_img: ImageTk.PhotoImage | None = None
        self.zoom = 1.0
        self.fit_mode = True
        self._drag_start = None
        self._rect_id = None
        self._autosave_id = None
        self._prefetch_cache: dict[int, Image.Image] = {}
        self._active = False

        # --- 상단 툴바 1행 ---
        row1 = tk.Frame(self, bg="#333")
        row1.pack(fill=tk.X)

        tk.Button(row1, text="< 그리드 (Esc)", command=self._go_back).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="< (A)", command=self._prev).pack(side=tk.LEFT)
        self.label_pos = tk.Label(row1, text="0/0", bg="#333", fg="white")
        self.label_pos.pack(side=tk.LEFT, padx=4)
        tk.Button(row1, text="> (D)", command=self._next).pack(side=tk.LEFT)

        tk.Frame(row1, width=20, bg="#333").pack(side=tk.LEFT)

        tools = [("모자이크 (1)", "mosaic"), ("블러 (2)", "blur"), ("가리기 (3)", "fill"), ("펜 (4)", "pen")]
        self.tool_btns = {}
        for label, tool in tools:
            btn = tk.Button(row1, text=label, command=lambda t=tool: self._set_tool(t))
            btn.pack(side=tk.LEFT, padx=1)
            self.tool_btns[tool] = btn

        tk.Frame(row1, width=20, bg="#333").pack(side=tk.LEFT)
        tk.Button(row1, text="초기화", command=self._reset_edits).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="이미지 삭제 (Del)", command=self._delete, fg="red").pack(side=tk.RIGHT, padx=8)
        self.label_tool = tk.Label(row1, text="", bg="#333", fg="#aaa")
        self.label_tool.pack(side=tk.RIGHT, padx=8)

        # --- 상단 툴바 2행 ---
        row2 = tk.Frame(self, bg="#3a3a3a")
        row2.pack(fill=tk.X)

        tk.Label(row2, text="색상:", bg="#3a3a3a", fg="white").pack(side=tk.LEFT, padx=4)
        for color, hex_c in [((0, 0, 0), "#000"), ((255, 0, 0), "#f00"), ((0, 0, 255), "#00f"), ((255, 255, 255), "#fff")]:
            tk.Button(row2, bg=hex_c, width=2, command=lambda c=color: self._set_color(c)).pack(side=tk.LEFT, padx=1)

        tk.Label(row2, text="  굵기:", bg="#3a3a3a", fg="white").pack(side=tk.LEFT)
        self.width_var = tk.IntVar(value=3)
        tk.Scale(row2, from_=1, to=20, orient=tk.HORIZONTAL, variable=self.width_var,
                 bg="#3a3a3a", fg="white", length=100, showvalue=True,
                 command=lambda v: setattr(self.editor, 'pen_width', int(v))).pack(side=tk.LEFT)

        tk.Button(row2, text="단축키", command=lambda: messagebox.showinfo("단축키", SHORTCUTS_TEXT)).pack(side=tk.RIGHT, padx=4)

        # --- 메인 영역 ---
        main = tk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- 오른쪽 사이드바 ---
        self.sidebar = tk.Frame(main, bg="#2b2b2b", width=200)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self._build_template_section()
        self._build_layer_section()

        # 캔버스 이벤트
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

    # ========== 사이드바 ==========

    def _build_template_section(self):
        """템플릿 섹션 — 제작/관리."""
        frame = tk.LabelFrame(self.sidebar, text="템플릿", bg="#2b2b2b", fg="white", font=("", 9, "bold"))
        frame.pack(fill=tk.X, padx=4, pady=4)

        self.btn_tpl_start = tk.Button(frame, text="템플릿 제작 시작", command=self._start_template, bg="#4caf50", fg="white")
        self.btn_tpl_start.pack(fill=tk.X, padx=4, pady=2)

        self.btn_tpl_save = tk.Button(frame, text="템플릿 저장 완료", command=self._save_template, bg="#2196f3", fg="white")
        self.btn_tpl_cancel = tk.Button(frame, text="제작 취소", command=self._cancel_template)
        # 제작 모드일 때만 표시 (초기에는 숨김)

        self.tpl_listbox = tk.Listbox(frame, bg="#333", fg="white", selectbackground="#4fc3f7",
                                       height=5, font=("", 9))
        self.tpl_listbox.pack(fill=tk.X, padx=4, pady=2)
        self.tpl_listbox.bind("<Double-Button-1>", self._rename_template)
        # Listbox가 키 이벤트 훔치지 않도록
        self.tpl_listbox.bind("<FocusIn>", lambda e: self.canvas.focus_set())

        btn_row = tk.Frame(frame, bg="#2b2b2b")
        btn_row.pack(fill=tk.X, padx=4, pady=2)
        tk.Button(btn_row, text="적용", width=4, command=self._apply_template).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="편집", width=4, command=self._edit_template).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="삭제", width=4, command=self._delete_template, fg="red").pack(side=tk.LEFT, padx=1)

        self.tpl_mode_label = tk.Label(frame, text="", bg="#2b2b2b", fg="#ff9800", font=("", 8))
        self.tpl_mode_label.pack(fill=tk.X, padx=4)

    def _build_layer_section(self):
        """레이어 섹션 — 템플릿 제작 모드에서만 활성."""
        self.layer_frame = tk.LabelFrame(self.sidebar, text="레이어 (템플릿 제작 중)", bg="#2b2b2b", fg="#888", font=("", 9, "bold"))
        self.layer_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        btn_row = tk.Frame(self.layer_frame, bg="#2b2b2b")
        btn_row.pack(fill=tk.X, padx=2, pady=2)
        tk.Button(btn_row, text="+", width=2, command=self._add_layer).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="-", width=2, command=self._remove_layer).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="▲", width=2, command=lambda: self._move_layer(-1)).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="▼", width=2, command=lambda: self._move_layer(1)).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="👁", width=2, command=self._toggle_layer).pack(side=tk.LEFT, padx=1)

        self.layer_listbox = tk.Listbox(self.layer_frame, bg="#333", fg="white", selectbackground="#4fc3f7",
                                         height=6, font=("", 9))
        self.layer_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.layer_listbox.bind("<<ListboxSelect>>", self._on_layer_select)
        self.layer_listbox.bind("<Double-Button-1>", self._rename_layer)
        self.layer_listbox.bind("<FocusIn>", lambda e: self.canvas.focus_set())

    # ========== 템플릿 제작 ==========

    def _start_template(self):
        self.editor.start_template_mode()
        self.btn_tpl_start.pack_forget()
        self.btn_tpl_save.pack(fill=tk.X, padx=4, pady=2)
        self.btn_tpl_cancel.pack(fill=tk.X, padx=4, pady=2)
        self.tpl_mode_label.config(text="▶ 템플릿 제작 중...")
        self.layer_frame.config(fg="white", text="레이어 (제작 중)")
        self._refresh_layer_list()
        self._render()

    def _save_template(self):
        # 이름 먼저 물어봄 (모드 종료 전)
        name = simpledialog.askstring("템플릿 저장", "템플릿 이름:")
        if not name:
            return  # 취소해도 제작 모드 유지
        layers = self.editor.end_template_mode()
        if not layers:
            messagebox.showinfo("알림", "편집 내용이 없습니다.")
            self._exit_template_ui()
            return
        self.fm.save_named_template(name, layers)
        self._exit_template_ui()
        self._refresh_template_list()
        self.label_tool.config(text=f"템플릿 '{name}' 저장됨")
        self._render()

    def _cancel_template(self):
        self.editor.cancel_template_mode()
        self._exit_template_ui()
        self._render()

    def _exit_template_ui(self):
        self.btn_tpl_save.pack_forget()
        self.btn_tpl_cancel.pack_forget()
        self.btn_tpl_start.pack(fill=tk.X, padx=4, pady=2)
        self.tpl_mode_label.config(text="")
        self.layer_frame.config(fg="#888", text="레이어 (템플릿 제작 중)")
        self.layer_listbox.delete(0, tk.END)

    def _apply_template(self):
        """선택된 템플릿을 현재 이미지에 적용."""
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if not sel or sel[0] >= len(templates):
            messagebox.showinfo("알림", "적용할 템플릿을 선택하세요.")
            return
        if self.editor.template_mode:
            messagebox.showinfo("알림", "템플릿 제작 중에는 적용할 수 없습니다.")
            return

        name = templates[sel[0]]
        layers = self.fm.load_named_template(name)
        # 레이어의 visible edits를 flat으로 모아서 현재 이미지 edits에 추가
        new_edits = []
        for layer in layers:
            if layer.get("visible", True):
                new_edits.extend(layer.get("edits", []))
        if new_edits:
            self.editor._push_history()
            self.editor.edits.extend(new_edits)
            self._save()
            self._render()
            self.label_tool.config(text=f"'{name}' 적용됨")

    def _edit_template(self):
        """선택된 템플릿을 제작 모드로 열어서 편집."""
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if not sel or sel[0] >= len(templates):
            messagebox.showinfo("알림", "편집할 템플릿을 선택하세요.")
            return
        if self.editor.template_mode:
            messagebox.showinfo("알림", "이미 템플릿 제작 중입니다.")
            return

        name = templates[sel[0]]
        layers = self.fm.load_named_template(name)
        # 제작 모드로 진입하되 기존 레이어를 로드
        self.editor.start_template_mode()
        self.editor.template_layers = [Layer.from_dict(l) for l in layers]
        self.editor.active_layer_idx = 0 if self.editor.template_layers else -1

        # 기존 템플릿 삭제 (저장 시 새로 만들어짐)
        self.fm.delete_template(name)
        self._refresh_template_list()

        self.btn_tpl_start.pack_forget()
        self.btn_tpl_save.pack(fill=tk.X, padx=4, pady=2)
        self.btn_tpl_cancel.pack(fill=tk.X, padx=4, pady=2)
        self.tpl_mode_label.config(text=f"▶ '{name}' 편집 중...")
        self.layer_frame.config(fg="white", text="레이어 (제작 중)")
        self._refresh_layer_list()
        self._render()

    def _rename_template(self, event=None):
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if not sel or sel[0] >= len(templates):
            return
        old_name = templates[sel[0]]
        new_name = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=old_name)
        if new_name and new_name != old_name:
            layers = self.fm.load_named_template(old_name)
            self.fm.delete_template(old_name)
            self.fm.save_named_template(new_name, layers)
            self._refresh_template_list()

    def _delete_template(self):
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if sel and sel[0] < len(templates):
            self.fm.delete_template(templates[sel[0]])
            self._refresh_template_list()

    def _refresh_template_list(self):
        self.tpl_listbox.delete(0, tk.END)
        for name in self.fm.list_templates():
            layers = self.fm.load_named_template(name)
            total = sum(len(l.get("edits", [])) for l in layers)
            self.tpl_listbox.insert(tk.END, f"{name} ({len(layers)}L, {total}편집)")

    # ========== 레이어 (템플릿 모드에서만) ==========

    def _refresh_layer_list(self):
        self.layer_listbox.delete(0, tk.END)
        if not self.editor.template_mode:
            return
        for i, layer in enumerate(self.editor.template_layers):
            vis = "◉" if layer.visible else "○"
            active = "▶" if i == self.editor.active_layer_idx else "  "
            self.layer_listbox.insert(tk.END, f"{active}{vis} {layer.name} ({len(layer.edits)})")
        if 0 <= self.editor.active_layer_idx < len(self.editor.template_layers):
            self.layer_listbox.selection_set(self.editor.active_layer_idx)

    def _rename_layer(self, event=None):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if not sel or sel[0] >= len(self.editor.template_layers):
            return
        layer = self.editor.template_layers[sel[0]]
        new_name = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=layer.name)
        if new_name:
            layer.name = new_name
            self._refresh_layer_list()

    def _on_layer_select(self, event):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.set_active_layer(sel[0])
            self._refresh_layer_list()

    def _add_layer(self):
        if not self.editor.template_mode:
            return
        name = simpledialog.askstring("새 레이어", "레이어 이름:",
                                       initialvalue=f"레이어 {len(self.editor.template_layers) + 1}")
        if name:
            self.editor.add_layer(name)
            self._refresh_layer_list()

    def _remove_layer(self):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.remove_layer(sel[0])
            self._render()
            self._refresh_layer_list()

    def _move_layer(self, direction: int):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.move_layer(sel[0], direction)
            self._render()
            self._refresh_layer_list()

    def _toggle_layer(self):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.toggle_layer(sel[0])
            self._render()
            self._refresh_layer_list()

    # ========== 키보드 ==========

    def activate(self):
        self._active = True
        root = self.winfo_toplevel()
        root.bind("<Left>", lambda e: self._prev())
        root.bind("<Right>", lambda e: self._next())
        root.bind("<a>", lambda e: self._prev())
        root.bind("<d>", lambda e: self._next())
        root.bind("<Escape>", lambda e: self._escape())
        root.bind("<Delete>", lambda e: self._delete())
        root.bind("<Control-s>", lambda e: self._save())
        root.bind("<Control-z>", lambda e: self._undo())
        root.bind("<Control-y>", lambda e: self._redo())
        root.bind("<space>", lambda e: self._toggle_fit())
        root.bind("<Key-1>", lambda e: self._set_tool("mosaic"))
        root.bind("<Key-2>", lambda e: self._set_tool("blur"))
        root.bind("<Key-3>", lambda e: self._set_tool("fill"))
        root.bind("<Key-4>", lambda e: self._set_tool("pen"))

    def deactivate(self):
        self._active = False
        root = self.winfo_toplevel()
        for key in ["<Left>", "<Right>", "<a>", "<d>", "<Escape>", "<Delete>",
                     "<Control-s>", "<Control-z>", "<Control-y>", "<space>",
                     "<Key-1>", "<Key-2>", "<Key-3>", "<Key-4>"]:
            root.unbind(key)

    # ========== 이미지 ==========

    def show(self, images: list[Path], index: int):
        self.images = images
        self._prefetch_cache.clear()
        self._go_to(index)
        self._refresh_template_list()
        self._start_autosave()

    def _go_to(self, index: int):
        if self.pil_orig is not None and self.editor.is_dirty:
            self._save()

        self.index = index
        img_path = self.images[self.index]
        self.label_pos.config(text=f"{self.index + 1}/{len(self.images)}  {img_path.stem}")

        if self.index in self._prefetch_cache:
            self.pil_orig = self._prefetch_cache[self.index]
        else:
            self.pil_orig = Image.open(img_path).convert("RGB")

        edits = self.fm.load_edits(img_path)
        self.editor.load_edits(edits)

        self.fit_mode = True
        self._render()
        self._prefetch()

    def _prefetch(self):
        import threading
        for offset in [-1, 1]:
            idx = self.index + offset
            if 0 <= idx < len(self.images) and idx not in self._prefetch_cache:
                def _load(i=idx):
                    try:
                        self._prefetch_cache[i] = Image.open(self.images[i]).convert("RGB")
                    except Exception:
                        pass
                threading.Thread(target=_load, daemon=True).start()

    def _render(self):
        if self.pil_orig is None:
            return

        all_edits = self.editor.all_visible_edits()
        img = FileManager.apply_edits(self.pil_orig, all_edits)

        self.canvas.update_idletasks()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 800, 600
        if self.fit_mode:
            self.zoom = min(cw / img.width, ch / img.height)
        dw = max(1, int(img.width * self.zoom))
        dh = max(1, int(img.height * self.zoom))
        display = img.resize((dw, dh), Image.LANCZOS) if self.zoom != 1.0 else img

        self.tk_img = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.tk_img, anchor=tk.CENTER)

    def _canvas_to_image(self, cx, cy) -> tuple[int, int]:
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        dw = int(self.pil_orig.width * self.zoom)
        dh = int(self.pil_orig.height * self.zoom)
        ox = (cw - dw) / 2
        oy = (ch - dh) / 2
        ix = int((cx - ox) / self.zoom)
        iy = int((cy - oy) / self.zoom)
        return max(0, min(ix, self.pil_orig.width - 1)), max(0, min(iy, self.pil_orig.height - 1))

    # ========== 마우스 ==========

    def _on_press(self, event):
        tool = self.editor.current_tool
        if tool == "pen":
            ix, iy = self._canvas_to_image(event.x, event.y)
            self.editor.pen_start(ix, iy)
            self._drag_start = (event.x, event.y)
        elif tool in ("mosaic", "blur", "fill"):
            self._drag_start = (event.x, event.y)

    def _on_drag(self, event):
        tool = self.editor.current_tool
        if tool == "pen" and self._drag_start:
            ix, iy = self._canvas_to_image(event.x, event.y)
            self.editor.pen_move(ix, iy)
            self.canvas.create_line(
                self._drag_start[0], self._drag_start[1], event.x, event.y,
                fill=self._color_hex(self.editor.pen_color),
                width=max(1, int(self.editor.pen_width * self.zoom)),
            )
            self._drag_start = (event.x, event.y)
        elif tool in ("mosaic", "blur", "fill") and self._drag_start:
            if self._rect_id:
                self.canvas.delete(self._rect_id)
            self._rect_id = self.canvas.create_rectangle(
                self._drag_start[0], self._drag_start[1], event.x, event.y,
                outline="yellow", dash=(4, 4),
            )

    def _on_release(self, event):
        tool = self.editor.current_tool
        if tool == "pen":
            self.editor.finish_pen()
            self._render()
            if self.editor.template_mode:
                self._refresh_layer_list()
        elif tool in ("mosaic", "blur", "fill") and self._drag_start:
            if self._rect_id:
                self.canvas.delete(self._rect_id)
                self._rect_id = None
            x1, y1 = self._canvas_to_image(*self._drag_start)
            x2, y2 = self._canvas_to_image(event.x, event.y)
            box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if box[2] - box[0] > 2 and box[3] - box[1] > 2:
                if tool == "mosaic":
                    self.editor.add_mosaic(box)
                elif tool == "blur":
                    self.editor.add_blur(box)
                elif tool == "fill":
                    self.editor.add_fill(box)
                self._render()
                if self.editor.template_mode:
                    self._refresh_layer_list()
        self._drag_start = None

    def _on_wheel(self, event):
        if event.delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1
        self.zoom = max(0.1, min(self.zoom, 5.0))
        self.fit_mode = False
        self._render()

    # ========== 액션 ==========

    def _set_tool(self, tool: str):
        if self.editor.current_tool == tool:
            self.editor.set_tool(None)
            self.label_tool.config(text="")
        else:
            self.editor.set_tool(tool)
            names = {"mosaic": "모자이크", "blur": "블러", "fill": "가리기", "pen": "펜"}
            self.label_tool.config(text=f"도구: {names.get(tool, tool)}")
        for t, btn in self.tool_btns.items():
            btn.config(relief=tk.SUNKEN if t == self.editor.current_tool else tk.RAISED)

    def _set_color(self, color: tuple):
        self.editor.pen_color = color
        self.editor.fill_color = color

    def _prev(self):
        if self.editor.template_mode:
            return  # 템플릿 제작 중 이동 금지
        if self.index > 0:
            self._go_to(self.index - 1)

    def _next(self):
        if self.editor.template_mode:
            return
        if self.index < len(self.images) - 1:
            self._go_to(self.index + 1)

    def _go_back(self):
        if self.editor.template_mode:
            messagebox.showinfo("알림", "템플릿 제작을 먼저 완료하거나 취소하세요.")
            return
        if self.editor.is_dirty:
            self._save()
        self._stop_autosave()
        self.on_back()

    def _escape(self):
        if self.editor.current_tool:
            self._set_tool(self.editor.current_tool)
        elif self.editor.template_mode:
            self._cancel_template()
        else:
            self._go_back()

    def _save(self):
        if self.images and not self.editor.template_mode:
            self.fm.save_edits(self.images[self.index], self.editor.edits)

    def _undo(self):
        if self.editor.undo():
            self._render()
            if self.editor.template_mode:
                self._refresh_layer_list()

    def _redo(self):
        if self.editor.redo():
            self._render()
            if self.editor.template_mode:
                self._refresh_layer_list()

    def _toggle_fit(self):
        self.fit_mode = not self.fit_mode
        if self.fit_mode:
            self._render()

    def _delete(self):
        if self.editor.template_mode or not self.images:
            return
        self.fm.soft_delete(self.images[self.index])
        self.images = self.fm.list_images()
        if not self.images:
            self._go_back()
            return
        self.index = min(self.index, len(self.images) - 1)
        self.editor.clear_edits()
        self._prefetch_cache.clear()
        self._go_to(self.index)

    def _reset_edits(self):
        if self.editor.template_mode:
            return
        self.editor.clear_edits()
        self.fm.save_edits(self.images[self.index], [])
        self._render()

    # ========== 오토세이브 ==========

    def _start_autosave(self):
        def _tick():
            if self.images and self.editor.is_dirty and not self.editor.template_mode:
                self.fm.autosave(self.images[self.index], self.editor.edits)
            self._autosave_id = self.after(10000, _tick)
        self._autosave_id = self.after(10000, _tick)

    def _stop_autosave(self):
        if self._autosave_id:
            self.after_cancel(self._autosave_id)
            self._autosave_id = None
        self.fm.clear_autosave()

    @staticmethod
    def _color_hex(rgb: tuple) -> str:
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
