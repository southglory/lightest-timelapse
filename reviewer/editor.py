"""편집 엔진 — 일반 편집 + 템플릿 제작 모드."""

import copy


class Layer:
    """템플릿 내부의 편집 레이어."""

    def __init__(self, name: str, edits: list[dict] | None = None, visible: bool = True):
        self.name = name
        self.edits: list[dict] = edits or []
        self.visible = visible

    def to_dict(self) -> dict:
        return {"name": self.name, "edits": copy.deepcopy(self.edits), "visible": self.visible}

    @classmethod
    def from_dict(cls, data: dict) -> "Layer":
        return cls(name=data["name"], edits=data.get("edits", []), visible=data.get("visible", True))


class Editor:
    def __init__(self):
        # 일반 편집
        self.edits: list[dict] = []
        self.applied_templates: list[str] = []

        # 템플릿 제작 모드
        self.template_mode = False
        self.template_layers: list[Layer] = []
        self.active_layer_idx: int = -1
        self._editing_template_name: str | None = None  # 편집 중 원본 이름

        # 도구
        self.current_tool: str | None = None
        self.pen_color = (255, 0, 0)
        self.pen_width = 3
        self.fill_color = (0, 0, 0)
        self.mosaic_block = 16
        self.blur_radius = 20
        self._pen_points: list[tuple[int, int]] = []

        # Undo/Redo
        self._history: list = []
        self._redo_stack: list = []

    @property
    def active_layer(self) -> Layer | None:
        if self.template_mode and 0 <= self.active_layer_idx < len(self.template_layers):
            return self.template_layers[self.active_layer_idx]
        return None

    def set_tool(self, tool: str | None):
        self.finish_pen()
        self.current_tool = tool

    # ==================== Undo/Redo ====================

    def _snapshot(self):
        if self.template_mode:
            return {"m": "t", "layers": [l.to_dict() for l in self.template_layers], "ali": self.active_layer_idx}
        return {"m": "n", "edits": copy.deepcopy(self.edits), "at": list(self.applied_templates)}

    def _restore(self, snap):
        if snap["m"] == "t":
            self.template_layers = [Layer.from_dict(d) for d in snap["layers"]]
            self.active_layer_idx = snap.get("ali", -1)
            if self.active_layer_idx >= len(self.template_layers):
                self.active_layer_idx = max(-1, len(self.template_layers) - 1)
        else:
            self.edits = snap["edits"]
            self.applied_templates = snap.get("at", [])

    def _push_history(self):
        self._history.append(self._snapshot())
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._history:
            return False
        self._redo_stack.append(self._snapshot())
        self._restore(self._history.pop())
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._history.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        return True

    # ==================== 일반 모드 ====================

    def load_image_data(self, edits: list[dict], applied_templates: list[str]):
        self.edits = copy.deepcopy(edits)
        self.applied_templates = list(applied_templates)
        self._history.clear()
        self._redo_stack.clear()

    def clear_edits(self):
        self._push_history()
        self.edits.clear()

    def clear_all(self):
        self.edits = []
        self.applied_templates = []
        self._history.clear()
        self._redo_stack.clear()

    # ==================== 템플릿 제작 모드 ====================

    def start_template_create(self):
        self.template_mode = True
        self.template_layers = [Layer("레이어 1")]
        self.active_layer_idx = 0
        self._editing_template_name = None
        self._history.clear()
        self._redo_stack.clear()

    def start_template_edit(self, name: str, layers: list[dict]):
        self.template_mode = True
        self.template_layers = [Layer.from_dict(l) for l in layers]
        self.active_layer_idx = 0 if self.template_layers else -1
        self._editing_template_name = name
        self._history.clear()
        self._redo_stack.clear()

    def finish_template(self) -> tuple[str | None, list[dict] | None]:
        """템플릿 완료. (편집 중 이름, 레이어 데이터) 반환."""
        if not self.template_mode:
            return None, None
        layers = [l.to_dict() for l in self.template_layers if l.edits]
        name = self._editing_template_name
        self._exit_template()
        if not layers:
            return name, None
        return name, layers

    def cancel_template(self):
        self._exit_template()

    def _exit_template(self):
        self.template_mode = False
        self.template_layers = []
        self.active_layer_idx = -1
        self._editing_template_name = None
        self._history.clear()
        self._redo_stack.clear()

    # ==================== 레이어 관리 ====================

    def add_layer(self, name: str):
        if not self.template_mode:
            return
        self._push_history()
        self.template_layers.append(Layer(name))
        self.active_layer_idx = len(self.template_layers) - 1

    def remove_layer(self, idx: int):
        if not self.template_mode or not (0 <= idx < len(self.template_layers)):
            return
        self._push_history()
        self.template_layers.pop(idx)
        if self.active_layer_idx >= len(self.template_layers):
            self.active_layer_idx = max(-1, len(self.template_layers) - 1)

    def toggle_layer(self, idx: int):
        if not self.template_mode or not (0 <= idx < len(self.template_layers)):
            return
        self._push_history()
        self.template_layers[idx].visible = not self.template_layers[idx].visible

    def move_layer(self, idx: int, direction: int):
        new_idx = idx + direction
        if not self.template_mode or not (0 <= idx < len(self.template_layers) and 0 <= new_idx < len(self.template_layers)):
            return
        self._push_history()
        self.template_layers[idx], self.template_layers[new_idx] = self.template_layers[new_idx], self.template_layers[idx]
        if self.active_layer_idx == idx:
            self.active_layer_idx = new_idx

    def set_active_layer(self, idx: int):
        if 0 <= idx < len(self.template_layers):
            self.active_layer_idx = idx

    # ==================== 편집 추가 ====================

    def _target_list(self) -> list[dict]:
        if self.template_mode:
            if self.active_layer is None:
                self.add_layer("레이어 1")
            return self.active_layer.edits
        return self.edits

    def add_mosaic(self, box: tuple[int, int, int, int]):
        self._push_history()
        self._target_list().append({"type": "mosaic", "box": list(box), "block_size": self.mosaic_block})

    def add_blur(self, box: tuple[int, int, int, int]):
        self._push_history()
        self._target_list().append({"type": "blur", "box": list(box), "radius": self.blur_radius})

    def add_fill(self, box: tuple[int, int, int, int]):
        self._push_history()
        self._target_list().append({"type": "fill", "box": list(box), "color": list(self.fill_color)})

    def pen_start(self, x: int, y: int):
        self._pen_points = [(x, y)]

    def pen_move(self, x: int, y: int):
        self._pen_points.append((x, y))

    def finish_pen(self):
        if len(self._pen_points) >= 2:
            self._push_history()
            self._target_list().append({
                "type": "pen", "points": [list(p) for p in self._pen_points],
                "color": list(self.pen_color), "width": self.pen_width,
            })
        self._pen_points.clear()

    # ==================== 편집 조작 (선택/이동/리사이즈/삭제) ====================

    def move_edit(self, idx: int, dx: int, dy: int):
        """편집 요소를 delta만큼 이동."""
        target = self._target_list()
        if not (0 <= idx < len(target)):
            return
        self._push_history()
        edit = target[idx]
        if edit["type"] in ("mosaic", "blur", "fill"):
            b = edit["box"]
            edit["box"] = [b[0]+dx, b[1]+dy, b[2]+dx, b[3]+dy]
        elif edit["type"] == "pen":
            edit["points"] = [[p[0]+dx, p[1]+dy] for p in edit["points"]]

    def resize_edit(self, idx: int, box: tuple[int, int, int, int]):
        """편집 요소의 box를 직접 설정 (box 편집만)."""
        target = self._target_list()
        if not (0 <= idx < len(target)):
            return
        edit = target[idx]
        if edit["type"] not in ("mosaic", "blur", "fill"):
            return
        self._push_history()
        edit["box"] = list(box)

    def delete_edit(self, idx: int):
        """편집 요소 삭제."""
        target = self._target_list()
        if not (0 <= idx < len(target)):
            return
        self._push_history()
        target.pop(idx)

    @staticmethod
    def get_edit_bounds(edit: dict) -> tuple[int, int, int, int]:
        """편집의 바운딩 박스 반환."""
        if edit["type"] in ("mosaic", "blur", "fill"):
            return tuple(edit["box"])
        elif edit["type"] == "pen":
            pts = edit["points"]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        return (0, 0, 0, 0)

    # ==================== 렌더링용 ====================

    def all_visible_edits(self, fm=None) -> list[dict]:
        """렌더링용 전체 edits. 순서: 템플릿참조 → 직접편집 → 템플릿제작미리보기."""
        result = []
        # 1. 적용된 템플릿 (참조 해석)
        if fm:
            for tpl_name in self.applied_templates:
                layers = fm.load_named_template(tpl_name)
                for layer in layers:
                    if layer.get("visible", True):
                        result.extend(layer.get("edits", []))
        # 2. 직접 편집
        result.extend(self.edits)
        # 3. 템플릿 제작 미리보기
        if self.template_mode:
            for layer in self.template_layers:
                if layer.visible:
                    result.extend(layer.edits)
        return result

    @property
    def is_dirty(self) -> bool:
        return len(self._history) > 0
