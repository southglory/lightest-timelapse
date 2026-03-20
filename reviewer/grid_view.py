import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import Image, ImageTk

from .file_manager import FileManager

THUMB_W = 200
THUMB_H = 112
PAD = 8


class GridView(tk.Frame):
    def __init__(self, master, fm: FileManager, on_select):
        super().__init__(master)
        self.fm = fm
        self.on_select = on_select
        self.images: list[Path] = []
        self.thumb_cache: dict[str, ImageTk.PhotoImage] = {}
        self.selected: set[int] = set()
        self._thumb_frames: list[tk.Frame] = []
        self.focus_idx = 0
        self._active = False  # 그리드가 화면에 보일 때만 True

        # 상단 바
        top = tk.Frame(self)
        top.pack(fill=tk.X, padx=4, pady=4)
        self.label_info = tk.Label(top, text="", anchor=tk.W)
        self.label_info.pack(side=tk.LEFT)
        tk.Button(top, text="내보내기", command=self._export).pack(side=tk.RIGHT, padx=4)
        tk.Button(top, text="선택에 템플릿 적용", command=self._apply_template_to_selected).pack(side=tk.RIGHT, padx=4)
        tk.Button(top, text="삭제된 파일", command=self._show_deleted).pack(side=tk.RIGHT, padx=4)

        # 캔버스 + 스크롤
        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(container, bg="#2b2b2b")
        self.scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner = tk.Frame(self.canvas, bg="#2b2b2b")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor=tk.NW)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def activate(self):
        """그리드가 화면에 표시될 때 호출."""
        self._active = True
        self._bind_keys()

    def deactivate(self):
        """그리드가 화면에서 숨겨질 때 호출."""
        self._active = False
        self._unbind_keys()

    def _bind_keys(self):
        self._key_bindings = [
            self.winfo_toplevel().bind("<Up>", lambda e: self._move(-self._cols())),
            self.winfo_toplevel().bind("<Down>", lambda e: self._move(self._cols())),
            self.winfo_toplevel().bind("<Left>", lambda e: self._move(-1)),
            self.winfo_toplevel().bind("<Right>", lambda e: self._move(1)),
            self.winfo_toplevel().bind("<w>", lambda e: self._move(-self._cols())),
            self.winfo_toplevel().bind("<s>", lambda e: self._move(self._cols())),
            self.winfo_toplevel().bind("<a>", lambda e: self._move(-1)),
            self.winfo_toplevel().bind("<d>", lambda e: self._move(1)),
            self.winfo_toplevel().bind("<Return>", lambda e: self._enter_viewer()),
            self.winfo_toplevel().bind("<Delete>", lambda e: self._delete_selected()),
        ]

    def _unbind_keys(self):
        for key in ["<Up>", "<Down>", "<Left>", "<Right>", "<w>", "<s>", "<a>", "<d>", "<Return>", "<Delete>"]:
            self.winfo_toplevel().unbind(key)

    def _move(self, delta: int):
        if not self._active or not self.images:
            return
        new_idx = self.focus_idx + delta
        if 0 <= new_idx < len(self.images):
            self.focus_idx = new_idx
            self.selected = {new_idx}
            self._update_selection_display()
            self._scroll_to_focus()

    def _scroll_to_focus(self):
        if self.focus_idx >= len(self._thumb_frames):
            return
        widget = self._thumb_frames[self.focus_idx]
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        scroll_h = bbox[3]
        canvas_h = self.canvas.winfo_height()
        if scroll_h <= canvas_h:
            return
        y = widget.winfo_y()
        h = widget.winfo_height()
        target = max(0, y - canvas_h // 2 + h // 2) / scroll_h
        self.canvas.yview_moveto(min(1.0, target))

    def _enter_viewer(self):
        if self._active and self.selected:
            self.on_select(self.focus_idx)

    def _delete_selected(self):
        if not self._active or not self.selected:
            return
        for idx in sorted(self.selected, reverse=True):
            if idx < len(self.images):
                self.fm.soft_delete(self.images[idx])
        self.refresh()

    def refresh(self):
        self.images = self.fm.list_images()
        self.label_info.config(text=f"{self.fm.session_dir.name}  ({len(self.images)}장)")
        self.selected.clear()
        self.focus_idx = min(self.focus_idx, max(0, len(self.images) - 1))
        self._thumb_frames.clear()
        self._load_thumbnails()

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        self._layout_thumbs()

    def _on_mousewheel(self, event):
        if self._active:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _load_thumbnails(self):
        for widget in self.inner.winfo_children():
            widget.destroy()
        self.thumb_cache.clear()
        self._thumb_frames.clear()

        def _generate():
            for i, img_path in enumerate(self.images):
                try:
                    thumb_path = self.fm.get_thumbnail(img_path)
                    pil = Image.open(thumb_path)
                    self.inner.after(0, self._add_thumb, i, img_path, pil)
                except Exception:
                    pass

        threading.Thread(target=_generate, daemon=True).start()

    def _add_thumb(self, index: int, img_path: Path, pil: Image.Image):
        tk_img = ImageTk.PhotoImage(pil)
        self.thumb_cache[img_path.name] = tk_img

        frame = tk.Frame(self.inner, bg="#2b2b2b", padx=PAD // 2, pady=PAD // 2,
                         highlightthickness=2, highlightbackground="#2b2b2b")

        label = tk.Label(frame, image=tk_img, bg="#2b2b2b", cursor="hand2")
        label.image = tk_img
        label.pack()

        name_text = img_path.stem
        if self.fm.has_edits(img_path):
            name_text += " [편집됨]"
        name_label = tk.Label(frame, text=name_text, bg="#2b2b2b", fg="white", font=("", 8))
        name_label.pack()

        label.bind("<Button-1>", lambda e, idx=index: self._on_click(idx, e))
        label.bind("<Double-Button-1>", lambda e, idx=index: self.on_select(idx))
        name_label.bind("<Button-1>", lambda e, idx=index: self._on_click(idx, e))
        name_label.bind("<Double-Button-1>", lambda e, idx=index: self.on_select(idx))

        self._thumb_frames.append(frame)
        self._layout_single(index)

    def _cols(self) -> int:
        w = self.canvas.winfo_width()
        if w < THUMB_W + PAD:
            return 1
        return max(1, w // (THUMB_W + PAD))

    def _layout_thumbs(self):
        cols = self._cols()
        for i, widget in enumerate(self._thumb_frames):
            widget.grid(row=i // cols, column=i % cols)

    def _layout_single(self, index: int):
        cols = self._cols()
        self._thumb_frames[index].grid(row=index // cols, column=index % cols)

    def _on_click(self, index: int, event=None):
        ctrl = event and (event.state & 0x4)
        if ctrl:
            if index in self.selected:
                self.selected.discard(index)
            else:
                self.selected.add(index)
        else:
            self.selected = {index}
        self.focus_idx = index
        self._update_selection_display()

    def _update_selection_display(self):
        for i, frame in enumerate(self._thumb_frames):
            if i == self.focus_idx and i in self.selected:
                frame.config(highlightbackground="#4fc3f7", highlightthickness=3)
            elif i in self.selected:
                frame.config(highlightbackground="#81d4fa", highlightthickness=2)
            elif i == self.focus_idx:
                frame.config(highlightbackground="#666", highlightthickness=2)
            else:
                frame.config(highlightbackground="#2b2b2b", highlightthickness=2)

    def _apply_template_to_selected(self):
        if not self.selected:
            messagebox.showinfo("알림", "이미지를 먼저 선택하세요 (클릭, Ctrl+클릭으로 다중)")
            return
        templates = self.fm.list_templates()
        if not templates:
            messagebox.showinfo("알림", "저장된 템플릿이 없습니다.\n뷰어에서 '템플릿 제작'으로 만드세요.")
            return

        top = tk.Toplevel(self)
        top.title("템플릿 적용")
        top.geometry("350x300")

        tk.Label(top, text=f"선택된 이미지: {len(self.selected)}장").pack(pady=4)

        listbox = tk.Listbox(top, selectmode=tk.MULTIPLE)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        for name in templates:
            layers = self.fm.load_named_template(name)
            total_edits = sum(len(l.get("edits", [])) for l in layers)
            listbox.insert(tk.END, f"{name} ({len(layers)}레이어, {total_edits}편집)")

        def _apply():
            sel = listbox.curselection()
            if not sel:
                return
            # 선택된 템플릿들의 모든 레이어 edits를 flat으로 모음
            all_edits = []
            for i in sel:
                if i < len(templates):
                    layers = self.fm.load_named_template(templates[i])
                    for layer in layers:
                        if layer.get("visible", True):
                            all_edits.extend(layer.get("edits", []))

            if not all_edits:
                return

            count = 0
            for idx in self.selected:
                if idx < len(self.images):
                    img_path = self.images[idx]
                    existing = self.fm.load_edits(img_path)
                    existing.extend(all_edits)
                    self.fm.save_edits(img_path, existing)
                    count += 1

            top.destroy()
            messagebox.showinfo("완료", f"{count}장에 템플릿 적용 완료")
            self.refresh()

        tk.Button(top, text="적용", command=_apply).pack(pady=5)

    def _export(self):
        top = tk.Toplevel(self)
        top.title("내보내기")
        top.geometry("300x80")
        progress = tk.Label(top, text="내보내기 중...")
        progress.pack(pady=10)
        bar = tk.Label(top, text="0%")
        bar.pack()

        def _cb(current, total):
            pct = int(current / total * 100)
            top.after(0, lambda: bar.config(text=f"{pct}% ({current}/{total})"))
            if current == total:
                top.after(0, lambda: progress.config(text="완료!"))
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

        listbox = tk.Listbox(top)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for f in deleted:
            listbox.insert(tk.END, f.name)

        def _restore():
            sel = listbox.curselection()
            if sel:
                filename = listbox.get(sel[0])
                self.fm.restore(filename)
                listbox.delete(sel[0])
                self.refresh()

        tk.Button(top, text="복구", command=_restore).pack(pady=5)
