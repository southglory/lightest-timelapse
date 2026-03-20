"""뷰어 — 이미지 표시, 편집, 템플릿 관리."""

import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk, ImageFilter, ImageEnhance, ImageChops

from .editor import Editor, Layer
from .file_manager import FileManager
from .selection import SelectionManager

# 디자인 토큰
BG_MAIN = "#1e1e1e"
BG_SIDEBAR = "#252526"
BG_PANEL = "#2d2d2d"
BG_INPUT = "#3c3c3c"
FG = "#cccccc"
FG_DIM = "#888888"
FG_DISABLED = "#555555"
ACCENT = "#007acc"
ACCENT_DANGER = "#c94040"
ACCENT_SUCCESS = "#4ec9b0"
ACCENT_WARN = "#d7ba7d"
BORDER = "#404040"
FONT = ("Segoe UI", 9)
FONT_SM = ("Segoe UI", 8)
FONT_BD = ("Segoe UI", 9, "bold")

SHORTCUTS = """◀ / A : 이전    ▶ / D : 다음
1: 모자이크  2: 블러  3: 가리기  4: 펜
Ctrl+Z: 취소   Ctrl+Y: 재실행   Ctrl+S: 저장
Delete: 삭제   Space: 화면맞춤   Escape: 해제/복귀"""


class Viewer(tk.Frame):
    def __init__(self, master, fm: FileManager, on_back):
        super().__init__(master, bg=BG_MAIN)
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
        self._prefetch: dict[int, Image.Image] = {}
        self._active = False
        self._status_clear_id = None
        self._batch_lock = False  # 배치 작업 진행 중 플래그

        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

    # ==================== UI 빌드 ====================

    def _build_toolbar(self):
        # 행 1: 네비게이션 + 도구
        r1 = tk.Frame(self, bg=BG_PANEL)
        r1.pack(fill=tk.X)

        tk.Button(r1, text="◀ 그리드 Esc", font=FONT_SM, command=self._go_back,
                  bg=BG_INPUT, fg=FG, bd=0, padx=6).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(r1, text="◀", font=FONT_SM, command=self._prev, bg=BG_INPUT, fg=FG, bd=0, width=3).pack(side=tk.LEFT)
        self.lbl_pos = tk.Label(r1, text="", bg=BG_PANEL, fg=FG, font=FONT)
        self.lbl_pos.pack(side=tk.LEFT, padx=6)
        tk.Button(r1, text="▶", font=FONT_SM, command=self._next, bg=BG_INPUT, fg=FG, bd=0, width=3).pack(side=tk.LEFT)

        tk.Frame(r1, width=16, bg=BG_PANEL).pack(side=tk.LEFT)

        self.tool_btns = {}
        for label, key in [("모자이크 1", "mosaic"), ("블러 2", "blur"), ("가리기 3", "fill"), ("펜 4", "pen")]:
            b = tk.Button(r1, text=label, font=FONT_SM, bg=BG_INPUT, fg=FG, bd=1, padx=4,
                          command=lambda t=key: self._set_tool(t))
            b.pack(side=tk.LEFT, padx=1, pady=2)
            self.tool_btns[key] = b

        tk.Button(r1, text="이미지삭제 Del", font=FONT_SM, bg=BG_INPUT, fg=ACCENT_DANGER, bd=0, padx=6,
                  command=self._delete).pack(side=tk.RIGHT, padx=4, pady=2)

        # 행 2: 색상 + 굵기
        r2 = tk.Frame(self, bg=BG_SIDEBAR)
        r2.pack(fill=tk.X)

        tk.Label(r2, text="색상:", bg=BG_SIDEBAR, fg=FG_DIM, font=FONT_SM).pack(side=tk.LEFT, padx=4)
        for rgb, hx in [((0,0,0),"#000"), ((255,0,0),"#e44"), ((0,100,255),"#06f"), ((255,255,255),"#fff")]:
            tk.Button(r2, bg=hx, width=2, bd=1, relief=tk.GROOVE,
                      command=lambda c=rgb: self._set_color(c)).pack(side=tk.LEFT, padx=1, pady=2)

        tk.Label(r2, text="  굵기:", bg=BG_SIDEBAR, fg=FG_DIM, font=FONT_SM).pack(side=tk.LEFT)
        self.width_var = tk.IntVar(value=3)
        tk.Scale(r2, from_=1, to=20, orient=tk.HORIZONTAL, variable=self.width_var,
                 bg=BG_SIDEBAR, fg=FG, troughcolor=BG_INPUT, highlightthickness=0, length=80,
                 showvalue=True, font=FONT_SM,
                 command=lambda v: setattr(self.editor, 'pen_width', int(v))).pack(side=tk.LEFT)

        tk.Button(r2, text="이미지초기화", font=FONT_SM, bg=BG_INPUT, fg=FG, bd=0, padx=4,
                  command=self._reset_edits).pack(side=tk.LEFT, padx=4)
        tk.Button(r2, text="전체초기화", font=FONT_SM, bg=BG_INPUT, fg=ACCENT_DANGER, bd=0, padx=4,
                  command=self._reset_all).pack(side=tk.LEFT, padx=4)
        tk.Button(r2, text="?", font=FONT_SM, bg=BG_INPUT, fg=FG_DIM, bd=0, width=2,
                  command=lambda: messagebox.showinfo("단축키", SHORTCUTS)).pack(side=tk.RIGHT, padx=4)

    def _build_main(self):
        main = tk.Frame(self, bg=BG_MAIN)
        main.pack(fill=tk.BOTH, expand=True)

        # 캔버스
        self.canvas = tk.Canvas(main, bg=BG_MAIN, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

        # 선택 매니저
        self.sel = SelectionManager(self.editor, self.canvas, self._c2i, self._i2c)

        # 사이드바
        sb = tk.Frame(main, bg=BG_SIDEBAR, width=200)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        sb.pack_propagate(False)

        self._build_applied_section(sb)
        self._build_manage_section(sb)
        self._build_layer_section(sb)

    def _build_applied_section(self, parent):
        """섹션 1: 템플릿 적용 — 전체 목록을 체크박스로. 원클릭 토글."""
        f = tk.LabelFrame(parent, text=" 템플릿 적용 ", bg=BG_SIDEBAR, fg=FG, font=FONT_BD,
                          bd=1, relief=tk.GROOVE, labelanchor=tk.NW)
        f.pack(fill=tk.X, padx=4, pady=3)
        self.applied_frame = f

        self.applied_checks: dict[str, tk.BooleanVar] = {}
        self.applied_inner = tk.Frame(f, bg=BG_SIDEBAR)
        self.applied_inner.pack(fill=tk.X, padx=2)

        btn_row = tk.Frame(f, bg=BG_SIDEBAR)
        btn_row.pack(fill=tk.X, padx=2, pady=2)
        tk.Button(btn_row, text="전체적용", font=FONT_SM, bg=BG_INPUT, fg=ACCENT, bd=0, padx=4,
                  command=self._apply_to_all_images).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="전체해제", font=FONT_SM, bg=BG_INPUT, fg=FG_DIM, bd=0, padx=4,
                  command=self._unapply_from_all_images).pack(side=tk.LEFT, padx=1)

    def _build_manage_section(self, parent):
        """섹션 2: 템플릿 관리."""
        f = tk.LabelFrame(parent, text=" 템플릿 관리 ", bg=BG_SIDEBAR, fg=FG, font=FONT_BD,
                          bd=1, relief=tk.GROOVE, labelanchor=tk.NW)
        f.pack(fill=tk.X, padx=4, pady=3)

        self.tpl_listbox = tk.Listbox(f, bg=BG_INPUT, fg=FG, selectbackground=ACCENT,
                                       height=4, font=FONT_SM, bd=0, highlightthickness=0)
        self.tpl_listbox.pack(fill=tk.X, padx=2, pady=2)
        self.tpl_listbox.bind("<FocusIn>", lambda e: self.canvas.focus_set())
        self.tpl_listbox.bind("<Double-Button-1>", self._rename_template)

        btn_row = tk.Frame(f, bg=BG_SIDEBAR)
        btn_row.pack(fill=tk.X, padx=2, pady=2)
        tk.Button(btn_row, text="제작", font=FONT_SM, bg=ACCENT_SUCCESS, fg="#000", bd=0, padx=4,
                  command=self._start_template).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="편집", font=FONT_SM, bg=BG_INPUT, fg=FG, bd=0, padx=4,
                  command=self._edit_template).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="삭제", font=FONT_SM, bg=BG_INPUT, fg=ACCENT_DANGER, bd=0, padx=4,
                  command=self._delete_template).pack(side=tk.LEFT, padx=1)

    def _build_layer_section(self, parent):
        """섹션 3: 레이어 (제작 모드 전용)."""
        self.layer_frame = tk.LabelFrame(parent, text=" 레이어 (비활성) ", bg=BG_SIDEBAR, fg=FG_DISABLED,
                                          font=FONT_BD, bd=1, relief=tk.GROOVE, labelanchor=tk.NW)
        self.layer_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=3)

        btn_row = tk.Frame(self.layer_frame, bg=BG_SIDEBAR)
        btn_row.pack(fill=tk.X, padx=2, pady=2)
        for txt, cmd in [("+", self._add_layer), ("−", self._remove_layer),
                         ("▲", lambda: self._move_layer(-1)), ("▼", lambda: self._move_layer(1)),
                         ("👁", self._toggle_layer)]:
            tk.Button(btn_row, text=txt, font=FONT_SM, bg=BG_INPUT, fg=FG, bd=0, width=2,
                      command=cmd).pack(side=tk.LEFT, padx=1)

        self.layer_listbox = tk.Listbox(self.layer_frame, bg=BG_INPUT, fg=FG, selectbackground=ACCENT,
                                         height=5, font=FONT_SM, bd=0, highlightthickness=0)
        self.layer_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.layer_listbox.bind("<<ListboxSelect>>", self._on_layer_select)
        self.layer_listbox.bind("<Double-Button-1>", self._rename_layer)
        self.layer_listbox.bind("<FocusIn>", lambda e: self.canvas.focus_set())

        # 제작 모드 버튼 (초기 숨김)
        self.tpl_action_frame = tk.Frame(self.layer_frame, bg=BG_SIDEBAR)
        self.btn_tpl_save = tk.Button(self.tpl_action_frame, text="저장 완료", font=FONT,
                                       bg=ACCENT, fg="#fff", bd=0, padx=8, command=self._save_template)
        self.btn_tpl_cancel = tk.Button(self.tpl_action_frame, text="취소", font=FONT,
                                         bg=BG_INPUT, fg=FG, bd=0, padx=8, command=self._cancel_template)

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=BG_PANEL, height=22)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        sb.pack_propagate(False)

        self.status_mode = tk.Label(sb, text="모드: 일반", bg=BG_PANEL, fg=FG_DIM, font=FONT_SM, anchor=tk.W)
        self.status_mode.pack(side=tk.LEFT, padx=8)
        self.status_tool = tk.Label(sb, text="도구: —", bg=BG_PANEL, fg=FG_DIM, font=FONT_SM)
        self.status_tool.pack(side=tk.LEFT, padx=8)
        self.status_info = tk.Label(sb, text="", bg=BG_PANEL, fg=FG_DIM, font=FONT_SM)
        self.status_info.pack(side=tk.LEFT, padx=8)
        self.status_msg = tk.Label(sb, text="", bg=BG_PANEL, fg=ACCENT_SUCCESS, font=FONT_SM, anchor=tk.E)
        self.status_msg.pack(side=tk.RIGHT, padx=8)

    # ==================== 상태 표시 ====================

    def _update_status(self):
        if self.editor.template_mode:
            name = self.editor._editing_template_name or "새 템플릿"
            layer = self.editor.active_layer
            layer_name = layer.name if layer else "—"
            self.status_mode.config(text=f"모드: 템플릿 제작 \"{name}\"", fg=ACCENT_WARN)
        else:
            self.status_mode.config(text="모드: 일반", fg=FG_DIM)

        tool_names = {"mosaic": "모자이크", "blur": "블러", "fill": "가리기", "pen": "펜"}
        t = self.editor.current_tool
        self.status_tool.config(text=f"도구: {tool_names.get(t, '—')}")

        n_edits = len(self.editor.edits)
        n_tpl = len(self.editor.applied_templates)
        tpl_names = ", ".join(self.editor.applied_templates) if self.editor.applied_templates else "없음"
        info = f"직접편집: {n_edits} │ 🛡 템플릿: {n_tpl} ({tpl_names})"
        self.status_info.config(text=info, fg=ACCENT_SUCCESS if n_tpl > 0 else FG_DIM)

    def _flash_status(self, msg: str, color=ACCENT_SUCCESS, duration=2000):
        self.status_msg.config(text=msg, fg=color)
        if self._status_clear_id:
            self.after_cancel(self._status_clear_id)
        self._status_clear_id = self.after(duration, lambda: self.status_msg.config(text=""))

    # ==================== 적용된 템플릿 (섹션 1) ====================

    def _refresh_applied(self):
        """모든 템플릿을 체크박스로 나열. 적용된 것은 체크 상태."""
        for w in self.applied_inner.winfo_children():
            w.destroy()
        self.applied_checks.clear()

        if self.editor.template_mode:
            tk.Label(self.applied_inner, text="(제작 중 비활성)", bg=BG_SIDEBAR, fg=FG_DISABLED, font=FONT_SM).pack(anchor=tk.W)
            return

        templates = self.fm.list_templates()
        if not templates:
            tk.Label(self.applied_inner, text="(템플릿 없음)", bg=BG_SIDEBAR, fg=FG_DISABLED, font=FONT_SM).pack(anchor=tk.W)
            return

        for name in templates:
            applied = name in self.editor.applied_templates
            var = tk.BooleanVar(value=applied)
            self.applied_checks[name] = var
            cb = tk.Checkbutton(self.applied_inner, text=name, variable=var, bg=BG_SIDEBAR,
                                fg=FG if applied else FG_DIM, selectcolor=BG_INPUT,
                                activebackground=BG_SIDEBAR, font=FONT_SM,
                                command=lambda n=name: self._on_applied_toggle(n))
            cb.pack(anchor=tk.W, padx=2)

    def _on_applied_toggle(self, name: str):
        var = self.applied_checks.get(name)
        if not var:
            return
        if var.get():
            # 적용
            if name not in self.editor.applied_templates:
                self.editor.applied_templates.append(name)
            self._flash_status(f"'{name}' 적용됨")
        else:
            # 해제
            if name in self.editor.applied_templates:
                self.editor.applied_templates.remove(name)
            self._flash_status(f"'{name}' 해제됨")
        self._save()
        self._render()
        self._refresh_applied()
        self._update_status()

    def _run_batch(self, action_name, batch_func, images, template_names):
        """배치 작업 공통. 진행 중이면 대기 후 실행."""
        if self._batch_lock:
            self._flash_status("이전 작업 완료 후 시도하세요", ACCENT_WARN)
            return
        self._batch_lock = True
        n = len(images) + 1  # 현재 이미지 포함
        c = len(template_names)
        self._flash_status(f"{action_name} 중... ({n}장)", ACCENT_WARN, duration=60000)
        import threading
        def _work():
            batch_func(images, template_names)
            self._batch_lock = False
            self.after(0, lambda: self._flash_status(f"✓ {n}장 {action_name} 완료", ACCENT_SUCCESS, 5000))
        threading.Thread(target=_work, daemon=True).start()

    def _apply_to_all_images(self):
        """현재 체크된 템플릿을 세션 내 모든 이미지에 적용 (비동기)."""
        if self.editor.template_mode or self._batch_lock:
            if self._batch_lock:
                self._flash_status("이전 작업 완료 후 시도하세요", ACCENT_WARN)
            return
        checked = [n for n, v in self.applied_checks.items() if v.get()]
        if not checked:
            self._flash_status("적용할 템플릿을 체크하세요", ACCENT_WARN)
            return
        # 현재 이미지 즉시 반영
        for name in checked:
            if name not in self.editor.applied_templates:
                self.editor.applied_templates.append(name)
        self._save()
        self._render()
        self._refresh_applied()
        self._update_status()
        # 나머지 비동기
        images = [p for i, p in enumerate(self.images) if i != self.index]
        self._run_batch("전체 적용", self.fm.batch_apply_templates, images, checked)

    def _unapply_from_all_images(self):
        """현재 체크된 템플릿을 세션 내 모든 이미지에서 해제 (비동기)."""
        if self.editor.template_mode or self._batch_lock:
            if self._batch_lock:
                self._flash_status("이전 작업 완료 후 시도하세요", ACCENT_WARN)
            return
        checked = [n for n, v in self.applied_checks.items() if v.get()]
        if not checked:
            self._flash_status("해제할 템플릿을 체크하세요", ACCENT_WARN)
            return
        # 현재 이미지 즉시 반영
        for name in checked:
            if name in self.editor.applied_templates:
                self.editor.applied_templates.remove(name)
        self._save()
        self._render()
        self._refresh_applied()
        self._update_status()
        # 나머지 비동기
        images = [p for i, p in enumerate(self.images) if i != self.index]
        self._run_batch("전체 해제", self.fm.batch_unapply_templates, images, checked)

    # ==================== 템플릿 관리 (섹션 2) ====================

    def _refresh_templates(self):
        self.tpl_listbox.delete(0, tk.END)
        for name in self.fm.list_templates():
            layers = self.fm.load_named_template(name)
            total = sum(len(l.get("edits", [])) for l in layers)
            self.tpl_listbox.insert(tk.END, f"{name} ({len(layers)}L, {total}편집)")

    def _start_template(self):
        if self.editor.template_mode:
            return
        self.editor.start_template_create()
        self._enter_template_ui()

    def _edit_template(self):
        if self.editor.template_mode:
            return
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if not sel or sel[0] >= len(templates):
            messagebox.showinfo("알림", "편집할 템플릿을 선택하세요.")
            return
        name = templates[sel[0]]
        layers = self.fm.load_named_template(name)
        self.editor.start_template_edit(name, layers)
        self._enter_template_ui()

    def _save_template(self):
        if not self.editor.template_mode:
            return
        old_name = self.editor._editing_template_name
        default = old_name or ""
        name = simpledialog.askstring("템플릿 저장", "템플릿 이름:", initialvalue=default)
        if not name:
            return  # 취소 → 제작 모드 유지

        _, layers = self.editor.finish_template()
        if not layers:
            messagebox.showinfo("알림", "편집 내용이 없습니다.")
            self._exit_template_ui()
            return

        # 이름이 바뀌었으면 이전 것 삭제
        if old_name and old_name != name:
            self.fm.delete_template(old_name)
        self.fm.save_named_template(name, layers)
        self._exit_template_ui()
        self._refresh_templates()
        self._flash_status(f"템플릿 '{name}' 저장됨")

    def _cancel_template(self):
        self.editor.cancel_template()
        self._exit_template_ui()

    def _enter_template_ui(self):
        self.layer_frame.config(fg=FG, text=" 레이어 (제작 중) ")
        self.tpl_action_frame.pack(fill=tk.X, padx=2, pady=4)
        self.btn_tpl_save.pack(side=tk.LEFT, padx=2)
        self.btn_tpl_cancel.pack(side=tk.LEFT, padx=2)
        self._refresh_layers()
        self._refresh_applied()
        self._render()
        self._update_status()

    def _exit_template_ui(self):
        self.layer_frame.config(fg=FG_DISABLED, text=" 레이어 (비활성) ")
        self.btn_tpl_save.pack_forget()
        self.btn_tpl_cancel.pack_forget()
        self.tpl_action_frame.pack_forget()
        self.layer_listbox.delete(0, tk.END)
        self._refresh_applied()
        self._render()
        self._update_status()

    def _rename_template(self, event=None):
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if not sel or sel[0] >= len(templates):
            return
        old = templates[sel[0]]
        new = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=old)
        if new and new != old:
            self.fm.rename_template(old, new)
            self._refresh_templates()

    def _delete_template(self):
        sel = self.tpl_listbox.curselection()
        templates = self.fm.list_templates()
        if sel and sel[0] < len(templates):
            self.fm.delete_template(templates[sel[0]])
            self._refresh_templates()

    # ==================== 레이어 (섹션 3) ====================

    def _refresh_layers(self):
        self.layer_listbox.delete(0, tk.END)
        if not self.editor.template_mode:
            return
        for i, layer in enumerate(self.editor.template_layers):
            vis = "◉" if layer.visible else "○"
            act = "▶" if i == self.editor.active_layer_idx else "  "
            self.layer_listbox.insert(tk.END, f"{act}{vis} {layer.name} ({len(layer.edits)})")
        if 0 <= self.editor.active_layer_idx < len(self.editor.template_layers):
            self.layer_listbox.selection_set(self.editor.active_layer_idx)

    def _on_layer_select(self, event):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.set_active_layer(sel[0])
            self._refresh_layers()
            self._update_status()

    def _add_layer(self):
        if not self.editor.template_mode:
            return
        name = simpledialog.askstring("새 레이어", "이름:", initialvalue=f"레이어 {len(self.editor.template_layers)+1}")
        if name:
            self.editor.add_layer(name)
            self._refresh_layers()

    def _remove_layer(self):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.remove_layer(sel[0])
            self._render()
            self._refresh_layers()

    def _move_layer(self, d):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.move_layer(sel[0], d)
            self._render()
            self._refresh_layers()

    def _toggle_layer(self):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel:
            self.editor.toggle_layer(sel[0])
            self._render()
            self._refresh_layers()

    def _rename_layer(self, event=None):
        if not self.editor.template_mode:
            return
        sel = self.layer_listbox.curselection()
        if sel and sel[0] < len(self.editor.template_layers):
            layer = self.editor.template_layers[sel[0]]
            new = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=layer.name)
            if new:
                layer.name = new
                self._refresh_layers()

    # ==================== 키보드 ====================

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
        for k in ["<Left>","<Right>","<a>","<d>","<Escape>","<Delete>",
                   "<Control-s>","<Control-z>","<Control-y>","<space>",
                   "<Key-1>","<Key-2>","<Key-3>","<Key-4>"]:
            root.unbind(k)

    # ==================== 이미지 ====================

    def show(self, images: list[Path], index: int):
        self.images = images
        self._prefetch.clear()
        self._go_to(index)
        self._refresh_templates()
        self._start_autosave()

    def _go_to(self, index: int):
        if self.pil_orig is not None and self.editor.is_dirty:
            self._save()
        self.index = index
        path = self.images[self.index]
        self.lbl_pos.config(text=f"{self.index+1}/{len(self.images)}  {path.stem}")

        self.pil_orig = self._prefetch.pop(self.index, None) or Image.open(path).convert("RGB")

        data = self.fm.load_image_data(path)
        self.editor.load_image_data(data["edits"], data["applied_templates"])

        self.fit_mode = True
        self._render()
        self._refresh_applied()
        self._update_status()
        self._do_prefetch()

    def _do_prefetch(self):
        import threading
        for off in [-1, 1]:
            idx = self.index + off
            if 0 <= idx < len(self.images) and idx not in self._prefetch:
                def _load(i=idx):
                    try: self._prefetch[i] = Image.open(self.images[i]).convert("RGB")
                    except: pass
                threading.Thread(target=_load, daemon=True).start()

    def _render(self):
        if not self.pil_orig:
            return

        if self.editor.template_mode:
            # 템플릿 편집 모드: 배경 어둡게 + 템플릿 편집만 선명
            # 1. 배경: 원본 + 적용된 템플릿 + 직접 편집 (어둡게)
            bg_edits = []
            for tpl_name in self.editor.applied_templates:
                layers = self.fm.load_named_template(tpl_name)
                for layer in layers:
                    if layer.get("visible", True):
                        bg_edits.extend(layer.get("edits", []))
            bg_edits.extend(self.editor.edits)
            bg_img = FileManager.apply_edits(self.pil_orig, bg_edits) if bg_edits else self.pil_orig.copy()
            # glass 효과: 블러 + 밝게 + 채도 낮춤
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=8))
            bg_img = ImageEnhance.Color(bg_img).enhance(0.2)        # 거의 무채색
            bg_img = ImageEnhance.Brightness(bg_img).enhance(1.4)   # 밝게

            # 2. 템플릿 편집을 위에 합성
            tpl_edits = []
            for layer in self.editor.template_layers:
                if layer.visible:
                    tpl_edits.extend(layer.edits)
            if tpl_edits:
                # 원본에 템플릿 편집만 적용한 이미지
                tpl_img = FileManager.apply_edits(self.pil_orig, tpl_edits)
                # 템플릿 편집 영역만 밝게 합성
                # 편집된 부분만 원본과 다른 곳 → 마스크
                diff = ImageChops.difference(tpl_img, self.pil_orig)
                # diff가 0이 아닌 곳 = 편집된 곳
                mask = diff.convert("L").point(lambda x: 255 if x > 0 else 0)
                bg_img.paste(tpl_img, mask=mask)
            img = bg_img
        else:
            # 일반 모드
            edits = self.editor.all_visible_edits(self.fm)
            img = FileManager.apply_edits(self.pil_orig, edits) if edits else self.pil_orig

        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10: cw = 800
        if ch < 10: ch = 600
        if self.fit_mode:
            self.zoom = min(cw / img.width, ch / img.height)
        dw, dh = max(1, int(img.width * self.zoom)), max(1, int(img.height * self.zoom))
        disp = img.resize((dw, dh), Image.LANCZOS) if self.zoom != 1.0 else img

        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.tk_img, anchor=tk.CENTER)
        self.sel.draw_overlay()

    def _c2i(self, cx, cy):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        dw, dh = self.pil_orig.width * self.zoom, self.pil_orig.height * self.zoom
        ix = int((cx - (cw - dw)/2) / self.zoom)
        iy = int((cy - (ch - dh)/2) / self.zoom)
        return max(0, min(ix, self.pil_orig.width-1)), max(0, min(iy, self.pil_orig.height-1))

    def _i2c(self, ix, iy):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        dw, dh = self.pil_orig.width * self.zoom, self.pil_orig.height * self.zoom
        cx = ix * self.zoom + (cw - dw) / 2
        cy = iy * self.zoom + (ch - dh) / 2
        return cx, cy

    # ==================== 마우스 ====================

    def _on_press(self, event):
        t = self.editor.current_tool
        if t:
            # 도구 모드: 새 편집 추가
            self.sel.deselect()
            if t == "pen":
                self.editor.pen_start(*self._c2i(event.x, event.y))
                self._drag_start = (event.x, event.y)
            elif t in ("mosaic","blur","fill"):
                self._drag_start = (event.x, event.y)
        else:
            # 선택 모드
            handle = self.sel.hit_handle(event.x, event.y)
            if handle:
                ix, iy = self._c2i(event.x, event.y)
                self.sel.start_resize(handle, ix, iy)
            else:
                ix, iy = self._c2i(event.x, event.y)
                idx = self.sel.hit_test(ix, iy)
                if idx is not None:
                    self.sel.select(idx)
                    self.sel.start_move(ix, iy)
                else:
                    self.sel.deselect()

    def _on_drag(self, event):
        t = self.editor.current_tool
        if t:
            # 도구 모드
            if t == "pen" and self._drag_start:
                self.editor.pen_move(*self._c2i(event.x, event.y))
                self.canvas.create_line(self._drag_start[0], self._drag_start[1], event.x, event.y,
                                        fill=f"#{self.editor.pen_color[0]:02x}{self.editor.pen_color[1]:02x}{self.editor.pen_color[2]:02x}",
                                        width=max(1, int(self.editor.pen_width * self.zoom)))
                self._drag_start = (event.x, event.y)
            elif t in ("mosaic","blur","fill") and self._drag_start:
                if self._rect_id: self.canvas.delete(self._rect_id)
                self._rect_id = self.canvas.create_rectangle(
                    self._drag_start[0], self._drag_start[1], event.x, event.y, outline="#ffcc00", dash=(4,4))
        elif self.sel.is_dragging:
            # 선택 모드: 이동/리사이즈
            ix, iy = self._c2i(event.x, event.y)
            self.sel.update_drag(ix, iy, self._render)

    def _on_release(self, event):
        t = self.editor.current_tool
        if t:
            # 도구 모드
            if t == "pen":
                self.editor.finish_pen()
                self._render()
                if self.editor.template_mode: self._refresh_layers()
            elif t in ("mosaic","blur","fill") and self._drag_start:
                if self._rect_id: self.canvas.delete(self._rect_id); self._rect_id = None
                x1,y1 = self._c2i(*self._drag_start)
                x2,y2 = self._c2i(event.x, event.y)
                box = (min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
                if box[2]-box[0]>2 and box[3]-box[1]>2:
                    {"mosaic": self.editor.add_mosaic, "blur": self.editor.add_blur, "fill": self.editor.add_fill}[t](box)
                    self._render()
                    if self.editor.template_mode: self._refresh_layers()
            self._drag_start = None
        elif self.sel.is_dragging:
            self.sel.end_drag()
        self._update_status()

    def _on_wheel(self, event):
        self.zoom *= 1.1 if event.delta > 0 else 1/1.1
        self.zoom = max(0.1, min(self.zoom, 5.0))
        self.fit_mode = False
        self._render()

    # ==================== 액션 ====================

    def _set_tool(self, tool):
        if self.editor.current_tool == tool:
            self.editor.set_tool(None)
        else:
            self.editor.set_tool(tool)
            self.sel.deselect()  # 도구 선택 시 선택 해제
        for t, b in self.tool_btns.items():
            b.config(relief=tk.SUNKEN if t == self.editor.current_tool else tk.RAISED)
        self._update_status()

    def _set_color(self, c):
        self.editor.pen_color = c
        self.editor.fill_color = c

    def _prev(self):
        if self.editor.template_mode:
            self._flash_status("템플릿 제작 중 이동 불가", ACCENT_WARN)
            return
        if self.index > 0: self._go_to(self.index - 1)

    def _next(self):
        if self.editor.template_mode:
            self._flash_status("템플릿 제작 중 이동 불가", ACCENT_WARN)
            return
        if self.index < len(self.images)-1: self._go_to(self.index + 1)

    def _go_back(self):
        if self.editor.template_mode:
            messagebox.showinfo("알림", "템플릿 제작을 먼저 완료하거나 취소하세요.")
            return
        if self.editor.is_dirty: self._save()
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
            self.fm.save_image_data(self.images[self.index], self.editor.edits, self.editor.applied_templates)
            self._flash_status("저장됨 ✓")

    def _undo(self):
        if self.editor.undo():
            self._render()
            if self.editor.template_mode: self._refresh_layers()
            self._update_status()

    def _redo(self):
        if self.editor.redo():
            self._render()
            if self.editor.template_mode: self._refresh_layers()
            self._update_status()

    def _toggle_fit(self):
        self.fit_mode = not self.fit_mode
        self._render()

    def _delete(self):
        # 선택된 편집 요소가 있으면 그것만 삭제
        if self.sel.selected_idx is not None:
            if self.sel.delete_selected():
                self._render()
                if self.editor.template_mode: self._refresh_layers()
                self._update_status()
                self._flash_status("편집 요소 삭제됨")
            return
        if self.editor.template_mode or not self.images: return
        self.fm.soft_delete(self.images[self.index])
        self.images = self.fm.list_images()
        if not self.images:
            self._go_back()
            return
        self.index = min(self.index, len(self.images)-1)
        self.editor.clear_all()
        self._prefetch.clear()
        self._go_to(self.index)
        self._flash_status("삭제됨 (복구 가능)")

    def _reset_edits(self):
        if self.editor.template_mode: return
        self.editor.clear_edits()
        self.editor.applied_templates.clear()
        self._save()
        self._render()
        self._refresh_applied()
        self._update_status()
        self._flash_status("현재 이미지 초기화됨")

    def _reset_all(self):
        if self.editor.template_mode: return
        if not messagebox.askyesno("전체 초기화", "모든 이미지의 편집과 템플릿 적용을 초기화합니다.\n계속하시겠습니까?"):
            return
        self._flash_status("전체 초기화 중...", ACCENT_WARN, duration=30000)
        import threading
        def _work():
            for img_path in self.images:
                edit_path = self.fm._edit_path(img_path)
                edit_path.unlink(missing_ok=True)
            self.after(0, self._after_reset_all)
        threading.Thread(target=_work, daemon=True).start()

    def _after_reset_all(self):
        self.editor.clear_all()
        self._render()
        self._refresh_applied()
        self._update_status()
        self._flash_status("✓ 전체 초기화 완료", ACCENT_SUCCESS, 5000)

    # ==================== 오토세이브 ====================

    def _start_autosave(self):
        def _tick():
            if self.images and self.editor.is_dirty and not self.editor.template_mode:
                self.fm.autosave(self.images[self.index], self.editor.edits, self.editor.applied_templates)
                self._flash_status("자동저장 ✓", duration=1500)
            self._autosave_id = self.after(10000, _tick)
        self._autosave_id = self.after(10000, _tick)

    def _stop_autosave(self):
        if self._autosave_id:
            self.after_cancel(self._autosave_id)
            self._autosave_id = None
        self.fm.clear_autosave()
