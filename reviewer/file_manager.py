"""파일 관리 — 편집 데이터, 템플릿, 소프트 딜리트, 썸네일, 내보내기."""

import json
import shutil
import threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

EDITS_DIR = ".edits"
DELETED_DIR = ".deleted"
THUMBS_DIR = ".thumbs"
TEMPLATES_DIR = ".templates"
AUTOSAVE_FILE = ".autosave.json"
EXPORT_DIR = "exported"


class FileManager:
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.edits_dir = session_dir / EDITS_DIR
        self.deleted_dir = session_dir / DELETED_DIR
        self.thumbs_dir = session_dir / THUMBS_DIR
        self.templates_dir = session_dir / TEMPLATES_DIR
        for d in [self.edits_dir, self.deleted_dir, self.thumbs_dir, self.templates_dir]:
            d.mkdir(exist_ok=True)

    # ==================== 이미지 목록 ====================

    def list_images(self) -> list[Path]:
        return sorted(self.session_dir.glob("*.jpg"))

    def list_deleted(self) -> list[Path]:
        return sorted(self.deleted_dir.glob("*.jpg"))

    # ==================== 편집 데이터 (참조 모델) ====================

    def _edit_path(self, image_path: Path) -> Path:
        return self.edits_dir / f"{image_path.stem}.json"

    def load_image_data(self, image_path: Path) -> dict:
        """이미지의 편집 데이터 로드. {"edits": [...], "applied_templates": [...]}"""
        path = self._edit_path(image_path)
        if not path.exists():
            return {"edits": [], "applied_templates": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return {"edits": [], "applied_templates": []}
            data = json.loads(content)
        except (json.JSONDecodeError, OSError):
            return {"edits": [], "applied_templates": []}
        return {
            "edits": data.get("edits", []),
            "applied_templates": data.get("applied_templates", []),
        }

    def save_image_data(self, image_path: Path, edits: list[dict], applied_templates: list[str]):
        """이미지의 편집 데이터 저장."""
        path = self._edit_path(image_path)
        if not edits and not applied_templates:
            path.unlink(missing_ok=True)
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"edits": edits, "applied_templates": applied_templates},
                      f, ensure_ascii=False, indent=2)

    def apply_template_to_image(self, image_path: Path, template_name: str):
        """이미지에 템플릿 참조 추가."""
        data = self.load_image_data(image_path)
        if template_name not in data["applied_templates"]:
            data["applied_templates"].append(template_name)
            self.save_image_data(image_path, data["edits"], data["applied_templates"])

    def unapply_template_from_image(self, image_path: Path, template_name: str):
        """이미지에서 템플릿 참조 제거."""
        data = self.load_image_data(image_path)
        if template_name in data["applied_templates"]:
            data["applied_templates"].remove(template_name)
            self.save_image_data(image_path, data["edits"], data["applied_templates"])

    def batch_apply_templates(self, images: list[Path], template_names: list[str]):
        """여러 이미지에 템플릿 일괄 적용. 파일 I/O 최소화."""
        for img_path in images:
            data = self.load_image_data(img_path)
            changed = False
            for name in template_names:
                if name not in data["applied_templates"]:
                    data["applied_templates"].append(name)
                    changed = True
            if changed:
                self.save_image_data(img_path, data["edits"], data["applied_templates"])

    def batch_unapply_templates(self, images: list[Path], template_names: list[str]):
        """여러 이미지에서 템플릿 일괄 해제. 파일 I/O 최소화."""
        for img_path in images:
            data = self.load_image_data(img_path)
            changed = False
            for name in template_names:
                if name in data["applied_templates"]:
                    data["applied_templates"].remove(name)
                    changed = True
            if changed:
                self.save_image_data(img_path, data["edits"], data["applied_templates"])

    def resolve_all_edits(self, image_path: Path) -> list[dict]:
        """템플릿 참조를 해석하여 전체 edits 반환. 렌더링 순서: 템플릿 → 직접."""
        data = self.load_image_data(image_path)
        result = []
        # 1. 적용된 템플릿 edits
        for tpl_name in data["applied_templates"]:
            layers = self.load_named_template(tpl_name)
            for layer in layers:
                if layer.get("visible", True):
                    result.extend(layer.get("edits", []))
        # 2. 직접 edits
        result.extend(data["edits"])
        return result

    def get_image_status(self, image_path: Path) -> dict:
        """이미지 상태 정보. 썸네일 표시용."""
        data = self.load_image_data(image_path)
        return {
            "has_edits": len(data["edits"]) > 0,
            "template_count": len(data["applied_templates"]),
        }

    def has_edits(self, image_path: Path) -> bool:
        return self._edit_path(image_path).exists()

    # ==================== 소프트 딜리트 ====================

    def soft_delete(self, image_path: Path):
        dest = self.deleted_dir / image_path.name
        shutil.move(str(image_path), str(dest))
        # 편집 데이터도 함께 이동
        edit_path = self._edit_path(image_path)
        if edit_path.exists():
            edit_dest = self.deleted_dir / edit_path.name
            shutil.move(str(edit_path), str(edit_dest))

    def restore(self, filename: str):
        src = self.deleted_dir / filename
        dest = self.session_dir / filename
        if src.exists():
            shutil.move(str(src), str(dest))
        # 편집 데이터도 복구
        edit_name = Path(filename).stem + ".json"
        edit_src = self.deleted_dir / edit_name
        if edit_src.exists():
            shutil.move(str(edit_src), str(self.edits_dir / edit_name))

    # ==================== 썸네일 ====================

    def get_thumbnail(self, image_path: Path, size=(200, 112)) -> Path:
        thumb_path = self.thumbs_dir / image_path.name
        if not thumb_path.exists():
            img = Image.open(image_path)
            img.thumbnail(size, Image.LANCZOS)
            img.save(str(thumb_path), "JPEG", quality=70)
        return thumb_path

    # ==================== 템플릿 ====================

    def save_named_template(self, name: str, layers: list[dict]):
        path = self.templates_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "layers": layers}, f, ensure_ascii=False, indent=2)

    def load_named_template(self, name: str) -> list[dict]:
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

    def rename_template(self, old_name: str, new_name: str):
        layers = self.load_named_template(old_name)
        if layers:
            self.delete_template(old_name)
            self.save_named_template(new_name, layers)

    # ==================== 오토세이브 ====================

    def autosave(self, image_path: Path, edits: list[dict], applied_templates: list[str]):
        path = self.session_dir / AUTOSAVE_FILE
        data = {"image": image_path.name, "edits": edits, "applied_templates": applied_templates}
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
        (self.session_dir / AUTOSAVE_FILE).unlink(missing_ok=True)

    # ==================== 편집 적용 (렌더링) ====================

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
                    Image.NEAREST)
                img.paste(small.resize(region.size, Image.NEAREST), box)
            elif t == "blur":
                box = tuple(edit["box"])
                region = img.crop(box)
                img.paste(region.filter(ImageFilter.GaussianBlur(radius=edit.get("radius", 20))), box)
            elif t == "fill":
                ImageDraw.Draw(img).rectangle(tuple(edit["box"]), fill=tuple(edit.get("color", [0, 0, 0])))
            elif t == "pen":
                draw = ImageDraw.Draw(img)
                pts = edit["points"]
                color = tuple(edit.get("color", [255, 0, 0]))
                width = edit.get("width", 3)
                for i in range(len(pts) - 1):
                    draw.line([tuple(pts[i]), tuple(pts[i + 1])], fill=color, width=width)
        return img

    # ==================== 내보내기 ====================

    def export_all(self, progress_callback=None):
        export_dir = self.session_dir / EXPORT_DIR
        export_dir.mkdir(exist_ok=True)
        images = self.list_images()
        total = len(images)
        for i, img_path in enumerate(images):
            all_edits = self.resolve_all_edits(img_path)
            img = Image.open(img_path)
            if all_edits:
                img = self.apply_edits(img, all_edits)
            img.save(str(export_dir / img_path.name), "JPEG", quality=90)
            if progress_callback:
                progress_callback(i + 1, total)
