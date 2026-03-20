import json
import shutil
import threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


EDITS_DIR = ".edits"
DELETED_DIR = ".deleted"
THUMBS_DIR = ".thumbs"
AUTOSAVE_FILE = ".autosave.json"
TEMPLATE_FILE = ".mask-template.json"
TEMPLATES_DIR = ".templates"
EXPORT_DIR = "exported"


class FileManager:
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.edits_dir = session_dir / EDITS_DIR
        self.deleted_dir = session_dir / DELETED_DIR
        self.thumbs_dir = session_dir / THUMBS_DIR
        self.templates_dir = session_dir / TEMPLATES_DIR
        self.edits_dir.mkdir(exist_ok=True)
        self.deleted_dir.mkdir(exist_ok=True)
        self.thumbs_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)

    def list_images(self) -> list[Path]:
        return sorted(self.session_dir.glob("*.jpg"))

    def list_deleted(self) -> list[Path]:
        return sorted(self.deleted_dir.glob("*.jpg"))

    # --- 편집 데이터 (flat edits) ---

    def load_edits(self, image_path: Path) -> list[dict]:
        edit_file = self.edits_dir / f"{image_path.stem}.json"
        if not edit_file.exists():
            return []
        with open(edit_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("edits", [])

    def save_edits(self, image_path: Path, edits: list[dict]):
        edit_file = self.edits_dir / f"{image_path.stem}.json"
        if not edits:
            edit_file.unlink(missing_ok=True)
            return
        with open(edit_file, "w", encoding="utf-8") as f:
            json.dump({"edits": edits}, f, ensure_ascii=False, indent=2)

    def has_edits(self, image_path: Path) -> bool:
        edit_file = self.edits_dir / f"{image_path.stem}.json"
        return edit_file.exists()

    # --- 소프트 딜리트 ---

    def soft_delete(self, image_path: Path):
        dest = self.deleted_dir / image_path.name
        shutil.move(str(image_path), str(dest))

    def restore(self, filename: str):
        src = self.deleted_dir / filename
        dest = self.session_dir / filename
        if src.exists():
            shutil.move(str(src), str(dest))

    # --- 썸네일 ---

    def get_thumbnail(self, image_path: Path, size=(200, 112)) -> Path:
        thumb_path = self.thumbs_dir / image_path.name
        if not thumb_path.exists():
            img = Image.open(image_path)
            img.thumbnail(size, Image.LANCZOS)
            img.save(str(thumb_path), "JPEG", quality=70)
        return thumb_path

    # --- 마스크 템플릿 ---

    def save_template(self, regions: list[dict]):
        path = self.session_dir / TEMPLATE_FILE
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"regions": regions}, f, ensure_ascii=False, indent=2)

    def load_template(self) -> list[dict]:
        path = self.session_dir / TEMPLATE_FILE
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("regions", [])

    # --- Named 템플릿 ---

    def save_named_template(self, name: str, layers: list[dict]):
        """템플릿 저장. layers = [{"name":..., "edits":[...], "visible":...}, ...]"""
        path = self.templates_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "layers": layers}, f, ensure_ascii=False, indent=2)

    def load_named_template(self, name: str) -> list[dict]:
        """템플릿 로드. 레이어 리스트 반환."""
        path = self.templates_dir / f"{name}.json"
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("layers", [])

    def list_templates(self) -> list[str]:
        return sorted([f.stem for f in self.templates_dir.glob("*.json")])

    def delete_template(self, name: str):
        path = self.templates_dir / f"{name}.json"
        path.unlink(missing_ok=True)

    # --- 오토세이브 ---

    def autosave(self, image_path: Path, edits: list[dict]):
        path = self.session_dir / AUTOSAVE_FILE
        data = {
            "image": image_path.name,
            "edits": edits,
        }
        def _write():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        threading.Thread(target=_write, daemon=True).start()

    def load_autosave(self) -> dict | None:
        path = self.session_dir / AUTOSAVE_FILE
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def clear_autosave(self):
        path = self.session_dir / AUTOSAVE_FILE
        path.unlink(missing_ok=True)

    # --- 편집 적용 ---

    @staticmethod
    def apply_edits(img: Image.Image, edits: list[dict]) -> Image.Image:
        img = img.copy()
        for edit in edits:
            t = edit["type"]
            if t == "mosaic":
                box = tuple(edit["box"])
                block = edit.get("block_size", 16)
                region = img.crop(box)
                small = region.resize(
                    (max(1, region.width // block), max(1, region.height // block)),
                    Image.NEAREST,
                )
                mosaic = small.resize(region.size, Image.NEAREST)
                img.paste(mosaic, box)
            elif t == "blur":
                box = tuple(edit["box"])
                radius = edit.get("radius", 20)
                region = img.crop(box)
                blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))
                img.paste(blurred, box)
            elif t == "fill":
                box = tuple(edit["box"])
                color = tuple(edit.get("color", [0, 0, 0]))
                draw = ImageDraw.Draw(img)
                draw.rectangle(box, fill=color)
            elif t == "pen":
                points = edit["points"]
                color = tuple(edit.get("color", [255, 0, 0]))
                width = edit.get("width", 3)
                draw = ImageDraw.Draw(img)
                for i in range(len(points) - 1):
                    draw.line(
                        [tuple(points[i]), tuple(points[i + 1])],
                        fill=color,
                        width=width,
                    )
        return img

    # --- 내보내기 ---

    def export_all(self, progress_callback=None):
        export_dir = self.session_dir / EXPORT_DIR
        export_dir.mkdir(exist_ok=True)
        images = self.list_images()
        total = len(images)
        for i, img_path in enumerate(images):
            edits = self.load_edits(img_path)
            img = Image.open(img_path)
            if edits:
                img = self.apply_edits(img, edits)
            img.save(str(export_dir / img_path.name), "JPEG", quality=90)
            if progress_callback:
                progress_callback(i + 1, total)
