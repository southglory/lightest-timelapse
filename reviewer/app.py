import tkinter as tk
from pathlib import Path

from .file_manager import FileManager
from .grid_view import GridView
from .viewer import Viewer


class App:
    def __init__(self, session_dir: Path):
        self.root = tk.Tk()
        self.root.title(f"Reviewer — {session_dir.name}")
        self.root.geometry("1200x800")
        self.root.configure(bg="#2b2b2b")

        self.fm = FileManager(session_dir)

        self.grid_view = GridView(self.root, self.fm, on_select=self._open_viewer)
        self.viewer = Viewer(self.root, self.fm, on_back=self._show_grid)

        self._show_grid()

    def _show_grid(self):
        self.viewer.deactivate()
        self.viewer.pack_forget()
        self.grid_view.pack(fill=tk.BOTH, expand=True)
        self.grid_view.refresh()
        self.grid_view.activate()

    def _open_viewer(self, index: int):
        self.grid_view.deactivate()
        self.grid_view.pack_forget()
        self.viewer.pack(fill=tk.BOTH, expand=True)
        self.viewer.show(self.fm.list_images(), index)
        self.viewer.activate()

    def run(self):
        self.root.mainloop()
