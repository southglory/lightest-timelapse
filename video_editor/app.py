"""메인 앱 — 영상 열기, 영역 편집, 마스크 적용."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .canvas_view import CanvasView
from .ffmpeg_utils import extract_first_frame, extract_frame_at, get_video_info, apply_masks, apply_crop, compress_video
from .region_manager import RegionManager

# 디자인 토큰
BG_MAIN = "#1e1e1e"
BG_SIDEBAR = "#252526"
BG_PANEL = "#2d2d2d"
BG_INPUT = "#3c3c3c"
FG = "#cccccc"
FG_DIM = "#888888"
ACCENT = "#007acc"
ACCENT_DANGER = "#c94040"
ACCENT_SUCCESS = "#4ec9b0"
BORDER = "#404040"
FONT = ("Segoe UI", 9)
FONT_SM = ("Segoe UI", 8)
FONT_BD = ("Segoe UI", 9, "bold")

KIND_LABELS = {"blur": "블러", "mosaic": "모자이크", "fill": "채우기", "crop": "크롭"}


class App:
    def __init__(self, video_path: str | None = None):
        self.root = tk.Tk()
        self.root.title("Video Editor")
        self.root.geometry("1280x800")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(900, 600)

        self.video_path: str | None = None
        self.video_info: dict = {}
        self.region_mgr = RegionManager()
        self._encoding = False

        self._build_toolbar()
        self._build_statusbar()
        self._build_timeline()
        self._build_main()
        self._bind_keys()

        if video_path:
            self.root.after(100, lambda: self._open_video(video_path))

    # ==================== UI 빌드 ====================

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=BG_PANEL)
        bar.pack(fill=tk.X)

        tk.Button(bar, text="열기", font=FONT, bg=BG_INPUT, fg=FG, bd=0, padx=8,
                  command=self._open_dialog).pack(side=tk.LEFT, padx=4, pady=4)

        tk.Frame(bar, width=16, bg=BG_PANEL).pack(side=tk.LEFT)
        tk.Label(bar, text="도구:", bg=BG_PANEL, fg=FG_DIM, font=FONT_SM).pack(side=tk.LEFT)

        self.tool_btns = {}
        for label, key in [("블러 1", "blur"), ("모자이크 2", "mosaic"), ("채우기 3", "fill"), ("크롭 4", "crop")]:
            b = tk.Button(bar, text=label, font=FONT_SM, bg=BG_INPUT, fg=FG, bd=1, padx=6,
                          command=lambda t=key: self._set_tool(t))
            b.pack(side=tk.LEFT, padx=2, pady=4)
            self.tool_btns[key] = b

        self.btn_apply = tk.Button(bar, text="적용 및 저장", font=FONT_BD, bg=ACCENT, fg="white",
                                   bd=0, padx=12, command=self._apply)
        self.btn_apply.pack(side=tk.RIGHT, padx=8, pady=4)

        tk.Button(bar, text="프레임 캡처 S", font=FONT_SM, bg=BG_INPUT, fg=ACCENT_SUCCESS, bd=0, padx=8,
                  command=self._capture_frame).pack(side=tk.RIGHT, padx=4, pady=4)

    def _build_main(self):
        main = tk.Frame(self.root, bg=BG_MAIN)
        main.pack(fill=tk.BOTH, expand=True)

        # 캔버스
        self.canvas_view = CanvasView(main, self.region_mgr, on_change=self._refresh_sidebar)
        self.canvas_view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 사이드바
        sidebar = tk.Frame(main, bg=BG_SIDEBAR, width=220)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="영역 목록", bg=BG_SIDEBAR, fg=FG, font=FONT_BD).pack(
            fill=tk.X, padx=8, pady=(8, 4))

        # 영역 리스트 (스크롤 가능)
        list_frame = tk.Frame(sidebar, bg=BG_SIDEBAR)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4)

        self.list_canvas = tk.Canvas(list_frame, bg=BG_SIDEBAR, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.list_canvas.yview)
        self.list_inner = tk.Frame(self.list_canvas, bg=BG_SIDEBAR)

        self.list_inner.bind("<Configure>",
                             lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.list_inner, anchor=tk.NW)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)

        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 하단 버튼
        bottom = tk.Frame(sidebar, bg=BG_SIDEBAR)
        bottom.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(bottom, text="전체 삭제", font=FONT_SM, bg=BG_INPUT, fg=ACCENT_DANGER, bd=0,
                  command=self._clear_all).pack(fill=tk.X)

    def _build_timeline(self):
        """프레임 슬라이더 바."""
        bar = tk.Frame(self.root, bg=BG_PANEL)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_time = tk.Label(bar, text="0:00 / 0:00", bg=BG_PANEL, fg=FG_DIM,
                                 font=FONT_SM, width=16)
        self.lbl_time.pack(side=tk.RIGHT, padx=8)

        self.timeline = tk.Scale(bar, from_=0, to=100, orient=tk.HORIZONTAL,
                                 bg=BG_PANEL, fg=FG, troughcolor=BG_INPUT,
                                 highlightthickness=0, showvalue=False, bd=0,
                                 command=self._on_timeline_change)
        self.timeline.pack(fill=tk.X, padx=8, pady=2)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=BG_PANEL, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self.lbl_status = tk.Label(bar, text="파일을 열어주세요", bg=BG_PANEL, fg=FG_DIM,
                                   font=FONT_SM, anchor=tk.W)
        self.lbl_status.pack(side=tk.LEFT, padx=8)

        self.progress = ttk.Progressbar(bar, length=200, mode="determinate")
        self.progress.pack(side=tk.RIGHT, padx=8, pady=4)

    def _bind_keys(self):
        self.root.bind("<Key-1>", lambda e: self._set_tool("blur"))
        self.root.bind("<Key-2>", lambda e: self._set_tool("mosaic"))
        self.root.bind("<Key-3>", lambda e: self._set_tool("fill"))
        self.root.bind("<Key-4>", lambda e: self._set_tool("crop"))
        self.root.bind("<Escape>", lambda e: self._set_tool(None))
        self.root.bind("<Delete>", lambda e: self._delete_selected())
        self.root.bind("<space>", lambda e: self._toggle_fit())
        self.root.bind("<s>", lambda e: self._capture_frame())
        self.root.bind("<S>", lambda e: self._capture_frame())

    # ==================== 파일 열기 ====================

    def _open_dialog(self):
        if self._encoding:
            return
        path = filedialog.askopenfilename(
            title="영상 파일 선택",
            filetypes=[("MP4 파일", "*.mp4"), ("모든 파일", "*.*")])
        if path:
            self._open_video(path)

    def _open_video(self, path: str):
        try:
            frame = extract_first_frame(path)
        except Exception as e:
            messagebox.showerror("오류", f"영상을 열 수 없습니다.\n{e}")
            return

        self.video_path = path
        self.video_info = get_video_info(path)
        self.region_mgr.clear_all()
        self.canvas_view.load_frame(frame)

        # 상태바 + 타임라인 업데이트
        w, h = self.video_info["width"], self.video_info["height"]
        dur = self.video_info["duration"]
        m, s = int(dur) // 60, int(dur) % 60
        name = Path(path).name
        self.lbl_status.config(text=f"{name} | {w}x{h} | {m}:{s:02d}")
        self.root.title(f"Video Editor — {name}")

        self.timeline.config(to=max(1, dur), resolution=0.1)
        self.timeline.set(0)
        self.lbl_time.config(text=f"0:00 / {m}:{s:02d}")

        self._refresh_sidebar()

    # ==================== 도구 ====================

    def _set_tool(self, tool: str | None):
        if tool and self.canvas_view.current_tool == tool:
            tool = None
        self.canvas_view.current_tool = tool
        if tool:
            self.region_mgr.selected_idx = None
            self._refresh_sidebar()
        for t, b in self.tool_btns.items():
            b.config(relief=tk.SUNKEN if t == tool else tk.RAISED)

    def _toggle_fit(self):
        self.canvas_view.fit_mode = True
        self.canvas_view.render()

    def _capture_frame(self):
        """현재 프레임을 편집 적용 상태로 JPG 저장."""
        if not self.video_path:
            messagebox.showwarning("알림", "먼저 영상을 열어주세요.")
            return

        frame = self.canvas_view.get_edited_frame()
        if frame is None:
            return

        src = Path(self.video_path)
        time_val = self.timeline.get()
        default_name = f"{src.stem}_{time_val:.1f}s.jpg"

        output = filedialog.asksaveasfilename(
            title="프레임 저장",
            initialdir=str(src.parent),
            initialfile=default_name,
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("모든 파일", "*.*")])
        if not output:
            return

        if output.lower().endswith(".png"):
            frame.save(output)
        else:
            frame.save(output, quality=95)
        self.lbl_status.config(text=f"캡처 저장: {Path(output).name}")

    # ==================== 타임라인 ====================

    def _on_timeline_change(self, value):
        if not self.video_path or self._encoding:
            return
        seconds = float(value)
        dur = self.video_info.get("duration", 0)
        m, s = int(seconds) // 60, seconds % 60
        tm, ts = int(dur) // 60, dur % 60
        self.lbl_time.config(text=f"{m}:{s:04.1f} / {tm}:{ts:04.1f}")

        # 디바운스로 프레임 추출
        if hasattr(self, "_timeline_after_id") and self._timeline_after_id:
            self.root.after_cancel(self._timeline_after_id)
        self._timeline_after_id = self.root.after(300, lambda: self._seek_frame(seconds))

    def _seek_frame(self, seconds: float):
        import threading
        def worker():
            try:
                frame = extract_frame_at(self.video_path, seconds)
                self.root.after(0, lambda: self._update_frame(frame))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _update_frame(self, frame):
        self.canvas_view.load_frame(frame)

    # ==================== 사이드바 ====================

    def _refresh_sidebar(self):
        """영역 리스트 UI 갱신."""
        for widget in self.list_inner.winfo_children():
            widget.destroy()

        for i, r in enumerate(self.region_mgr.regions):
            is_selected = i == self.region_mgr.selected_idx
            bg = BG_INPUT if is_selected else BG_SIDEBAR

            row = tk.Frame(self.list_inner, bg=bg)
            row.pack(fill=tk.X, pady=1)

            # 클릭으로 선택
            label_text = f"{i+1}. {r.label}"
            lbl = tk.Label(row, text=label_text, bg=bg, fg=FG, font=FONT_SM, anchor=tk.W)
            lbl.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
            lbl.bind("<Button-1>", lambda e, idx=i: self._select_region(idx))

            # 유형 변경
            kind_var = tk.StringVar(value=r.kind)
            menu = tk.OptionMenu(row, kind_var, "blur", "mosaic", "fill", "crop",
                                 command=lambda val, idx=i: self._change_kind(idx, val))
            menu.config(bg=bg, fg=FG, font=FONT_SM, highlightthickness=0, bd=0, width=6)
            menu.pack(side=tk.LEFT)

            # 삭제 버튼
            tk.Button(row, text="x", font=FONT_SM, bg=bg, fg=ACCENT_DANGER, bd=0, width=2,
                      command=lambda idx=i: self._delete_region(idx)).pack(side=tk.RIGHT, padx=2)

    def _select_region(self, idx: int):
        self.canvas_view.current_tool = None
        for t, b in self.tool_btns.items():
            b.config(relief=tk.RAISED)
        self.region_mgr.selected_idx = idx
        self.canvas_view.render()
        self._refresh_sidebar()

    def _change_kind(self, idx: int, kind: str):
        self.region_mgr.update_kind(idx, kind)
        self.canvas_view.render()
        self._refresh_sidebar()

    def _delete_region(self, idx: int):
        self.region_mgr.remove(idx)
        self.canvas_view.render()
        self._refresh_sidebar()

    def _delete_selected(self):
        if self.region_mgr.selected_idx is not None:
            self._delete_region(self.region_mgr.selected_idx)

    def _clear_all(self):
        if not self.region_mgr.regions:
            return
        if messagebox.askyesno("확인", "모든 영역을 삭제하시겠습니까?"):
            self.region_mgr.clear_all()
            self.canvas_view.render()
            self._refresh_sidebar()

    # ==================== 적용 ====================

    def _apply(self):
        if self._encoding:
            return
        if not self.video_path:
            messagebox.showwarning("알림", "먼저 영상을 열어주세요.")
            return

        has_regions = bool(self.region_mgr.regions)

        # 압축 여부 확인 (예/아니오/취소)
        answer = messagebox.askyesnocancel("압축", "압축 저장하시겠습니까?\n\n예: 편집 적용 + 압축\n아니오: 편집만 적용\n취소: 저장 안 함")
        if answer is None:
            return
        do_compress = answer

        if not has_regions and not do_compress:
            messagebox.showwarning("알림", "적용할 영역이 없습니다.")
            return

        # 압축 설정
        compress_opts = None
        if do_compress:
            compress_opts = self._show_compress_dialog()
            if compress_opts is None:
                return  # 취소

        # 출력 경로
        src = Path(self.video_path)
        suffix = "_compressed" if do_compress and not has_regions else "_edited"
        default_name = f"{src.stem}{suffix}{src.suffix}"
        output = filedialog.asksaveasfilename(
            title="저장 위치 선택",
            initialdir=str(src.parent),
            initialfile=default_name,
            defaultextension=".mp4",
            filetypes=[("MP4 파일", "*.mp4")])
        if not output:
            return

        all_regions = self.region_mgr.to_filter_params() if has_regions else []
        mask_regions = [r for r in all_regions if r["kind"] != "crop"]
        crop_regions = [r for r in all_regions if r["kind"] == "crop"]

        if len(crop_regions) > 1:
            messagebox.showwarning("알림", "크롭 영역은 하나만 지정할 수 있습니다.")
            return

        crop = crop_regions[0] if crop_regions else None

        self._encoding = True
        self.btn_apply.config(state=tk.DISABLED, text="인코딩 중...")
        self.progress["value"] = 0

        def worker():
            import tempfile
            progress_cb = lambda pct: self.root.after(0, self._update_progress, pct)
            current_input = self.video_path

            try:
                tmp_files = []

                # 1단계: 마스크 적용
                if mask_regions:
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                    tmp.close()
                    tmp_files.append(tmp.name)
                    ok, msg = apply_masks(current_input, tmp.name, mask_regions, progress_callback=progress_cb)
                    if not ok:
                        self.root.after(0, self._encode_done, False, msg)
                        return
                    current_input = tmp.name

                # 2단계: 크롭 적용
                if crop:
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                    tmp.close()
                    tmp_files.append(tmp.name)
                    ok, msg = apply_crop(current_input, tmp.name, crop, progress_callback=progress_cb)
                    if not ok:
                        self.root.after(0, self._encode_done, False, msg)
                        return
                    current_input = tmp.name

                # 3단계: 압축 (선택)
                if compress_opts:
                    ok, msg = compress_video(
                        current_input, output,
                        width=compress_opts["width"],
                        bitrate=compress_opts["bitrate"],
                        mute=compress_opts["mute"],
                        progress_callback=progress_cb)
                    self.root.after(0, self._encode_done, ok, msg)
                elif current_input != self.video_path:
                    # 마스크/크롭만 적용 — 마지막 임시 파일을 최종 출력으로 이동
                    import shutil
                    shutil.move(current_input, output)
                    tmp_files = [t for t in tmp_files if t != current_input]
                    self.root.after(0, self._encode_done, True, f"완료: {output}")
                else:
                    self.root.after(0, self._encode_done, True, f"완료: {output}")

            finally:
                for t in tmp_files:
                    Path(t).unlink(missing_ok=True)

        threading.Thread(target=worker, daemon=True).start()

    def _show_compress_dialog(self) -> dict | None:
        """압축 설정 다이얼로그. 반환: {"width", "bitrate", "mute"} 또는 None(취소)."""
        result = {}

        dlg = tk.Toplevel(self.root)
        dlg.title("압축 설정")
        dlg.geometry("300x200")
        dlg.configure(bg=BG_MAIN)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="가로 해상도:", bg=BG_MAIN, fg=FG, font=FONT).pack(anchor=tk.W, padx=16, pady=(16, 2))
        width_var = tk.StringVar(value="480")
        tk.Entry(dlg, textvariable=width_var, bg=BG_INPUT, fg=FG, font=FONT,
                 insertbackground=FG, width=10).pack(anchor=tk.W, padx=16)

        tk.Label(dlg, text="비트레이트:", bg=BG_MAIN, fg=FG, font=FONT).pack(anchor=tk.W, padx=16, pady=(8, 2))
        bitrate_var = tk.StringVar(value="500k")
        tk.Entry(dlg, textvariable=bitrate_var, bg=BG_INPUT, fg=FG, font=FONT,
                 insertbackground=FG, width=10).pack(anchor=tk.W, padx=16)

        mute_var = tk.BooleanVar(value=True)
        tk.Checkbutton(dlg, text="음소거", variable=mute_var, bg=BG_MAIN, fg=FG,
                       selectcolor=BG_INPUT, font=FONT, activebackground=BG_MAIN,
                       activeforeground=FG).pack(anchor=tk.W, padx=16, pady=(8, 4))

        def on_ok():
            try:
                result["width"] = int(width_var.get())
            except ValueError:
                messagebox.showwarning("알림", "해상도는 숫자로 입력하세요.", parent=dlg)
                return
            result["bitrate"] = bitrate_var.get().strip()
            result["mute"] = mute_var.get()
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=BG_MAIN)
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="확인", font=FONT_BD, bg=ACCENT, fg="white", bd=0, padx=16,
                  command=on_ok).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="취소", font=FONT, bg=BG_INPUT, fg=FG, bd=0, padx=16,
                  command=on_cancel).pack(side=tk.LEFT, padx=4)

        self.root.wait_window(dlg)
        return result if result else None

    def _update_progress(self, pct: float):
        self.progress["value"] = pct

    def _encode_done(self, success: bool, msg: str):
        self._encoding = False
        self.btn_apply.config(state=tk.NORMAL, text="적용 및 저장")
        self.progress["value"] = 100 if success else 0

        if success:
            messagebox.showinfo("완료", msg)
        else:
            messagebox.showerror("오류", msg)

    # ==================== 실행 ====================

    def run(self):
        self.root.mainloop()
