from __future__ import annotations

import io
import json
import math
import struct
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

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
    "version": "6.0.0",
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


def _build_spring_skeleton(
    nodes: list[dict[str, Any]],
    bones: dict[str, int],
    bone_world: dict[str, tuple[float, float, float]],
) -> tuple[dict[str, int], dict[str, tuple[float, float, float]]]:
    spring_defs = {
        "backHairRoot": ("BackHairRoot", (0.0, 0.32, 0.0), "head"),
        "backHairMid": ("BackHairMid", (0.0, -0.17, 0.0), "backHairRoot"),
        "backHairTip": ("BackHairTip", (0.0, -0.17, 0.0), "backHairMid"),
        "frontHairRoot": ("FrontHairRoot", (0.0, 0.32, 0.0), "head"),
        "frontHairMid": ("FrontHairMid", (0.0, -0.11, 0.0), "frontHairRoot"),
        "frontHairTip": ("FrontHairTip", (0.0, -0.11, 0.0), "frontHairMid"),
        "accessoryRoot": ("AccessoryRoot", (0.095, 0.26, 0.0), "head"),
        "accessoryTip": ("AccessoryTip", (0.0, -0.14, 0.0), "accessoryRoot"),
    }
    spring_nodes: dict[str, int] = {}
    spring_world: dict[str, tuple[float, float, float]] = {}
    for name, (node_name, translation, parent) in spring_defs.items():
        spring_nodes[name] = _add_node(nodes, node_name, translation)
        parent_node = bones.get(parent, spring_nodes.get(parent))
        if parent_node is None:
            raise ValueError(f"unknown spring bone parent: {parent}")
        nodes[parent_node].setdefault("children", []).append(spring_nodes[name])
        parent_position = bone_world.get(parent, spring_world.get(parent))
        if parent_position is None:
            raise ValueError(f"unknown spring bone parent position: {parent}")
        spring_world[name] = tuple(
            parent_position[index] + translation[index] for index in range(3)
        )
    return spring_nodes, spring_world


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


def _grid_size(sprite_name: str) -> tuple[int, int]:
    if sprite_name in {
        "left_eye_white",
        "right_eye_white",
        "left_iris",
        "right_iris",
        "left_lashes",
        "right_lashes",
    }:
        return (4, 2)
    if sprite_name in {"mouth", "mouth_inside"}:
        return (5, 2)
    if sprite_name == "torso":
        return (4, 8)
    if "arm" in sprite_name:
        return (3, 8)
    if "leg" in sprite_name:
        return (3, 10)
    if sprite_name in {"back_hair", "front_hair"}:
        return (5, 8)
    if sprite_name == "accessory":
        return (2, 3)
    return (1, 1)


def _grid_geometry(
    sprite: LayerSprite, canvas_size: tuple[int, int]
) -> tuple[
    list[tuple[float, float, float]],
    list[tuple[float, float]],
    list[int],
    tuple[int, int],
]:
    corners = _quad(sprite, canvas_size)
    columns, rows = _grid_size(sprite.name)
    left = corners[0][0]
    right = corners[1][0]
    bottom = corners[0][1]
    top = corners[2][1]
    positions: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    for row in range(rows + 1):
        vertical = row / rows
        y = bottom + (top - bottom) * vertical
        for column in range(columns + 1):
            horizontal = column / columns
            x = left + (right - left) * horizontal
            positions.append((x, y, sprite.depth))
            uvs.append((horizontal, 1.0 - vertical))
    indices: list[int] = []
    stride = columns + 1
    for row in range(rows):
        for column in range(columns):
            lower_left = row * stride + column
            lower_right = lower_left + 1
            upper_left = lower_left + stride
            upper_right = upper_left + 1
            indices.extend(
                [lower_left, lower_right, upper_right, lower_left, upper_right, upper_left]
            )
    return positions, uvs, indices, (columns, rows)


def _skin_data(
    sprite: LayerSprite,
    grid: tuple[int, int],
    joint_lookup: dict[str, int],
) -> tuple[list[int], list[float], bool]:
    columns, rows = grid
    spring_pair: tuple[str, str] | None = None
    if sprite.name == "back_hair":
        spring_pair = ("backHairMid", "backHairRoot")
    elif sprite.name == "front_hair":
        spring_pair = ("frontHairMid", "frontHairRoot")
    if spring_pair is not None:
        lower_joint = joint_lookup[spring_pair[0]]
        upper_joint = joint_lookup[spring_pair[1]]
        joints: list[int] = []
        weights: list[float] = []
        for row in range(rows + 1):
            upper_weight = row / rows
            lower_weight = 1.0 - upper_weight
            for _ in range(columns + 1):
                joints.extend(
                    [
                        lower_joint if lower_weight > 0.0 else 0,
                        upper_joint if upper_weight > 0.0 else 0,
                        0,
                        0,
                    ]
                )
                weights.extend([lower_weight, upper_weight, 0.0, 0.0])
        return joints, weights, True
    if sprite.name == "accessory":
        accessory_joint = joint_lookup["accessoryRoot"]
        vertex_count = (columns + 1) * (rows + 1)
        joints = [accessory_joint, 0, 0, 0] * vertex_count
        weights = [1.0, 0.0, 0.0, 0.0] * vertex_count
        return joints, weights, False
    secondary_bone: str | None = None
    if sprite.name == "torso":
        secondary_bone = "chest"
    elif "UpperLeg" in sprite.bone:
        secondary_bone = sprite.bone.replace("UpperLeg", "LowerLeg")
    primary_joint = joint_lookup[sprite.bone]
    secondary_joint = joint_lookup.get(secondary_bone, primary_joint)
    joints: list[int] = []
    weights: list[float] = []
    for row in range(rows + 1):
        vertical = row / rows
        if sprite.name == "torso":
            secondary_weight = max(0.0, (vertical - 0.25) / 0.75) * 0.65
        elif secondary_bone is not None:
            secondary_weight = max(0.0, 1.0 - vertical / 0.72) * 0.85
        else:
            secondary_weight = 0.0
        for _ in range(columns + 1):
            weighted_secondary_joint = secondary_joint if secondary_weight > 0.0 else 0
            joints.extend([primary_joint, weighted_secondary_joint, 0, 0])
            weights.extend([1.0 - secondary_weight, secondary_weight, 0.0, 0.0])
    return joints, weights, secondary_bone is not None


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
    if sprite_name == "screen_right_arm":
        return ["idleLeft", "idleRight", "greet"]
    if sprite_name in {"screen_left_arm", "screen_left_leg", "screen_right_leg"}:
        return ["idleLeft", "idleRight"]
    return []


def _deform_arm_from_shoulder(
    sprite: LayerSprite,
    base: list[tuple[float, float, float]],
    angle_degrees: float,
) -> list[tuple[float, float, float]]:
    """Curve a one-piece arm while keeping its inner shoulder seam fixed."""
    bottom = min(point[1] for point in base)
    top = max(point[1] for point in base)
    span = max(top - bottom, 1e-6)
    inner_x = (
        max(point[0] for point in base)
        if sprite.name == "screen_left_arm"
        else min(point[0] for point in base)
    )
    pivot = (inner_x, top)
    deformed: list[tuple[float, float, float]] = []
    for point in base:
        progress = max(0.0, min(1.0, (top - point[1]) / span))
        eased = progress * progress * (3.0 - 2.0 * progress)
        deformed.append(_rotate(point, pivot, angle_degrees * eased))
    return deformed


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
        bottom = min(point[1] for point in base)
        top = max(point[1] for point in base)
        close_line = bottom + (top - bottom) * 0.38
        return [(x, close_line + (y - center[1]) * 0.05, z) for x, y, z in base]
    if target == "wide":
        return [_scale(point, center, 1.02, 1.09) for point in base]
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
        columns, rows = _grid_size(sprite.name)
        width_scale, height_scale = scales[target]
        source_height = max(point[1] for point in base) - min(point[1] for point in base)
        if sprite.name == "mouth_inside":
            source_height = 1.8 * (sprite.canvas_box[3] - sprite.canvas_box[1]) / 4175
        source_height = max(source_height, 1e-5)
        shaped: list[tuple[float, float, float]] = []
        for index, (x, _, z) in enumerate(base):
            row = index // (columns + 1)
            column = index % (columns + 1)
            horizontal = column / columns * 2.0 - 1.0
            vertical = row / rows * 2.0 - 1.0
            arch = (1.0 - horizontal * horizontal) * source_height
            if target in {"ih", "ee"}:
                curve = 0.06 * arch
            elif target == "ou":
                curve = -0.04 * arch * vertical
            else:
                curve = 0.10 * arch * vertical
            shaped.append(
                (
                    center[0] + (x - center[0]) * width_scale,
                    center[1] + vertical * source_height * height_scale / 2.0 + curve,
                    z,
                )
            )
        return shaped
    if target == "happy":
        left = min(point[0] for point in base)
        right = max(point[0] for point in base)
        half_width = max((right - left) / 2.0, 1e-6)
        return [
            (x, y + 0.008 * abs((x - center[0]) / half_width), z) for x, y, z in base
        ]
    if target == "sad":
        if "lashes" in sprite.name:
            direction = -3.0 if sprite.name.startswith("left") else 3.0
            return [_rotate(point, center, direction) for point in base]
        left = min(point[0] for point in base)
        right = max(point[0] for point in base)
        half_width = max((right - left) / 2.0, 1e-6)
        return [
            (x, y - 0.006 * abs((x - center[0]) / half_width), z) for x, y, z in base
        ]
    if target == "angry":
        direction = 4.0 if sprite.name.startswith("left") else -4.0
        return [_rotate(point, center, direction) for point in base]
    if target == "breath":
        anchor = (center[0], min(point[1] for point in base))
        return [_scale(point, anchor, 1.008, 1.004) for point in base]
    if target == "greet" and sprite.name == "screen_right_arm":
        return _deform_arm_from_shoulder(sprite, base, 6.0)
    if target in {"idleLeft", "idleRight"}:
        direction = 1.0 if target == "idleLeft" else -1.0
        if sprite.name == "torso":
            bottom = min(point[1] for point in base)
            top = max(point[1] for point in base)
            span = max(top - bottom, 1e-6)
            return [(x + direction * 0.006 * (y - bottom) / span, y, z) for x, y, z in base]
        if "arm" in sprite.name:
            angle = direction * 0.35
            if sprite.name.startswith("screen_right"):
                angle *= -1.0
            return _deform_arm_from_shoulder(sprite, base, angle)
        if "leg" in sprite.name:
            angle = direction * 0.35
            if sprite.name.startswith("screen_right"):
                angle *= -1.0
            pivot = bone_world[sprite.bone][:2]
            return [_rotate(point, pivot, angle) for point in base]
    return base


def _flatten(values: list[tuple[float, float, float]]) -> list[float]:
    return [component for point in values for component in point]


def _expression_bind(node: int, index: int, weight: float = 1.0) -> dict[str, Any]:
    return {"node": node, "index": index, "weight": weight}


def _prepare_sprite_texture(image: Image.Image, scale: float) -> Image.Image:
    """Resize transparent art without dark fringes, then restore line clarity."""
    prepared = image.convert("RGBA")
    if scale < 1.0:
        size = (
            max(1, round(prepared.width * scale)),
            max(1, round(prepared.height * scale)),
        )
        prepared = prepared.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")

    red, green, blue, alpha = prepared.split()
    rgb = Image.merge("RGB", (red, green, blue)).filter(
        ImageFilter.UnsharpMask(radius=0.6, percent=75, threshold=3)
    )
    return Image.merge("RGBA", (*rgb.split(), alpha))


def build_layered_vrm_from_sprites(
    canvas_size: tuple[int, int],
    sprites: list[LayerSprite],
    output: Path,
    max_texture_size: int = 4096,
) -> dict[str, Any]:
    """Build a layered VRM from an already reviewed sprite set."""
    binary = BinaryBuilder()
    nodes: list[dict[str, Any]] = []
    root, bones, bone_world = _build_skeleton(nodes)
    spring_nodes, spring_world = _build_spring_skeleton(nodes, bones, bone_world)
    skin_nodes = {**bones, **spring_nodes}
    skin_world = {**bone_world, **spring_world}
    joint_names = list(skin_nodes)
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
        resized = _prepare_sprite_texture(sprite.image, texture_scale)
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

        base, uvs, indices, grid = _grid_geometry(sprite, canvas_size)
        vertex_count = len(base)
        position_values = _flatten(base)
        position_view = binary.add(
            struct.pack(f"<{len(position_values)}f", *position_values), target=34962
        )
        position_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": position_view,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC3",
                "min": [min(point[axis] for point in base) for axis in range(3)],
                "max": [max(point[axis] for point in base) for axis in range(3)],
            }
        )
        normal_values = [0.0, 0.0, 1.0] * vertex_count
        normal_view = binary.add(
            struct.pack(f"<{len(normal_values)}f", *normal_values), target=34962
        )
        normal_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": normal_view,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC3",
            }
        )
        uv_values = [component for point in uvs for component in point]
        uv_view = binary.add(struct.pack(f"<{len(uv_values)}f", *uv_values), target=34962)
        uv_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": uv_view,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC2",
            }
        )
        joint_values, weight_values, has_gradient_weights = _skin_data(
            sprite, grid, joint_lookup
        )
        joint_view = binary.add(bytes(joint_values), target=34962)
        joint_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": joint_view,
                "componentType": 5121,
                "count": vertex_count,
                "type": "VEC4",
            }
        )
        weight_view = binary.add(
            struct.pack(f"<{len(weight_values)}f", *weight_values), target=34962
        )
        weight_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": weight_view,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC4",
            }
        )
        index_view = binary.add(
            struct.pack(f"<{len(indices)}H", *indices), target=34963
        )
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": index_view,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
                "min": [0],
                "max": [vertex_count - 1],
            }
        )

        targets: list[dict[str, int]] = []
        names = _target_names(sprite.name)
        target_indices[sprite.name] = {name: index for index, name in enumerate(names)}
        for target_name in names:
            transformed = _target_vertices(sprite, target_name, base, bone_world)
            offsets = [
                tuple(transformed[index][axis] - base[index][axis] for axis in range(3))
                for index in range(vertex_count)
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
                    "count": vertex_count,
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
        mesh: dict[str, Any] = {
            "name": f"{sprite.name}Mesh",
            "primitives": [primitive],
            "extras": {
                "grid": list(grid),
                "gradientWeights": has_gradient_weights,
            },
        }
        if names:
            mesh["weights"] = [0.0] * len(names)
            mesh["extras"]["targetNames"] = names
        meshes.append(mesh)
        node = _add_node(nodes, sprite.name)
        nodes[node].update({"mesh": mesh_index, "skin": 0})
        sprite_nodes[sprite.name] = node

    inverse_bind_values: list[float] = []
    for name in joint_names:
        x, y, z = skin_world[name]
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

    expressive_names = {
        "left_eye_white", "right_eye_white", "left_iris", "right_iris",
        "left_lashes", "right_lashes", "mouth", "mouth_inside",
    }
    preset: dict[str, Any] = {}
    if expressive_names <= sprite_nodes.keys():
        left_eye_parts = ["right_eye_white", "right_iris", "right_lashes"]
        right_eye_parts = ["left_eye_white", "left_iris", "left_lashes"]
        both_eye_parts = [*left_eye_parts, *right_eye_parts]
        mouth_parts = ["mouth", "mouth_inside"]
        preset = {
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
        preset.update({
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
        })
    else:
        # Structural experiments remain valid VRM files while facial extraction
        # is deliberately deferred; empty presets must not fake expressions.
        for name in (
            "blinkLeft", "blinkRight", "blink", "aa", "ih", "ou", "ee", "oh",
            "happy", "angry", "sad", "relaxed", "surprised",
            "lookLeft", "lookRight", "lookUp", "lookDown",
        ):
            preset[name] = {"morphTargetBinds": []}
    idle_sprites = [
        sprite.name for sprite in sprites if "idleLeft" in target_indices.get(sprite.name, {})
    ]
    custom = {
        "breath": {"morphTargetBinds": [bind("torso", "breath")]},
        "idleLeft": {"morphTargetBinds": [bind(name, "idleLeft") for name in idle_sprites]},
        "idleRight": {"morphTargetBinds": [bind(name, "idleRight") for name in idle_sprites]},
        "greet": {"morphTargetBinds": [bind("screen_right_arm", "greet")]},
    }

    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "mugi_live2d layered VRM builder"},
        "extensionsUsed": ["VRMC_vrm", "VRMC_springBone", "KHR_materials_unlit"],
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
            },
            "VRMC_springBone": {
                "specVersion": "1.0",
                "springs": [
                    {
                        "name": "BackHair",
                        "center": bones["head"],
                        "joints": [
                            {
                                "node": spring_nodes["backHairRoot"],
                                "hitRadius": 0.012,
                                "stiffness": 1.15,
                                "gravityPower": 0.015,
                                "gravityDir": [0.0, -1.0, 0.0],
                                "dragForce": 0.38,
                            },
                            {
                                "node": spring_nodes["backHairMid"],
                                "hitRadius": 0.01,
                                "stiffness": 0.9,
                                "gravityPower": 0.02,
                                "gravityDir": [0.0, -1.0, 0.0],
                                "dragForce": 0.32,
                            },
                            {"node": spring_nodes["backHairTip"]},
                        ],
                    },
                    {
                        "name": "FrontHair",
                        "center": bones["head"],
                        "joints": [
                            {
                                "node": spring_nodes["frontHairRoot"],
                                "hitRadius": 0.008,
                                "stiffness": 1.45,
                                "gravityPower": 0.01,
                                "gravityDir": [0.0, -1.0, 0.0],
                                "dragForce": 0.48,
                            },
                            {
                                "node": spring_nodes["frontHairMid"],
                                "hitRadius": 0.006,
                                "stiffness": 1.2,
                                "gravityPower": 0.012,
                                "gravityDir": [0.0, -1.0, 0.0],
                                "dragForce": 0.42,
                            },
                            {"node": spring_nodes["frontHairTip"]},
                        ],
                    },
                    {
                        "name": "HairAccessory",
                        "center": bones["head"],
                        "joints": [
                            {
                                "node": spring_nodes["accessoryRoot"],
                                "hitRadius": 0.006,
                                "stiffness": 1.7,
                                "gravityPower": 0.008,
                                "gravityDir": [0.0, -1.0, 0.0],
                                "dragForce": 0.52,
                            },
                            {"node": spring_nodes["accessoryTip"]},
                        ],
                    },
                ],
            },
        },
        "scene": 0,
        "scenes": [{"name": "Mugi Layered VRM", "nodes": [root, *sprite_nodes.values()]}],
        "nodes": nodes,
        "meshes": meshes,
        "skins": [
            {
                "inverseBindMatrices": inverse_bind_accessor,
                "joints": [skin_nodes[name] for name in joint_names],
                "skeleton": bones["hips"],
            }
        ],
        "materials": materials,
        "textures": textures,
        "samplers": [{"magFilter": 9729, "minFilter": 9729, "wrapS": 33071, "wrapT": 33071}],
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
        "vertices": sum(
            accessors[mesh["primitives"][0]["attributes"]["POSITION"]]["count"]
            for mesh in meshes
        ),
        "deformableMeshes": sum(mesh["extras"]["grid"] != [1, 1] for mesh in meshes),
        "gradientWeightedMeshes": sum(
            mesh["extras"]["gradientWeights"] for mesh in meshes
        ),
        "facialGridMeshes": sum(
            mesh["name"]
            in {
                "left_eye_whiteMesh",
                "right_eye_whiteMesh",
                "left_irisMesh",
                "right_irisMesh",
                "left_lashesMesh",
                "right_lashesMesh",
                "mouthMesh",
                "mouth_insideMesh",
            }
            and mesh["extras"]["grid"] != [1, 1]
            for mesh in meshes
        ),
        "springBones": len(document["extensions"]["VRMC_springBone"]["springs"]),
        "expressions": {"preset": len(preset), "custom": len(custom)},
    }


def build_layered_vrm(psd_path: Path, output: Path, max_texture_size: int = 4096) -> dict[str, Any]:
    """Extract the canonical PSD sprites and build the layered VRM."""
    canvas_size, sprites = extract_layer_sprites(psd_path)
    return build_layered_vrm_from_sprites(canvas_size, sprites, output, max_texture_size)
