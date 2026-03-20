"""그리드 뷰 — 썸네일 브라우징, 선택, 일괄 작업."""

import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import Image, ImageTk

from .file_manager import FileManager

BG = "#1e1e1e"
BG_PANEL = "#2d2d2d"
BG_INPUT = "#3c3c3c"
FG = "#cccccc"
FG_DIM = "#888888"
ACCENT = "#007acc"
ACCENT_LIGHT = "#264f78"
FONT = ("Segoe UI", 9)
FONT_SM = ("Segoe UI", 8)

THUMB_W = 200
THUMB_H = 112
PAD = 6


class GridView(tk.Frame):
    def __init__(self, master, fm: FileManager, on_select):
        super().__init__(master, bg=BG)
        self.fm = fm
        self.on_select = on_select
        self.images: list[Path] = []
        self.thumb_cache: dict[str, ImageTk.PhotoImage] = {}
        self.selected: set[int] = set()
        self._frames: list[tk.Frame] = []
        self.focus_idx = 0
        self._active = False
        self._cached_cols = 1

        # 상단 바
        top = tk.Frame(self, bg=BG_PANEL)
        top.pack(fill=tk.X)

        self.lbl_info = tk.Label(top, text="", bg=BG_PANEL, fg=FG, font=FONT, anchor=tk.W)
        self.lbl_info.pack(side=tk.LEFT, padx=8, pady=4)
        self.lbl_sel = tk.Label(top, text="", bg=BG_PANEL, fg=FG_DIM, font=FONT_SM)
        self.lbl_sel.pack(side=tk.LEFT, padx=4)

        for txt, cmd in [("내보내기", self._export), ("템플릿 적용", self._batch_apply),
                         ("삭제된 파일", self._show_deleted)]:
            tk.Button(top, text=txt, font=FONT_SM, bg=BG_INPUT, fg=FG, bd=0, padx=6,
                      command=cmd).pack(side=tk.RIGHT, padx=2, pady=4)

        # 캔버스
        container = tk.Frame(self, bg=BG)
        container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self.canvas_win = self.canvas.create_window((0, 0), window=self.inner, anchor=tk.NW)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)

        # 하단 힌트
        hint = tk.Frame(self, bg=BG_PANEL)
        hint.pack(fill=tk.X)
        tk.Label(hint, text="WASD/화살표: 이동 │ Enter: 열기 │ Space: 선택토글 │ Ctrl+A: 전체 │ Del: 삭제",
                 bg=BG_PANEL, fg=FG_DIM, font=FONT_SM).pack(padx=8, pady=2)

    # ==================== 활성화/비활성화 ====================

    def activate(self):
        self._active = True
        root = self.winfo_toplevel()
        root.bind("<Up>", lambda e: self._move(-self._cached_cols))
        root.bind("<Down>", lambda e: self._move(self._cached_cols))
        root.bind("<Left>", lambda e: self._move(-1))
        root.bind("<Right>", lambda e: self._move(1))
        root.bind("<w>", lambda e: self._move(-self._cached_cols))
        root.bind("<s>", lambda e: self._move(self._cached_cols))
        root.bind("<a>", lambda e: self._move(-1))
        root.bind("<d>", lambda e: self._move(1))
        root.bind("<Return>", lambda e: self._open())
        root.bind("<space>", lambda e: self._toggle_select())
        root.bind("<Delete>", lambda e: self._delete_selected())
        root.bind("<Control-a>", lambda e: self._select_all())
        root.bind_all("<MouseWheel>", self._on_wheel)

    def deactivate(self):
        self._active = False
        root = self.winfo_toplevel()
        for k in ["<Up>","<Down>","<Left>","<Right>","<w>","<s>","<a>","<d>",
                   "<Return>","<space>","<Delete>","<Control-a>"]:
            root.unbind(k)

    # ==================== 네비게이션 ====================

    def _move(self, delta: int):
        if not self._active or not self.images:
            return
        new = self.focus_idx + delta
        if 0 <= new < len(self.images):
            self.focus_idx = new
            self.selected = {new}
            self._update_display()
            self._scroll_to_focus()

    def _open(self):
        if self._active and self.images:
            self.on_select(self.focus_idx)

    def _toggle_select(self):
        if not self._active:
            return
        if self.focus_idx in self.selected:
            self.selected.discard(self.focus_idx)
        else:
            self.selected.add(self.focus_idx)
        self._update_display()

    def _select_all(self):
        self.selected = set(range(len(self.images)))
        self._update_display()

    def _delete_selected(self):
        if not self._active or not self.selected:
            return
        for idx in sorted(self.selected, reverse=True):
            if idx < len(self.images):
                self.fm.soft_delete(self.images[idx])
        self.refresh()

    def _scroll_to_focus(self):
        if self.focus_idx >= len(self._frames):
            return
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        w = self._frames[self.focus_idx]
        y, h = w.winfo_y(), w.winfo_height()
        total = bbox[3]
        ch = self.canvas.winfo_height()
        if total > ch:
            self.canvas.yview_moveto(max(0, min(1, (y - ch//2 + h//2) / total)))

    def _on_wheel(self, event):
        if self._active:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ==================== 표시 ====================

    def refresh(self):
        self.images = self.fm.list_images()
        self.lbl_info.config(text=f"{self.fm.session_dir.name}  │  {len(self.images)}장")
        self.focus_idx = min(self.focus_idx, max(0, len(self.images) - 1))
        self.selected = {self.focus_idx} if self.images else set()
        self._frames.clear()
        self._load_thumbs()

    def _on_resize(self, event):
        self.canvas.itemconfig(self.canvas_win, width=event.width)
        self._cached_cols = max(1, event.width // (THUMB_W + PAD))
        self._relayout()

    def _load_thumbs(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.thumb_cache.clear()
        self._frames.clear()

        def _gen():
            for i, p in enumerate(self.images):
                try:
                    tp = self.fm.get_thumbnail(p)
                    pil = Image.open(tp)
                    self.inner.after(0, self._add_thumb, i, p, pil)
                except Exception:
                    pass
        threading.Thread(target=_gen, daemon=True).start()

    def _add_thumb(self, idx: int, path: Path, pil: Image.Image):
        tk_img = ImageTk.PhotoImage(pil)
        self.thumb_cache[path.name] = tk_img

        f = tk.Frame(self.inner, bg=BG, padx=PAD//2, pady=PAD//2,
                     highlightthickness=2, highlightbackground=BG)

        # 썸네일 + 상태 아이콘 오버레이
        thumb_container = tk.Frame(f, bg=BG)
        thumb_container.pack()

        img_label = tk.Label(thumb_container, image=tk_img, bg=BG, cursor="hand2")
        img_label.image = tk_img
        img_label.pack()

        # 상태 아이콘 (썸네일 위 오버레이)
        status = self.fm.get_image_status(path)
        icons = ""
        icon_fg = FG_DIM
        if status["template_count"] > 0:
            icons += f"🛡{status['template_count']}"
            icon_fg = "#4ec9b0"  # 녹색 — 템플릿 적용됨
        if status["has_edits"]:
            icons += " ✏"
        if icons:
            icon_label = tk.Label(thumb_container, text=icons.strip(), bg="#000000", fg=icon_fg,
                                   font=("Segoe UI", 7), padx=2, pady=0)
            icon_label.place(relx=1.0, rely=0.0, anchor=tk.NE, x=-2, y=2)

        # 파일명
        tk.Label(f, text=path.stem, bg=BG, fg=FG_DIM, font=FONT_SM).pack()

        img_label.bind("<Button-1>", lambda e, i=idx: self._on_click(i, e))
        img_label.bind("<Double-Button-1>", lambda e, i=idx: self.on_select(i))

        self._frames.append(f)
        cols = self._cached_cols
        f.grid(row=idx // cols, column=idx % cols)

    def _relayout(self):
        cols = self._cached_cols
        for i, f in enumerate(self._frames):
            f.grid(row=i // cols, column=i % cols)

    def _on_click(self, idx: int, event=None):
        ctrl = event and (event.state & 0x4)
        if ctrl:
            if idx in self.selected:
                self.selected.discard(idx)
            else:
                self.selected.add(idx)
        else:
            self.selected = {idx}
        self.focus_idx = idx
        self._update_display()

    def _update_display(self):
        for i, f in enumerate(self._frames):
            if i == self.focus_idx and i in self.selected:
                f.config(highlightbackground=ACCENT, highlightthickness=3)
            elif i in self.selected:
                f.config(highlightbackground=ACCENT_LIGHT, highlightthickness=2)
            elif i == self.focus_idx:
                f.config(highlightbackground="#555", highlightthickness=2)
            else:
                f.config(highlightbackground=BG, highlightthickness=2)

        n = len(self.selected)
        self.lbl_sel.config(text=f"선택: {n}장" if n > 0 else "")

    # ==================== 일괄 작업 ====================

    def _batch_apply(self):
        if not self.selected:
            messagebox.showinfo("알림", "이미지를 먼저 선택하세요.\nSpace로 토글, Ctrl+A로 전체 선택")
            return
        templates = self.fm.list_templates()
        if not templates:
            messagebox.showinfo("알림", "저장된 템플릿이 없습니다.\n뷰어에서 '제작'으로 만드세요.")
            return

        top = tk.Toplevel(self)
        top.title("템플릿 일괄 적용")
        top.geometry("320x280")
        top.configure(bg=BG_PANEL)

        tk.Label(top, text=f"선택: {len(self.selected)}장 │ 적용할 템플릿:", bg=BG_PANEL, fg=FG, font=FONT).pack(pady=6)

        vars_map = {}
        for name in templates:
            var = tk.BooleanVar(value=False)
            layers = self.fm.load_named_template(name)
            n = sum(len(l.get("edits", [])) for l in layers)
            tk.Checkbutton(top, text=f"{name} ({len(layers)}L, {n}편집)", variable=var,
                           bg=BG_PANEL, fg=FG, selectcolor=BG_INPUT, font=FONT_SM).pack(anchor=tk.W, padx=16)
            vars_map[name] = var

        def _apply():
            chosen = [n for n, v in vars_map.items() if v.get()]
            if not chosen:
                return
            count = 0
            for idx in self.selected:
                if idx < len(self.images):
                    for tpl_name in chosen:
                        self.fm.apply_template_to_image(self.images[idx], tpl_name)
                    count += 1
            top.destroy()
            messagebox.showinfo("완료", f"{count}장에 템플릿 {len(chosen)}개 적용 완료")
            self.refresh()

        tk.Button(top, text="적용", font=FONT, bg=ACCENT, fg="#fff", bd=0, padx=12,
                  command=_apply).pack(pady=8)

    def _export(self):
        top = tk.Toplevel(self)
        top.title("내보내기")
        top.geometry("300x100")
        top.configure(bg=BG_PANEL)
        lbl = tk.Label(top, text="내보내기 중...", bg=BG_PANEL, fg=FG, font=FONT)
        lbl.pack(pady=10)
        bar = tk.Label(top, text="0%", bg=BG_PANEL, fg=FG_DIM, font=FONT)
        bar.pack()

        def _cb(cur, total):
            pct = int(cur/total*100)
            top.after(0, lambda: bar.config(text=f"{pct}% ({cur}/{total})"))
            if cur == total:
                top.after(0, lambda: lbl.config(text="완료!"))
                top.after(1500, top.destroy)

        threading.Thread(target=self.fm.export_all, args=(_cb,), daemon=True).start()

    def _show_deleted(self):
        deleted = self.fm.list_deleted()
        if not deleted:
            messagebox.showinfo("삭제된 파일", "삭제된 파일이 없습니다.")
            return
        top = tk.Toplevel(self)
        top.title("삭제된 파일")
        top.geometry("400x300")
        top.configure(bg=BG_PANEL)

        lb = tk.Listbox(top, bg=BG_INPUT, fg=FG, font=FONT_SM)
        lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for f in deleted:
            lb.insert(tk.END, f.name)

        def _restore():
            sel = lb.curselection()
            if sel:
                self.fm.restore(lb.get(sel[0]))
                lb.delete(sel[0])
                self.refresh()

        tk.Button(top, text="복구", font=FONT, bg=BG_INPUT, fg=FG, bd=0, padx=8,
                  command=_restore).pack(pady=5)
