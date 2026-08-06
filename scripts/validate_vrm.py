from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

REQUIRED_BONES = {
    "hips",
    "spine",
    "head",
    "leftUpperLeg",
    "leftLowerLeg",
    "leftFoot",
    "rightUpperLeg",
    "rightLowerLeg",
    "rightFoot",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
}
REQUIRED_EXPRESSIONS = {
    "happy",
    "angry",
    "sad",
    "relaxed",
    "surprised",
    "aa",
    "ih",
    "ou",
    "ee",
    "oh",
    "blink",
    "blinkLeft",
    "blinkRight",
    "lookLeft",
    "lookRight",
    "lookUp",
    "lookDown",
}
EXPECTED_PARENTS = {
    "spine": "hips",
    "head": "spine",
    "leftUpperLeg": "hips",
    "leftLowerLeg": "leftUpperLeg",
    "leftFoot": "leftLowerLeg",
    "rightUpperLeg": "hips",
    "rightLowerLeg": "rightUpperLeg",
    "rightFoot": "rightLowerLeg",
    "leftUpperArm": "spine",
    "leftLowerArm": "leftUpperArm",
    "leftHand": "leftLowerArm",
    "rightUpperArm": "spine",
    "rightLowerArm": "rightUpperArm",
    "rightHand": "rightLowerArm",
}


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("file is too short to be a GLB")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != b"glTF":
        raise ValueError("GLB magic is not glTF")
    if version != 2:
        raise ValueError(f"GLB version must be 2, got {version}")
    if declared_length != len(data):
        raise ValueError(f"GLB length mismatch: header={declared_length}, actual={len(data)}")
    offset = 12
    chunks: dict[bytes, bytes] = {}
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated GLB chunk header")
        length, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        end = offset + length
        if end > len(data):
            raise ValueError("truncated GLB chunk")
        chunks[chunk_type] = data[offset:end]
        offset = end
    if b"JSON" not in chunks or b"BIN\x00" not in chunks:
        raise ValueError("GLB must contain JSON and BIN chunks")
    document = json.loads(chunks[b"JSON"].decode("utf-8"))
    return document, chunks[b"BIN\x00"]


def _descendants(nodes: list[dict[str, Any]], root: int) -> set[int]:
    found: set[int] = set()
    pending = list(nodes[root].get("children", []))
    while pending:
        node = pending.pop()
        if node in found:
            continue
        found.add(node)
        pending.extend(nodes[node].get("children", []))
    return found


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        document, binary = read_glb(path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]

    if document.get("asset", {}).get("version") != "2.0":
        errors.append("asset.version must be 2.0")
    if "VRMC_vrm" not in document.get("extensionsRequired", []):
        errors.append("VRMC_vrm must be listed in extensionsRequired")
    vrm = document.get("extensions", {}).get("VRMC_vrm", {})
    if vrm.get("specVersion") != "1.0":
        errors.append("VRMC_vrm.specVersion must be 1.0")
    meta = vrm.get("meta", {})
    for field in ("name", "authors", "licenseUrl"):
        if not meta.get(field):
            errors.append(f"VRMC_vrm.meta.{field} is required")

    nodes = document.get("nodes", [])
    human_bones = vrm.get("humanoid", {}).get("humanBones", {})
    missing = sorted(REQUIRED_BONES - human_bones.keys())
    if missing:
        errors.append("missing required humanoid bones: " + ", ".join(missing))
    indices: dict[str, int] = {}
    for name, bone in human_bones.items():
        node = bone.get("node")
        if not isinstance(node, int) or not 0 <= node < len(nodes):
            errors.append(f"humanoid bone {name} has an invalid node")
        else:
            indices[name] = node
    if len(set(indices.values())) != len(indices):
        errors.append("humanoid bone nodes must be unique")
    for child, parent in EXPECTED_PARENTS.items():
        if child in indices and parent in indices:
            if indices[child] not in _descendants(nodes, indices[parent]):
                errors.append(f"{child} must descend from {parent}")

    spring_bone = document.get("extensions", {}).get("VRMC_springBone")
    if spring_bone is not None:
        if spring_bone.get("specVersion") != "1.0":
            errors.append("VRMC_springBone.specVersion must be 1.0")
        spring_joint_nodes: set[int] = set()
        for spring_index, spring in enumerate(spring_bone.get("springs", [])):
            joints = spring.get("joints", [])
            if len(joints) < 2:
                errors.append(f"spring {spring_index} must contain at least two joints")
            for joint_index, joint in enumerate(joints):
                node = joint.get("node")
                if not isinstance(node, int) or not 0 <= node < len(nodes):
                    errors.append(f"spring {spring_index} joint {joint_index} has an invalid node")
                    continue
                if node in spring_joint_nodes:
                    errors.append(f"spring joint node {node} is used by multiple spring chains")
                spring_joint_nodes.add(node)
                if joint_index + 1 < len(joints):
                    child_node = joints[joint_index + 1].get("node")
                    if isinstance(child_node, int) and child_node not in _descendants(nodes, node):
                        errors.append(
                            f"spring {spring_index} joints must follow the node hierarchy"
                        )
                drag_force = joint.get("dragForce")
                if drag_force is not None and not 0.0 <= drag_force <= 1.0:
                    errors.append(
                        f"spring {spring_index} joint {joint_index} dragForce is out of range"
                    )
                for nonnegative in ("hitRadius", "stiffness", "gravityPower"):
                    value = joint.get(nonnegative)
                    if value is not None and value < 0.0:
                        errors.append(
                            f"spring {spring_index} joint {joint_index} {nonnegative} is negative"
                        )

    buffers = document.get("buffers", [])
    if len(buffers) != 1 or buffers[0].get("byteLength", -1) > len(binary):
        errors.append("embedded BIN buffer is missing or shorter than declared")
    views = document.get("bufferViews", [])
    for image in document.get("images", []):
        view_index = image.get("bufferView")
        if image.get("mimeType") not in {"image/png", "image/jpeg"}:
            errors.append("embedded images must be PNG or JPEG")
        if not isinstance(view_index, int) or not 0 <= view_index < len(views):
            errors.append("image bufferView is invalid")
            continue
        view = views[view_index]
        end = view.get("byteOffset", 0) + view.get("byteLength", 0)
        if end > len(binary):
            errors.append("image bufferView exceeds BIN chunk")

    primitives = [
        primitive for mesh in document.get("meshes", []) for primitive in mesh.get("primitives", [])
    ]
    if not primitives:
        errors.append("model has no mesh primitives")
    required_attributes = {"POSITION", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"}
    if primitives and not any(
        required_attributes <= primitive.get("attributes", {}).keys()
        for primitive in primitives
    ):
        errors.append("no skinned textured card primitive was found")
    if not document.get("skins"):
        errors.append("model has no skin")

    preset = vrm.get("expressions", {}).get("preset", {})
    missing_expressions = sorted(REQUIRED_EXPRESSIONS - preset.keys())
    if missing_expressions:
        errors.append("missing required expressions: " + ", ".join(missing_expressions))
    custom = vrm.get("expressions", {}).get("custom", {})
    for name in ("breath", "idleLeft", "idleRight"):
        if name not in custom:
            errors.append(f"custom {name} expression is missing")
    meshes = document.get("meshes", [])
    node_target_counts: dict[int, int] = {}
    for node_index, node in enumerate(nodes):
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int) and 0 <= mesh_index < len(meshes):
            mesh_primitives = meshes[mesh_index].get("primitives", [])
            if mesh_primitives:
                node_target_counts[node_index] = len(mesh_primitives[0].get("targets", []))
    for expression_name, expression in {**preset, **custom}.items():
        for binding in expression.get("morphTargetBinds", []):
            node = binding.get("node")
            target_index = binding.get("index")
            target_count = node_target_counts.get(node, 0)
            if not isinstance(node, int) or node not in node_target_counts:
                errors.append(f"expression {expression_name} has an invalid mesh node")
            elif not isinstance(target_index, int) or not 0 <= target_index < target_count:
                errors.append(f"expression {expression_name} has an invalid morph target index")
            weight = binding.get("weight")
            if not isinstance(weight, int | float) or not 0.0 <= weight <= 1.0:
                errors.append(
                    f"expression {expression_name} morph target weight must be between 0 and 1"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Mugi VRM 1.0 deliverable")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"VRM validation passed: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
