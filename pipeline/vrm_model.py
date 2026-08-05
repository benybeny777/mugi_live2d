from __future__ import annotations

import io
import json
import math
import struct
from pathlib import Path
from typing import Any

from PIL import Image

from pipeline.vrm_layers import (
    LayerSprite,
    extract_layer_sprites,
    flatten_sprites,
)

LICENSE_URL = (
    "https://github.com/benybeny777/mugi_live2d/"
    "blob/main/docs/VRM.md#%E5%88%A9%E7%94%A8%E6%9D%A1%E4%BB%B6"
)
VRM_META: dict[str, Any] = {
    "name": "むぎ 多層ペラ板 VRM",
    "version": "2.0.0",
    "authors": ["benybeny777"],
    "copyrightInformation": "Copyright (c) benybeny777. All rights reserved.",
    "references": ["work/psd/hiyori/mugi-hiyori-compatible-final.psd"],
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


def _build_skeleton(
    nodes: list[dict[str, Any]],
) -> tuple[int, dict[str, int], dict[str, tuple[float, float, float]]]:
    root = _add_node(nodes, "AvatarRoot")
    bone_defs = {
        "hips": ("Hips", (0.0, 0.84, 0.0), None),
        "spine": ("Spine", (0.0, 0.22, 0.0), "hips"),
        "chest": ("Chest", (0.0, 0.24, 0.0), "spine"),
        "neck": ("Neck", (0.0, 0.08, 0.0), "chest"),
        "head": ("Head", (0.0, 0.04, 0.0), "neck"),
        "leftUpperLeg": ("LeftUpperLeg", (0.075, 0.0, 0.0), "hips"),
        "leftLowerLeg": ("LeftLowerLeg", (0.0, -0.39, 0.0), "leftUpperLeg"),
        "leftFoot": ("LeftFoot", (0.0, -0.34, 0.0), "leftLowerLeg"),
        "rightUpperLeg": ("RightUpperLeg", (-0.075, 0.0, 0.0), "hips"),
        "rightLowerLeg": ("RightLowerLeg", (0.0, -0.39, 0.0), "rightUpperLeg"),
        "rightFoot": ("RightFoot", (0.0, -0.34, 0.0), "rightLowerLeg"),
        "leftUpperArm": ("LeftUpperArm", (0.16, 0.05, 0.0), "chest"),
        "leftLowerArm": ("LeftLowerArm", (0.30, 0.0, 0.0), "leftUpperArm"),
        "leftHand": ("LeftHand", (0.25, 0.0, 0.0), "leftLowerArm"),
        "rightUpperArm": ("RightUpperArm", (-0.16, 0.05, 0.0), "chest"),
        "rightLowerArm": ("RightLowerArm", (-0.30, 0.0, 0.0), "rightUpperArm"),
        "rightHand": ("RightHand", (-0.25, 0.0, 0.0), "rightLowerArm"),
    }
    bones: dict[str, int] = {}
    world: dict[str, tuple[float, float, float]] = {}
    for bone, (name, translation, _) in bone_defs.items():
        bones[bone] = _add_node(nodes, name, translation)
    nodes[root]["children"] = [bones["hips"]]
    for bone, (_, translation, parent) in bone_defs.items():
        if parent is None:
            world[bone] = translation
        else:
            nodes[bones[parent]].setdefault("children", []).append(bones[bone])
            parent_position = world[parent]
            world[bone] = tuple(parent_position[index] + translation[index] for index in range(3))
    return root, bones, world


def _png_bytes(image: Image.Image, max_size: tuple[int, int] | None = None) -> bytes:
    converted = image.convert("RGBA")
    if max_size is not None:
        converted.thumbnail(max_size, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    converted.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _quad(sprite: LayerSprite, canvas_size: tuple[int, int]) -> list[tuple[float, float, float]]:
    canvas_width, canvas_height = canvas_size
    model_height = 1.8
    model_width = model_height * canvas_width / canvas_height
    left, top, right, bottom = sprite.canvas_box
    world_left = model_width * (left / canvas_width - 0.5)
    world_right = model_width * (right / canvas_width - 0.5)
    world_top = model_height * (1.0 - top / canvas_height)
    world_bottom = model_height * (1.0 - bottom / canvas_height)
    if sprite.name == "mouth_inside":
        center = (world_top + world_bottom) / 2.0
        world_top = center
        world_bottom = center
    return [
        (world_left, world_bottom, sprite.depth),
        (world_right, world_bottom, sprite.depth),
        (world_right, world_top, sprite.depth),
        (world_left, world_top, sprite.depth),
    ]


def _rotate(
    point: tuple[float, float, float], pivot: tuple[float, float], angle_degrees: float
) -> tuple[float, float, float]:
    angle = math.radians(angle_degrees)
    x = point[0] - pivot[0]
    y = point[1] - pivot[1]
    return (
        pivot[0] + x * math.cos(angle) - y * math.sin(angle),
        pivot[1] + x * math.sin(angle) + y * math.cos(angle),
        point[2],
    )


def _scale(
    point: tuple[float, float, float], center: tuple[float, float], sx: float, sy: float
) -> tuple[float, float, float]:
    return (
        center[0] + (point[0] - center[0]) * sx,
        center[1] + (point[1] - center[1]) * sy,
        point[2],
    )


def _target_names(sprite_name: str) -> list[str]:
    if sprite_name in {"left_eye_white", "right_eye_white"}:
        return ["blink", "wide"]
    if sprite_name in {"left_iris", "right_iris"}:
        return ["blink", "wide", "lookLeft", "lookRight", "lookUp", "lookDown"]
    if sprite_name in {"left_lashes", "right_lashes"}:
        return ["blink", "wide", "angry", "sad"]
    if sprite_name in {"mouth", "mouth_inside"}:
        return ["aa", "ih", "ou", "ee", "oh", "happy", "sad"]
    if sprite_name == "torso":
        return ["breath", "idleLeft", "idleRight"]
    if sprite_name in {
        "screen_left_arm",
        "screen_right_arm",
        "screen_left_leg",
        "screen_right_leg",
        "back_hair",
        "front_hair",
        "accessory",
    }:
        return ["idleLeft", "idleRight"]
    return []


def _target_vertices(
    sprite: LayerSprite,
    target: str,
    base: list[tuple[float, float, float]],
    bone_world: dict[str, tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    center = (
        sum(point[0] for point in base) / len(base),
        sum(point[1] for point in base) / len(base),
    )
    if target == "blink":
        return [_scale(point, center, 1.0, 0.10) for point in base]
    if target == "wide":
        return [_scale(point, center, 1.03, 1.16) for point in base]
    if target.startswith("look"):
        movement = {
            "lookLeft": (0.011, 0.0),
            "lookRight": (-0.011, 0.0),
            "lookUp": (0.0, 0.008),
            "lookDown": (0.0, -0.008),
        }[target]
        return [(x + movement[0], y + movement[1], z) for x, y, z in base]
    if target in {"aa", "ih", "ou", "ee", "oh"}:
        scales = {
            "aa": (1.08, 2.20),
            "ih": (1.35, 0.75),
            "ou": (0.72, 1.55),
            "ee": (1.45, 0.82),
            "oh": (0.82, 1.95),
        }
        if sprite.name == "mouth_inside":
            left = min(point[0] for point in base)
            right = max(point[0] for point in base)
            original_height = 1.8 * (sprite.canvas_box[3] - sprite.canvas_box[1]) / 4175
            width_scale, height_scale = scales[target]
            half_height = original_height * height_scale / 2
            scaled_left = center[0] + (left - center[0]) * width_scale
            scaled_right = center[0] + (right - center[0]) * width_scale
            return [
                (scaled_left, center[1] - half_height, base[0][2]),
                (scaled_right, center[1] - half_height, base[1][2]),
                (scaled_right, center[1] + half_height, base[2][2]),
                (scaled_left, center[1] + half_height, base[3][2]),
            ]
        return [_scale(point, center, *scales[target]) for point in base]
    if target == "happy":
        return [(x, y + 0.003, z) for x, y, z in base]
    if target == "sad":
        if "lashes" in sprite.name:
            direction = -3.0 if sprite.name.startswith("left") else 3.0
            return [_rotate(point, center, direction) for point in base]
        return [(x, y - 0.003, z) for x, y, z in base]
    if target == "angry":
        direction = 4.0 if sprite.name.startswith("left") else -4.0
        return [_rotate(point, center, direction) for point in base]
    if target == "breath":
        anchor = (center[0], min(point[1] for point in base))
        return [_scale(point, anchor, 1.008, 1.004) for point in base]
    if target in {"idleLeft", "idleRight"}:
        direction = 1.0 if target == "idleLeft" else -1.0
        if sprite.name == "torso":
            bottom = min(point[1] for point in base)
            top = max(point[1] for point in base)
            span = max(top - bottom, 1e-6)
            return [(x + direction * 0.006 * (y - bottom) / span, y, z) for x, y, z in base]
        if "arm" in sprite.name or "leg" in sprite.name:
            angle = direction * (1.2 if "arm" in sprite.name else 0.35)
            if sprite.name.startswith("screen_right"):
                angle *= -1.0
            pivot = bone_world[sprite.bone][:2]
            return [_rotate(point, pivot, angle) for point in base]
        if sprite.name in {"back_hair", "front_hair", "accessory"}:
            top = max(point[1] for point in base)
            bottom = min(point[1] for point in base)
            span = max(top - bottom, 1e-6)
            return [(x - direction * 0.008 * (top - y) / span, y, z) for x, y, z in base]
    return base


def _flatten(values: list[tuple[float, float, float]]) -> list[float]:
    return [component for point in values for component in point]


def _expression_bind(node: int, index: int, weight: float = 1.0) -> dict[str, Any]:
    return {"node": node, "index": index, "weight": weight}


def build_layered_vrm(psd_path: Path, output: Path, max_texture_size: int = 2048) -> dict[str, Any]:
    canvas_size, sprites = extract_layer_sprites(psd_path)
    binary = BinaryBuilder()
    nodes: list[dict[str, Any]] = []
    root, bones, bone_world = _build_skeleton(nodes)
    joint_names = list(bones)
    joint_lookup = {name: index for index, name in enumerate(joint_names)}

    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    textures: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    sprite_nodes: dict[str, int] = {}
    target_indices: dict[str, dict[str, int]] = {}

    thumbnail = flatten_sprites(canvas_size, sprites)
    thumbnail_view = binary.add(_png_bytes(thumbnail, (512, 512)))
    images.append({"name": "MugiThumbnail", "bufferView": thumbnail_view, "mimeType": "image/png"})

    texture_scale = min(1.0, max_texture_size / max(canvas_size))
    for sprite in sprites:
        resized = sprite.image
        if texture_scale < 1.0:
            resized = sprite.image.resize(
                (
                    max(1, round(sprite.image.width * texture_scale)),
                    max(1, round(sprite.image.height * texture_scale)),
                ),
                Image.Resampling.LANCZOS,
            )
        image_view = binary.add(_png_bytes(resized))
        image_index = len(images)
        images.append(
            {"name": f"{sprite.name}Texture", "bufferView": image_view, "mimeType": "image/png"}
        )
        texture_index = len(textures)
        textures.append({"sampler": 0, "source": image_index})
        material_index = len(materials)
        materials.append(
            {
                "name": f"{sprite.name}Unlit",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                    "baseColorTexture": {"index": texture_index},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
                "alphaMode": "BLEND",
                "doubleSided": True,
                "extensions": {"KHR_materials_unlit": {}},
            }
        )

        base = _quad(sprite, canvas_size)
        position_values = _flatten(base)
        position_view = binary.add(
            struct.pack(f"<{len(position_values)}f", *position_values), target=34962
        )
        position_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": position_view,
                "componentType": 5126,
                "count": 4,
                "type": "VEC3",
                "min": [min(point[axis] for point in base) for axis in range(3)],
                "max": [max(point[axis] for point in base) for axis in range(3)],
            }
        )
        normal_view = binary.add(struct.pack("<12f", *([0.0, 0.0, 1.0] * 4)), target=34962)
        normal_accessor = len(accessors)
        accessors.append(
            {"bufferView": normal_view, "componentType": 5126, "count": 4, "type": "VEC3"}
        )
        uv_view = binary.add(
            struct.pack("<8f", 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0), target=34962
        )
        uv_accessor = len(accessors)
        accessors.append({"bufferView": uv_view, "componentType": 5126, "count": 4, "type": "VEC2"})
        joint = joint_lookup[sprite.bone]
        joint_view = binary.add(bytes([joint, 0, 0, 0] * 4), target=34962)
        joint_accessor = len(accessors)
        accessors.append(
            {"bufferView": joint_view, "componentType": 5121, "count": 4, "type": "VEC4"}
        )
        weight_view = binary.add(struct.pack("<16f", *([1.0, 0.0, 0.0, 0.0] * 4)), target=34962)
        weight_accessor = len(accessors)
        accessors.append(
            {"bufferView": weight_view, "componentType": 5126, "count": 4, "type": "VEC4"}
        )
        index_view = binary.add(struct.pack("<6H", 0, 1, 2, 0, 2, 3), target=34963)
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": index_view,
                "componentType": 5123,
                "count": 6,
                "type": "SCALAR",
                "min": [0],
                "max": [3],
            }
        )

        targets: list[dict[str, int]] = []
        names = _target_names(sprite.name)
        target_indices[sprite.name] = {name: index for index, name in enumerate(names)}
        for target_name in names:
            transformed = _target_vertices(sprite, target_name, base, bone_world)
            offsets = [
                tuple(transformed[index][axis] - base[index][axis] for axis in range(3))
                for index in range(4)
            ]
            offset_values = _flatten(offsets)
            offset_view = binary.add(
                struct.pack(f"<{len(offset_values)}f", *offset_values), target=34962
            )
            offset_accessor = len(accessors)
            accessors.append(
                {
                    "bufferView": offset_view,
                    "componentType": 5126,
                    "count": 4,
                    "type": "VEC3",
                    "min": [min(point[axis] for point in offsets) for axis in range(3)],
                    "max": [max(point[axis] for point in offsets) for axis in range(3)],
                }
            )
            targets.append({"POSITION": offset_accessor})

        mesh_index = len(meshes)
        primitive: dict[str, Any] = {
            "attributes": {
                "POSITION": position_accessor,
                "NORMAL": normal_accessor,
                "TEXCOORD_0": uv_accessor,
                "JOINTS_0": joint_accessor,
                "WEIGHTS_0": weight_accessor,
            },
            "indices": index_accessor,
            "material": material_index,
        }
        if targets:
            primitive["targets"] = targets
        mesh: dict[str, Any] = {"name": f"{sprite.name}Mesh", "primitives": [primitive]}
        if names:
            mesh["weights"] = [0.0] * len(names)
            mesh["extras"] = {"targetNames": names}
        meshes.append(mesh)
        node = _add_node(nodes, sprite.name)
        nodes[node].update({"mesh": mesh_index, "skin": 0})
        sprite_nodes[sprite.name] = node

    inverse_bind_values: list[float] = []
    for name in joint_names:
        x, y, z = bone_world[name]
        inverse_bind_values.extend(
            [
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
                -x,
                -y,
                -z,
                1.0,
            ]
        )
    inverse_bind_view = binary.add(
        struct.pack(f"<{len(inverse_bind_values)}f", *inverse_bind_values)
    )
    inverse_bind_accessor = len(accessors)
    accessors.append(
        {
            "bufferView": inverse_bind_view,
            "componentType": 5126,
            "count": len(joint_names),
            "type": "MAT4",
        }
    )

    def bind(sprite_name: str, target_name: str, weight: float = 1.0) -> dict[str, Any]:
        return _expression_bind(
            sprite_nodes[sprite_name], target_indices[sprite_name][target_name], weight
        )

    left_eye_parts = ["right_eye_white", "right_iris", "right_lashes"]
    right_eye_parts = ["left_eye_white", "left_iris", "left_lashes"]
    both_eye_parts = [*left_eye_parts, *right_eye_parts]
    mouth_parts = ["mouth", "mouth_inside"]
    preset: dict[str, Any] = {
        "blinkLeft": {"morphTargetBinds": [bind(name, "blink") for name in left_eye_parts]},
        "blinkRight": {"morphTargetBinds": [bind(name, "blink") for name in right_eye_parts]},
        "blink": {"morphTargetBinds": [bind(name, "blink") for name in both_eye_parts]},
    }
    for vowel in ("aa", "ih", "ou", "ee", "oh"):
        preset[vowel] = {"morphTargetBinds": [bind(name, vowel) for name in mouth_parts]}
    for direction in ("lookLeft", "lookRight", "lookUp", "lookDown"):
        preset[direction] = {
            "morphTargetBinds": [bind("left_iris", direction), bind("right_iris", direction)]
        }
    preset.update(
        {
            "happy": {
                "morphTargetBinds": [
                    bind("mouth", "happy"),
                    *[bind(name, "blink", 0.15) for name in both_eye_parts],
                ],
                "overrideMouth": "blend",
            },
            "angry": {
                "morphTargetBinds": [bind("left_lashes", "angry"), bind("right_lashes", "angry")]
            },
            "sad": {
                "morphTargetBinds": [
                    bind("mouth", "sad"),
                    bind("left_lashes", "sad"),
                    bind("right_lashes", "sad"),
                ],
                "overrideMouth": "blend",
            },
            "relaxed": {
                "morphTargetBinds": [
                    bind("mouth", "happy", 0.35),
                    *[bind(name, "blink", 0.35) for name in both_eye_parts],
                ],
                "overrideBlink": "blend",
                "overrideMouth": "blend",
            },
            "surprised": {
                "morphTargetBinds": [
                    *[bind(name, "wide") for name in both_eye_parts],
                    bind("mouth", "oh", 0.8),
                    bind("mouth_inside", "oh", 0.8),
                ],
                "overrideBlink": "blend",
                "overrideMouth": "blend",
            },
        }
    )
    idle_sprites = [
        sprite.name for sprite in sprites if "idleLeft" in target_indices.get(sprite.name, {})
    ]
    custom = {
        "breath": {"morphTargetBinds": [bind("torso", "breath")]},
        "idleLeft": {"morphTargetBinds": [bind(name, "idleLeft") for name in idle_sprites]},
        "idleRight": {"morphTargetBinds": [bind(name, "idleRight") for name in idle_sprites]},
    }

    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "mugi_live2d layered VRM builder"},
        "extensionsUsed": ["VRMC_vrm", "KHR_materials_unlit"],
        "extensionsRequired": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {**VRM_META, "thumbnailImage": 0},
                "humanoid": {"humanBones": {name: {"node": node} for name, node in bones.items()}},
                "expressions": {"preset": preset, "custom": custom},
                "lookAt": {
                    "offsetFromHeadBone": [0.0, 0.04, 0.0],
                    "type": "expression",
                    "rangeMapHorizontalInner": {"inputMaxValue": 30.0, "outputScale": 1.0},
                    "rangeMapHorizontalOuter": {"inputMaxValue": 30.0, "outputScale": 1.0},
                    "rangeMapVerticalDown": {"inputMaxValue": 25.0, "outputScale": 1.0},
                    "rangeMapVerticalUp": {"inputMaxValue": 25.0, "outputScale": 1.0},
                },
            }
        },
        "scene": 0,
        "scenes": [{"name": "Mugi Layered VRM", "nodes": [root, *sprite_nodes.values()]}],
        "nodes": nodes,
        "meshes": meshes,
        "skins": [
            {
                "inverseBindMatrices": inverse_bind_accessor,
                "joints": [bones[name] for name in joint_names],
                "skeleton": bones["hips"],
            }
        ],
        "materials": materials,
        "textures": textures,
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "images": images,
        "accessors": accessors,
        "bufferViews": binary.buffer_views,
        "buffers": [{"byteLength": len(binary.data)}],
    }
    json_data = _align4(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode(), b" "
    )
    bin_data = _align4(bytes(binary.data))
    total_length = 12 + 8 + len(json_data) + 8 + len(bin_data)
    glb = (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(json_data), b"JSON")
        + json_data
        + struct.pack("<I4s", len(bin_data), b"BIN\x00")
        + bin_data
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(glb)
    return {
        "output": str(output),
        "bytes": len(glb),
        "layers": len(sprites),
        "meshes": len(meshes),
        "expressions": {"preset": len(preset), "custom": len(custom)},
    }
