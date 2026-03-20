"""Self-contained HumanTools: layout transformer + zones."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from uuid import uuid4

Number = Union[float, int]
Color = str
AlignX = Literal["left", "center", "right"]
AlignY = Literal["top", "middle", "bottom"]
ResizeAnchor = Literal["center", "top-left", "bottom-right"]


# ---------------------------------------------------------------------------
# Zone types
# ---------------------------------------------------------------------------

@dataclass
class Zone:
    x0: float; y0: float; x1: float; y1: float

    @property
    def width(self) -> float: return self.x1 - self.x0
    @property
    def height(self) -> float: return self.y1 - self.y0
    @property
    def center(self) -> Tuple[float, float]: return (self.x0 + self.width / 2, self.y0 + self.height / 2)
    @property
    def x(self) -> float: return self.x0
    @property
    def y(self) -> float: return self.y0

    def inset(self, dx: float = 0, dy: float = 0) -> Zone: return Zone(self.x0 + dx, self.y0 + dy, self.x1 - dx, self.y1 - dy)
    def outset(self, dx: float = 0, dy: float = 0) -> Zone: return Zone(self.x0 - dx, self.y0 - dy, self.x1 + dx, self.y1 + dy)
    def to_xywh(self) -> XYWHZone: return XYWHZone(self.x0, self.y0, self.width, self.height)

    @classmethod
    def from_xywh(cls, x: float, y: float, w: float, h: float) -> Zone: return cls(x, y, x + w, y + h)


@dataclass
class XYWHZone:
    x: float; y: float; width: float; height: float

    @property
    def right(self) -> float: return self.x + self.width
    @property
    def bottom(self) -> float: return self.y + self.height
    @property
    def center_x(self) -> float: return self.x + self.width / 2
    @property
    def center_y(self) -> float: return self.y + self.height / 2
    @property
    def center(self) -> Tuple[float, float]: return (self.center_x, self.center_y)

    def expand(self, padding: Number) -> XYWHZone: return XYWHZone(self.x - padding, self.y - padding, self.width + padding * 2, self.height + padding * 2)
    def inset(self, dx: float = 0, dy: float = 0) -> XYWHZone: return XYWHZone(self.x + dx, self.y + dy, self.width - 2 * dx, self.height - 2 * dy)
    def outset(self, dx: float = 0, dy: float = 0) -> XYWHZone: return XYWHZone(self.x - dx, self.y - dy, self.width + 2 * dx, self.height + 2 * dy)
    def to_bounds(self) -> Zone: return Zone(self.x, self.y, self.right, self.bottom)

    @classmethod
    def from_bounds(cls, x0: float, y0: float, x1: float, y1: float) -> XYWHZone: return cls(x0, y0, x1 - x0, y1 - y0)


HumanToolZone = XYWHZone


# ---------------------------------------------------------------------------
# Layout transformer
# ---------------------------------------------------------------------------

Element = Dict[str, Any]


class HumanToolLayoutTransformer:
    def __init__(self, layout_json: Dict[str, Any]):
        self.layout = layout_json
        self._index_map: Dict[str, Element] = {}
        self._parent_map: Dict[str, Element] = {}
        self._rebuild_index()

    @property
    def generated_layout(self) -> Dict[str, Any]:
        return self.layout

    @staticmethod
    def _as_list(ids: Union[str, List[str]]) -> List[str]:
        return [ids] if isinstance(ids, str) else ids

    def _rebuild_index(self):
        self._index_map = {}
        self._parent_map = {}
        def traverse(node, parent):
            if "id" in node:
                self._index_map[node["id"]] = node
                if parent: self._parent_map[node["id"]] = parent
            for child in node.get("children", []):
                traverse(child, node)
        traverse(self.layout, None)

    def _get_nodes(self, ids: Union[str, List[str]]) -> List[Element]:
        return [n for eid in self._as_list(ids) if (n := self._index_map.get(eid))]

    def _get_bounds(self, nodes: List[Element]) -> Optional[HumanToolZone]:
        if not nodes: return None
        min_x = min(n["x"] for n in nodes); min_y = min(n["y"] for n in nodes)
        max_x = max(n["x"] + n["width"] for n in nodes); max_y = max(n["y"] + n["height"] for n in nodes)
        return HumanToolZone(min_x, min_y, max_x - min_x, max_y - min_y)

    # --- Query ---

    def get_by_id(self, element_id: str) -> Element:
        node = self._index_map.get(element_id)
        if not node: raise KeyError(f"No element with id '{element_id}'")
        return node

    # --- Add / Delete ---

    def add_element(self, type: str, x: float, y: float, w: float, h: float, **kwargs) -> str:
        new_id = str(uuid4())
        el = {"id": new_id, "type": type, "x": x, "y": y, "width": w, "height": h, **kwargs}
        self.layout.setdefault("children", []).append(el)
        self._rebuild_index()
        return new_id

    def delete_elements(self, ids: Union[str, List[str]]):
        for eid in self._as_list(ids):
            parent = self._parent_map.get(eid, self.layout)
            parent["children"] = [c for c in parent.get("children", []) if c["id"] != eid]
        self._rebuild_index()

    # --- Move / Resize / Rotate ---

    def move_elements(self, ids: List[str], dx: Number, dy: Number):
        for node in self._get_nodes(ids):
            node["x"] += dx; node["y"] += dy

    def resize_elements(self, ids: List[str], width: Optional[Number] = None, height: Optional[Number] = None, lock_aspect: bool = True, anchor: ResizeAnchor = "center"):
        for node in self._get_nodes(ids):
            old_w, old_h, old_x, old_y = node["width"], node["height"], node["x"], node["y"]
            new_w, new_h = width, height
            if lock_aspect:
                ratio = old_w / old_h if old_h > 0 else 1
                if new_w is not None and new_h is None: new_h = new_w / ratio
                elif new_h is not None and new_w is None: new_w = new_h * ratio
            new_w = new_w if new_w is not None else old_w
            new_h = new_h if new_h is not None else old_h
            node["width"] = new_w; node["height"] = new_h
            if anchor == "center":
                node["x"] = old_x + (old_w - new_w) / 2; node["y"] = old_y + (old_h - new_h) / 2

    def rotate_element(self, ids: List[str], angle: Number):
        for node in self._get_nodes(ids):
            node["rotation"] = angle % 360

    def crop_element(self, id: str, crop_zone: HumanToolZone):
        node = self._index_map.get(id)
        if node: node["crop"] = {"x": crop_zone.x, "y": crop_zone.y, "width": crop_zone.width, "height": crop_zone.height}

    # --- Layout ---

    def align_elements(self, ids: List[str], align_x: Optional[AlignX] = None, align_y: Optional[AlignY] = None, to_stage: bool = False):
        nodes = self._get_nodes(ids)
        if not nodes: return
        target = HumanToolZone(0, 0, self.layout["width"], self.layout["height"]) if to_stage else self._get_bounds(nodes)
        if not target: return
        for node in nodes:
            if align_x == "left": node["x"] = target.x
            elif align_x == "right": node["x"] = target.right - node["width"]
            elif align_x == "center": node["x"] = target.center_x - node["width"] / 2
            if align_y == "top": node["y"] = target.y
            elif align_y == "bottom": node["y"] = target.bottom - node["height"]
            elif align_y == "middle": node["y"] = target.center_y - node["height"] / 2

    def distribute_elements(self, ids: List[str], axis: Literal["x", "y"], spacing: Optional[Number] = None):
        nodes = self._get_nodes(ids)
        if len(nodes) < 2: return
        prop = "x" if axis == "x" else "y"
        dim = "width" if axis == "x" else "height"
        nodes.sort(key=lambda n: n[prop])
        if spacing is not None:
            cursor = nodes[0][prop]
            for node in nodes: node[prop] = cursor; cursor += node[dim] + spacing
        else:
            start = nodes[0][prop]; end = nodes[-1][prop] + nodes[-1][dim]
            total_content = sum(n[dim] for n in nodes)
            gap = (end - start - total_content) / (len(nodes) - 1)
            cursor = start
            for node in nodes: node[prop] = cursor; cursor += node[dim] + gap

    def create_grid_layout(self, ids: List[str], cols: int, gutter: Number = 10):
        nodes = self._get_nodes(ids)
        if not nodes: return
        cell_w, cell_h = nodes[0]["width"], nodes[0]["height"]
        start_x, start_y = min(n["x"] for n in nodes), min(n["y"] for n in nodes)
        for i, node in enumerate(nodes):
            node["x"] = start_x + (i % cols) * (cell_w + gutter)
            node["y"] = start_y + (i // cols) * (cell_h + gutter)

    # --- Layer order ---

    def reorder_layer(self, ids: Union[str, List[str]], action: Literal["front", "back", "forward", "backward"]):
        for eid in self._as_list(ids):
            node = self._index_map.get(eid)
            parent = self._parent_map.get(eid, self.layout)
            siblings = parent["children"]
            if node not in siblings: continue
            idx = siblings.index(node); siblings.pop(idx)
            if action == "front": siblings.append(node)
            elif action == "back": siblings.insert(0, node)
            elif action == "forward": siblings.insert(min(len(siblings), idx + 1), node)
            elif action == "backward": siblings.insert(max(0, idx - 1), node)

    # --- Grouping ---

    def group_elements(self, ids: List[str]) -> str:
        nodes = self._get_nodes(ids)
        if not nodes: raise ValueError("Empty selection")
        bounds = self._get_bounds(nodes)
        if not bounds: raise ValueError("Cannot calculate bounds")
        parent = self._parent_map.get(nodes[0]["id"], self.layout)
        group_id = str(uuid4())
        group_node = {"id": group_id, "type": "group", "x": bounds.x, "y": bounds.y, "width": bounds.width, "height": bounds.height, "scaleX": 1, "scaleY": 1, "rotation": 0}
        # Flat format: group is a sibling, children reference it via groupId
        parent["children"] = [c for c in parent["children"] if c["id"] not in ids]
        parent["children"].append(group_node)
        for node in nodes:
            node["x"] -= bounds.x; node["y"] -= bounds.y
            node["groupId"] = group_id
            parent["children"].append(node)
        self._rebuild_index()
        return group_id

    def ungroup_elements(self, group_id: str):
        group = self._index_map.get(group_id)
        if not group or group.get("type") != "group": return
        parent = self._parent_map.get(group_id, self.layout)
        parent["children"].remove(group)
        for child in parent["children"]:
            if child.get("groupId") != group_id: continue
            child["x"] += group["x"]; child["y"] += group["y"]
            del child["groupId"]
        self._rebuild_index()

    # --- Style ---

    def update_style(self, ids: Union[str, List[str]], **kwargs):
        for node in self._get_nodes(ids):
            for k, v in kwargs.items(): node[k] = v

    # --- Background ---

    def replace_image_source(self, id: str, new_url: str):
        node = self._index_map.get(id)
        if node: node["src"] = new_url

    def set_background(self, color: Optional[Color] = None, image_url: Optional[str] = None):
        if color: self.layout["background"] = color
        elif image_url: self.layout["background"] = {"type": "image", "src": image_url}
