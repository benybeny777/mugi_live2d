from __future__ import annotations

import argparse
import io
import json
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


def build_vrm(source: Path, output: Path, max_texture_size: int = 2048) -> dict[str, Any]:
    texture, texture_size = _texture_png(source, max_texture_size)
    height = 1.8
    width = height * texture_size[0] / texture_size[1]

    binary = BinaryBuilder()
    positions = [
        -width / 2,
        0.0,
        0.0,
        width / 2,
        0.0,
        0.0,
        width / 2,
        height,
        0.0,
        -width / 2,
        height,
        0.0,
    ]
    position_view = binary.add(struct.pack("<12f", *positions), target=34962)
    normal_view = binary.add(struct.pack("<12f", *([0.0, 0.0, 1.0] * 4)), target=34962)
    uv_view = binary.add(struct.pack("<8f", 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0), target=34962)
    joint_view = binary.add(bytes([0, 0, 0, 0] * 4), target=34962)
    weight_view = binary.add(struct.pack("<16f", *([1.0, 0.0, 0.0, 0.0] * 4)), target=34962)
    index_view = binary.add(struct.pack("<6H", 0, 1, 2, 0, 2, 3), target=34963)
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
    image_view = binary.add(texture)

    nodes: list[dict[str, Any]] = []
    root, bones = _build_skeleton(nodes)
    card_node = _add_node(nodes, "MugiCard")
    nodes[card_node].update({"mesh": 0, "skin": 0})

    accessors = [
        {
            "bufferView": position_view,
            "componentType": 5126,
            "count": 4,
            "type": "VEC3",
            "min": [-width / 2, 0.0, 0.0],
            "max": [width / 2, height, 0.0],
        },
        {"bufferView": normal_view, "componentType": 5126, "count": 4, "type": "VEC3"},
        {"bufferView": uv_view, "componentType": 5126, "count": 4, "type": "VEC2"},
        {"bufferView": joint_view, "componentType": 5121, "count": 4, "type": "VEC4"},
        {"bufferView": weight_view, "componentType": 5126, "count": 4, "type": "VEC4"},
        {
            "bufferView": index_view,
            "componentType": 5123,
            "count": 6,
            "type": "SCALAR",
            "min": [0],
            "max": [3],
        },
        {
            "bufferView": inverse_bind_view,
            "componentType": 5126,
            "count": 1,
            "type": "MAT4",
        },
    ]

    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "mugi_live2d scripts/build_vrm.py"},
        "extensionsUsed": ["VRMC_vrm", "KHR_materials_unlit"],
        "extensionsRequired": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {**VRM_META, "thumbnailImage": 0},
                "humanoid": {"humanBones": {name: {"node": node} for name, node in bones.items()}},
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
                    }
                ],
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
