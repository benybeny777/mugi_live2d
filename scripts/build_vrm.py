from __future__ import annotations

import argparse
import io
import json
import math
import struct
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "source" / "mugi-original.png"
DEFAULT_OUTPUT = ROOT / "exports" / "vrm" / "mugi.vrm"
LICENSE_URL = (
    "https://github.com/benybeny777/mugi_live2d/"
    "blob/main/docs/VRM.md#%E5%88%A9%E7%94%A8%E6%9D%A1%E4%BB%B6"
)
VRM_META: dict[str, Any] = {
    "name": "むぎ ペラ板 VRM",
    "version": "1.0.0",
    "authors": ["benybeny777"],
    "copyrightInformation": "Copyright (c) benybeny777. All rights reserved.",
    "references": ["source/mugi-original.png"],
    "licenseUrl": LICENSE_URL,
    "avatarPermission": "onlyAuthor",
    "allowExcessivelyViolentUsage": False,
    "allowExcessivelySexualUsage": False,
    "commercialUsage": "personalNonProfit",
    "allowPoliticalOrReligiousUsage": False,
    "allowAntisocialOrHateUsage": False,
    "creditNotation": "required",
    "allowRedistribution": False,
    "modification": "prohibited",
}
GRID_COLUMNS = 65
GRID_ROWS = 97
MORPH_NAMES = (
    "blinkLeft",
    "blinkRight",
    "aa",
    "ih",
    "ou",
    "ee",
    "oh",
    "happy",
    "angry",
    "sad",
    "relaxed",
    "surprised",
    "breath",
)


def _align4(data: bytes, padding: bytes = b"\x00") -> bytes:
    return data + padding * ((-len(data)) % 4)


class BinaryBuilder:
    def __init__(self) -> None:
        self.data = bytearray()
        self.buffer_views: list[dict[str, Any]] = []

    def add(self, payload: bytes, *, target: int | None = None) -> int:
        while len(self.data) % 4:
            self.data.append(0)
        offset = len(self.data)
        self.data.extend(payload)
        view: dict[str, Any] = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(payload),
        }
        if target is not None:
            view["target"] = target
        self.buffer_views.append(view)
        return len(self.buffer_views) - 1


def _texture_png(source: Path, max_texture_size: int) -> tuple[bytes, tuple[int, int]]:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        image.thumbnail((max_texture_size, max_texture_size), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue(), image.size


def _add_node(
    nodes: list[dict[str, Any]],
    name: str,
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> int:
    node: dict[str, Any] = {"name": name}
    if translation != (0.0, 0.0, 0.0):
        node["translation"] = list(translation)
    nodes.append(node)
    return len(nodes) - 1


def _build_skeleton(nodes: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    root = _add_node(nodes, "AvatarRoot")
    bone_defs = {
        "hips": ("Hips", (0.0, 0.9, 0.0), None),
        "spine": ("Spine", (0.0, 0.28, 0.0), "hips"),
        "chest": ("Chest", (0.0, 0.25, 0.0), "spine"),
        "neck": ("Neck", (0.0, 0.22, 0.0), "chest"),
        "head": ("Head", (0.0, 0.15, 0.0), "neck"),
        "leftUpperLeg": ("LeftUpperLeg", (0.14, 0.0, 0.0), "hips"),
        "leftLowerLeg": ("LeftLowerLeg", (0.0, -0.42, 0.0), "leftUpperLeg"),
        "leftFoot": ("LeftFoot", (0.0, -0.42, 0.0), "leftLowerLeg"),
        "rightUpperLeg": ("RightUpperLeg", (-0.14, 0.0, 0.0), "hips"),
        "rightLowerLeg": ("RightLowerLeg", (0.0, -0.42, 0.0), "rightUpperLeg"),
        "rightFoot": ("RightFoot", (0.0, -0.42, 0.0), "rightLowerLeg"),
        "leftUpperArm": ("LeftUpperArm", (0.24, 0.14, 0.0), "chest"),
        "leftLowerArm": ("LeftLowerArm", (0.30, 0.0, 0.0), "leftUpperArm"),
        "leftHand": ("LeftHand", (0.26, 0.0, 0.0), "leftLowerArm"),
        "rightUpperArm": ("RightUpperArm", (-0.24, 0.14, 0.0), "chest"),
        "rightLowerArm": ("RightLowerArm", (-0.30, 0.0, 0.0), "rightUpperArm"),
        "rightHand": ("RightHand", (-0.26, 0.0, 0.0), "rightLowerArm"),
    }
    bones: dict[str, int] = {}
    for bone, (name, translation, _) in bone_defs.items():
        bones[bone] = _add_node(nodes, name, translation)
    nodes[root]["children"] = [bones["hips"]]
    for bone, (_, _, parent) in bone_defs.items():
        if parent is not None:
            nodes[bones[parent]].setdefault("children", []).append(bones[bone])
    return root, bones


def _grid_geometry(
    width: float, height: float
) -> tuple[list[float], list[float], list[float], list[int]]:
    positions: list[float] = []
    normals: list[float] = []
    uvs: list[float] = []
    for row in range(GRID_ROWS):
        v = row / (GRID_ROWS - 1)
        y = height * (1.0 - v)
        for column in range(GRID_COLUMNS):
            u = column / (GRID_COLUMNS - 1)
            x = width * (u - 0.5)
            positions.extend((x, y, 0.0))
            normals.extend((0.0, 0.0, 1.0))
            uvs.extend((u, v))
    indices: list[int] = []
    for row in range(GRID_ROWS - 1):
        for column in range(GRID_COLUMNS - 1):
            top_left = row * GRID_COLUMNS + column
            top_right = top_left + 1
            bottom_left = top_left + GRID_COLUMNS
            bottom_right = bottom_left + 1
            indices.extend((top_left, bottom_left, top_right, top_right, bottom_left, bottom_right))
    return positions, normals, uvs, indices


def _gaussian(
    u: float, v: float, center: tuple[float, float], radius: tuple[float, float]
) -> float:
    x = (u - center[0]) / radius[0]
    y = (v - center[1]) / radius[1]
    return math.exp(-2.0 * (x * x + y * y))


def _eye_close(u: float, v: float, center: tuple[float, float], height: float) -> float:
    strength = _gaussian(u, v, center, (0.060, 0.027))
    return (v - center[1]) * height * 0.78 * strength


def _eye_expand(
    u: float, v: float, center: tuple[float, float], width: float, height: float
) -> tuple[float, float]:
    strength = _gaussian(u, v, center, (0.064, 0.030))
    return (
        (u - center[0]) * width * 0.14 * strength,
        (center[1] - v) * height * 0.16 * strength,
    )


def _mouth_deform(
    u: float,
    v: float,
    width: float,
    height: float,
    *,
    horizontal: float,
    vertical: float,
) -> tuple[float, float]:
    center = (0.500, 0.183)
    strength = _gaussian(u, v, center, (0.050, 0.024))
    return (
        (u - center[0]) * width * horizontal * strength,
        (center[1] - v) * height * vertical * strength,
    )


def _morph_offset(
    name: str, u: float, v: float, width: float, height: float
) -> tuple[float, float, float]:
    left_eye = (0.540, 0.151)
    right_eye = (0.466, 0.151)
    dx = 0.0
    dy = 0.0
    if name == "blinkLeft":
        dy = _eye_close(u, v, left_eye, height)
    elif name == "blinkRight":
        dy = _eye_close(u, v, right_eye, height)
    elif name == "aa":
        dx, dy = _mouth_deform(u, v, width, height, horizontal=0.12, vertical=0.72)
    elif name == "ih":
        dx, dy = _mouth_deform(u, v, width, height, horizontal=0.42, vertical=-0.12)
    elif name == "ou":
        dx, dy = _mouth_deform(u, v, width, height, horizontal=-0.34, vertical=0.42)
    elif name == "ee":
        dx, dy = _mouth_deform(u, v, width, height, horizontal=0.50, vertical=0.08)
    elif name == "oh":
        dx, dy = _mouth_deform(u, v, width, height, horizontal=-0.18, vertical=0.62)
    elif name in {"happy", "sad", "relaxed"}:
        direction = -1.0 if name == "sad" else 1.0
        amount = 0.0025 if name == "relaxed" else 0.004
        for corner in ((0.482, 0.183), (0.518, 0.183)):
            dy += direction * height * amount * _gaussian(u, v, corner, (0.020, 0.010))
        if name == "relaxed":
            dy += 0.34 * (_eye_close(u, v, left_eye, height) + _eye_close(u, v, right_eye, height))
    elif name == "angry":
        inner_brow = (0.496, 0.128) if u < 0.5 else (0.504, 0.128)
        outer_brow = (0.452, 0.128) if u < 0.5 else (0.548, 0.128)
        dy -= height * 0.010 * _gaussian(u, v, inner_brow, (0.030, 0.018))
        dy += height * 0.006 * _gaussian(u, v, outer_brow, (0.032, 0.018))
    elif name == "surprised":
        for eye in (left_eye, right_eye):
            eye_dx, eye_dy = _eye_expand(u, v, eye, width, height)
            dx += eye_dx
            dy += eye_dy
        mouth_dx, mouth_dy = _mouth_deform(u, v, width, height, horizontal=-0.12, vertical=0.58)
        dx += mouth_dx
        dy += mouth_dy
    elif name == "breath":
        torso = math.exp(-2.0 * ((v - 0.38) / 0.18) ** 2)
        center_falloff = math.exp(-1.5 * ((u - 0.5) / 0.32) ** 2)
        dx = (u - 0.5) * width * 0.012 * torso
        dy = height * 0.0035 * torso * center_falloff
    return dx, dy, 0.0


def _morph_targets(width: float, height: float) -> dict[str, list[float]]:
    targets = {name: [] for name in MORPH_NAMES}
    for row in range(GRID_ROWS):
        v = row / (GRID_ROWS - 1)
        for column in range(GRID_COLUMNS):
            u = column / (GRID_COLUMNS - 1)
            for name in MORPH_NAMES:
                targets[name].extend(_morph_offset(name, u, v, width, height))
    return targets


def _expression(node: int, index: int, **overrides: str) -> dict[str, Any]:
    return {
        "morphTargetBinds": [{"node": node, "index": index, "weight": 1.0}],
        **overrides,
    }


def build_vrm(source: Path, output: Path, max_texture_size: int = 2048) -> dict[str, Any]:
    texture, texture_size = _texture_png(source, max_texture_size)
    height = 1.8
    width = height * texture_size[0] / texture_size[1]

    binary = BinaryBuilder()
    positions, normals, uvs, indices = _grid_geometry(width, height)
    vertex_count = GRID_COLUMNS * GRID_ROWS
    position_view = binary.add(struct.pack(f"<{len(positions)}f", *positions), target=34962)
    normal_view = binary.add(struct.pack(f"<{len(normals)}f", *normals), target=34962)
    uv_view = binary.add(struct.pack(f"<{len(uvs)}f", *uvs), target=34962)
    joint_view = binary.add(bytes([0, 0, 0, 0] * vertex_count), target=34962)
    weight_values = [1.0, 0.0, 0.0, 0.0] * vertex_count
    weight_view = binary.add(struct.pack(f"<{len(weight_values)}f", *weight_values), target=34962)
    index_view = binary.add(struct.pack(f"<{len(indices)}H", *indices), target=34963)
    inverse_bind = [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        -0.9,
        0.0,
        1.0,
    ]
    inverse_bind_view = binary.add(struct.pack("<16f", *inverse_bind))
    morph_data = _morph_targets(width, height)
    morph_views: dict[str, int] = {}
    for name, values in morph_data.items():
        morph_views[name] = binary.add(struct.pack(f"<{len(values)}f", *values), target=34962)
    image_view = binary.add(texture)

    nodes: list[dict[str, Any]] = []
    root, bones = _build_skeleton(nodes)
    card_node = _add_node(nodes, "MugiCard")
    nodes[card_node].update({"mesh": 0, "skin": 0})

    accessors = [
        {
            "bufferView": position_view,
            "componentType": 5126,
            "count": vertex_count,
            "type": "VEC3",
            "min": [-width / 2, 0.0, 0.0],
            "max": [width / 2, height, 0.0],
        },
        {"bufferView": normal_view, "componentType": 5126, "count": vertex_count, "type": "VEC3"},
        {"bufferView": uv_view, "componentType": 5126, "count": vertex_count, "type": "VEC2"},
        {"bufferView": joint_view, "componentType": 5121, "count": vertex_count, "type": "VEC4"},
        {"bufferView": weight_view, "componentType": 5126, "count": vertex_count, "type": "VEC4"},
        {
            "bufferView": index_view,
            "componentType": 5123,
            "count": len(indices),
            "type": "SCALAR",
            "min": [0],
            "max": [vertex_count - 1],
        },
        {
            "bufferView": inverse_bind_view,
            "componentType": 5126,
            "count": 1,
            "type": "MAT4",
        },
    ]
    morph_accessor_indices: dict[str, int] = {}
    for name in MORPH_NAMES:
        values = morph_data[name]
        triples = list(zip(values[0::3], values[1::3], values[2::3], strict=True))
        accessor = {
            "bufferView": morph_views[name],
            "componentType": 5126,
            "count": vertex_count,
            "type": "VEC3",
            "min": [min(value[axis] for value in triples) for axis in range(3)],
            "max": [max(value[axis] for value in triples) for axis in range(3)],
        }
        morph_accessor_indices[name] = len(accessors)
        accessors.append(accessor)

    morph_indices = {name: index for index, name in enumerate(MORPH_NAMES)}
    preset_expressions = {
        "blinkLeft": _expression(card_node, morph_indices["blinkLeft"]),
        "blinkRight": _expression(card_node, morph_indices["blinkRight"]),
        "blink": {
            "morphTargetBinds": [
                {"node": card_node, "index": morph_indices["blinkLeft"], "weight": 1.0},
                {"node": card_node, "index": morph_indices["blinkRight"], "weight": 1.0},
            ]
        },
        "aa": _expression(card_node, morph_indices["aa"]),
        "ih": _expression(card_node, morph_indices["ih"]),
        "ou": _expression(card_node, morph_indices["ou"]),
        "ee": _expression(card_node, morph_indices["ee"]),
        "oh": _expression(card_node, morph_indices["oh"]),
        "happy": _expression(card_node, morph_indices["happy"], overrideMouth="blend"),
        "angry": _expression(card_node, morph_indices["angry"]),
        "sad": _expression(card_node, morph_indices["sad"], overrideMouth="blend"),
        "relaxed": _expression(
            card_node, morph_indices["relaxed"], overrideBlink="blend", overrideMouth="blend"
        ),
        "surprised": _expression(
            card_node, morph_indices["surprised"], overrideBlink="blend", overrideMouth="blend"
        ),
    }

    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "mugi_live2d scripts/build_vrm.py"},
        "extensionsUsed": ["VRMC_vrm", "KHR_materials_unlit"],
        "extensionsRequired": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {**VRM_META, "thumbnailImage": 0},
                "humanoid": {"humanBones": {name: {"node": node} for name, node in bones.items()}},
                "expressions": {
                    "preset": preset_expressions,
                    "custom": {"breath": _expression(card_node, morph_indices["breath"])},
                },
            }
        },
        "scene": 0,
        "scenes": [{"name": "Mugi VRM", "nodes": [root, card_node]}],
        "nodes": nodes,
        "meshes": [
            {
                "name": "MugiCardMesh",
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": 0,
                            "NORMAL": 1,
                            "TEXCOORD_0": 2,
                            "JOINTS_0": 3,
                            "WEIGHTS_0": 4,
                        },
                        "indices": 5,
                        "material": 0,
                        "targets": [
                            {"POSITION": morph_accessor_indices[name]} for name in MORPH_NAMES
                        ],
                    }
                ],
                "weights": [0.0] * len(MORPH_NAMES),
                "extras": {"targetNames": list(MORPH_NAMES)},
            }
        ],
        "skins": [{"inverseBindMatrices": 6, "joints": [bones["hips"]], "skeleton": bones["hips"]}],
        "materials": [
            {
                "name": "MugiUnlitTransparent",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
                "alphaMode": "BLEND",
                "doubleSided": True,
                "extensions": {"KHR_materials_unlit": {}},
            }
        ],
        "textures": [{"sampler": 0, "source": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"name": "MugiTexture", "bufferView": image_view, "mimeType": "image/png"}],
        "accessors": accessors,
        "bufferViews": binary.buffer_views,
        "buffers": [{"byteLength": len(binary.data)}],
    }

    json_data = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()
    json_chunk = _align4(json_data, b" ")
    bin_chunk = _align4(bytes(binary.data))
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    glb = (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
        + bin_chunk
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(glb)
    return {
        "output": str(output),
        "bytes": len(glb),
        "texture": list(texture_size),
        "cardMeters": [round(width, 6), height],
        "vertices": vertex_count,
        "morphTargets": list(MORPH_NAMES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Mugi flat-card VRM 1.0 model")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-texture-size", type=int, default=2048)
    args = parser.parse_args()
    result = build_vrm(args.source.resolve(), args.output.resolve(), args.max_texture_size)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
