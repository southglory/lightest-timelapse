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
    """
    편집 모드:
    - 일반 모드: 이미지에 직접 편집 (단일 edits 리스트)
    - 템플릿 제작 모드: 레이어 구조로 편집 → 템플릿으로 저장
    """

    def __init__(self):
        # 일반 편집 (이미지별)
        self.edits: list[dict] = []

        # 템플릿 제작 모드
        self.template_mode = False
        self.template_layers: list[Layer] = []
        self.active_layer_idx: int = -1

        # 공통
        self._history: list = []
        self._redo_stack: list = []
        self.current_tool: str | None = None
        self.pen_color = (255, 0, 0)
        self.pen_width = 3
        self.fill_color = (0, 0, 0)
        self.mosaic_block = 16
        self.blur_radius = 20
        self._pen_points: list[tuple[int, int]] = []

    @property
    def active_layer(self) -> Layer | None:
        if self.template_mode and 0 <= self.active_layer_idx < len(self.template_layers):
            return self.template_layers[self.active_layer_idx]
        return None

    def set_tool(self, tool: str | None):
        self.finish_pen()
        self.current_tool = tool

    # --- 상태 관리 ---

    def _snapshot(self):
        if self.template_mode:
            return {"mode": "template", "layers": [l.to_dict() for l in self.template_layers]}
        else:
            return {"mode": "normal", "edits": copy.deepcopy(self.edits)}

    def _restore(self, snap):
        if snap["mode"] == "template":
            self.template_layers = [Layer.from_dict(d) for d in snap["layers"]]
            if self.active_layer_idx >= len(self.template_layers):
                self.active_layer_idx = max(-1, len(self.template_layers) - 1)
        else:
            self.edits = snap["edits"]

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

    # --- 일반 모드 ---

    def load_edits(self, edits: list[dict]):
        self.edits = copy.deepcopy(edits)
        self._history.clear()
        self._redo_stack.clear()

    def clear_edits(self):
        self.edits = []
        self._history.clear()
        self._redo_stack.clear()

    # --- 템플릿 제작 모드 ---

    def start_template_mode(self):
        self.template_mode = True
        self.template_layers = [Layer("레이어 1")]
        self.active_layer_idx = 0
        self._history.clear()
        self._redo_stack.clear()

    def end_template_mode(self) -> dict | None:
        """템플릿 제작 종료. 레이어 데이터를 반환."""
        if not self.template_mode:
            return None
        result = [l.to_dict() for l in self.template_layers if l.edits]
        self.template_mode = False
        self.template_layers = []
        self.active_layer_idx = -1
        self._history.clear()
        self._redo_stack.clear()
        if not result:
            return None
        return result

    def cancel_template_mode(self):
        self.template_mode = False
        self.template_layers = []
        self.active_layer_idx = -1
        self._history.clear()
        self._redo_stack.clear()

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
        if not self.template_mode:
            return
        if not (0 <= idx < len(self.template_layers) and 0 <= new_idx < len(self.template_layers)):
            return
        self._push_history()
        self.template_layers[idx], self.template_layers[new_idx] = \
            self.template_layers[new_idx], self.template_layers[idx]
        if self.active_layer_idx == idx:
            self.active_layer_idx = new_idx

    def set_active_layer(self, idx: int):
        if 0 <= idx < len(self.template_layers):
            self.active_layer_idx = idx

    # --- 편집 추가 ---

    def _target_list(self) -> list[dict]:
        """편집을 추가할 대상 리스트."""
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

    # --- 렌더링용 ---

    def all_visible_edits(self) -> list[dict]:
        """현재 표시할 전체 edits. 일반 편집 + 템플릿 미리보기."""
        result = list(self.edits)
        if self.template_mode:
            for layer in self.template_layers:
                if layer.visible:
                    result.extend(layer.edits)
        return result

    @property
    def is_dirty(self) -> bool:
        return len(self._history) > 0
