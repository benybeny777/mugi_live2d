from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from pipeline.vrm_layers import LayerSprite

REFERENCE_CANVAS = (2920, 4096)
HEAD_BOTTOM_RATIO = 0.235
UPPER_TORSO_RATIO = 0.150
ARM_BOTTOM_RATIO = 0.345
TORSO_LEFT_RATIO = 0.34
TORSO_RIGHT_RATIO = 0.66
LEG_TOP_RATIO = 0.535


def _foreground(image: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """Recover prematte-free RGB and alpha from the plain white background."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    contrast = 255 - rgb.min(axis=2)
    candidates = ndimage.binary_opening(contrast >= 16, iterations=1)
    labels, count = ndimage.label(candidates)
    if count == 0:
        raise ValueError("T-pose source contains no character silhouette")
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    character = labels == int(sizes.argmax())
    character = ndimage.binary_fill_holes(character)
    fringe = ndimage.binary_dilation(character, iterations=2)
    edge = np.clip(contrast * 18, 0, 255).astype(np.uint8)
    boundary = character & ~ndimage.binary_erosion(character, iterations=2)
    alpha = np.where(character, 255, np.where(fringe, edge, 0)).astype(np.uint8)
    alpha[boundary] = np.maximum(edge[boundary], 24)
    fraction = alpha.astype(np.float32)[:, :, None] / 255.0
    recovered = np.where(
        fraction > 0,
        (rgb.astype(np.float32) - 255.0 * (1.0 - fraction)) / np.maximum(fraction, 1 / 255),
        0.0,
    )
    return np.clip(recovered, 0, 255).astype(np.uint8), alpha


def _masked(rgb: np.ndarray, alpha: np.ndarray, selector: np.ndarray) -> Image.Image:
    selected_solid = selector & (alpha >= 24)
    labels, count = ndimage.label(selected_solid)
    if count:
        sizes = np.bincount(labels.ravel())
        sizes[0] = 0
        main = labels == int(sizes.argmax())
        selector = selector & ndimage.binary_dilation(main, iterations=2)
    result = Image.fromarray(rgb, mode="RGB").convert("RGBA")
    result.putalpha(Image.fromarray(np.where(selector, alpha, 0).astype(np.uint8), mode="L"))
    return result


def _sprite(name: str, bone: str, depth: float, image: Image.Image) -> LayerSprite:
    box = image.getchannel("A").getbbox()
    if box is None:
        raise ValueError(f"T-pose layer {name} has no visible pixels")
    padding = 8
    padded_box = (
        max(0, box[0] - padding),
        max(0, box[1] - padding),
        min(image.width, box[2] + padding),
        min(image.height, box[3] + padding),
    )
    return LayerSprite(name, bone, depth, image.crop(padded_box), padded_box)


def extract_tpose_sprites(source_path: Path) -> tuple[tuple[int, int], list[LayerSprite]]:
    """Split every structural sprite from one Photoshop T-pose source."""
    source = Image.open(source_path).convert("RGBA")
    width, height = source.size
    if source.size != REFERENCE_CANVAS:
        raise ValueError(
            "T-pose source must be "
            f"{REFERENCE_CANVAS[0]}x{REFERENCE_CANVAS[1]}, got {width}x{height}"
        )
    recovered_rgb, alpha = _foreground(source)
    yy, xx = np.indices((height, width))
    head_bottom = round(height * HEAD_BOTTOM_RATIO)
    upper_torso = round(height * UPPER_TORSO_RATIO)
    arm_bottom = round(height * ARM_BOTTOM_RATIO)
    torso_left = round(width * TORSO_LEFT_RATIO)
    torso_right = round(width * TORSO_RIGHT_RATIO)
    leg_top = round(height * LEG_TOP_RATIO)
    center = width // 2

    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    head_core_bottom = round(height * 0.205)
    hair_or_outline = (rgb[:, :, 0] < 165) & (rgb[:, :, 1] < 150) & (rgb[:, :, 2] < 135)
    head_center = np.abs(xx - center) <= width * 0.13
    head = (yy < head_core_bottom) | ((yy < head_bottom) & (hair_or_outline | head_center))
    upper_garment = (
        (yy >= upper_torso)
        & (yy < head_bottom)
        & (alpha >= 24)
        & (rgb[:, :, 0] >= 150)
        & (rgb[:, :, 1] >= 125)
        & (rgb[:, :, 2] >= 85)
    )
    lower_body = yy >= head_bottom
    arm_join_progress = np.clip((yy - upper_torso) / max(head_bottom - upper_torso, 1), 0.0, 1.0)
    left_arm_edge = width * (0.325 + 0.045 * arm_join_progress)
    right_arm_edge = width - left_arm_edge
    left_arm = (upper_garment | lower_body) & (yy < arm_bottom) & (xx <= left_arm_edge)
    right_arm = (upper_garment | lower_body) & (yy < arm_bottom) & (xx >= right_arm_edge)
    # Put the ellipse apex on the source shoulder line. If its apex starts
    # above that line, the original T-pose's horizontal contour stays visible
    # and makes the lowered shoulder look square.
    shoulder_center_y = height * 0.245
    shoulder_radius_x = width * 0.040
    shoulder_radius_y = height * 0.060
    left_shoulder_underlay = (
        ((xx - width * 0.390) / shoulder_radius_x) ** 2
        + ((yy - shoulder_center_y) / shoulder_radius_y) ** 2
        <= 1.0
    ) & (upper_garment | lower_body)
    right_shoulder_underlay = (
        ((xx - width * 0.610) / shoulder_radius_x) ** 2
        + ((yy - shoulder_center_y) / shoulder_radius_y) ** 2
        <= 1.0
    ) & (upper_garment | lower_body)
    shoulder_sample_offset = round(height * 0.020)
    shoulder_rgb = np.roll(recovered_rgb, -shoulder_sample_offset, axis=0)
    shoulder_alpha = np.roll(alpha, -shoulder_sample_offset, axis=0)
    shoulder_alpha[-shoulder_sample_offset:] = 0
    shoulder_progress = np.clip((yy - upper_torso) / max(arm_bottom - upper_torso, 1), 0.0, 1.0)
    torso_half_width = width * (0.040 + 0.095 * shoulder_progress)
    torso = (
        (upper_garment | lower_body)
        & (yy < leg_top)
        & (xx >= np.maximum(torso_left, center - torso_half_width))
        & (xx <= np.minimum(torso_right, center + torso_half_width))
    )
    left_leg = (yy >= leg_top) & (xx < center)
    right_leg = (yy >= leg_top) & (xx >= center)

    sprites = [
        _sprite(
            "screen_left_leg", "rightUpperLeg", -0.030, _masked(recovered_rgb, alpha, left_leg)
        ),
        _sprite(
            "screen_right_leg", "leftUpperLeg", -0.030, _masked(recovered_rgb, alpha, right_leg)
        ),
        _sprite(
            "screen_left_shoulder_underlay",
            "spine",
            -0.025,
            _masked(shoulder_rgb, shoulder_alpha, left_shoulder_underlay),
        ),
        _sprite(
            "screen_right_shoulder_underlay",
            "spine",
            -0.025,
            _masked(shoulder_rgb, shoulder_alpha, right_shoulder_underlay),
        ),
        _sprite(
            "screen_left_arm", "rightUpperArm", -0.020, _masked(recovered_rgb, alpha, left_arm)
        ),
        _sprite(
            "screen_right_arm", "leftUpperArm", -0.020, _masked(recovered_rgb, alpha, right_arm)
        ),
        _sprite("torso", "spine", -0.010, _masked(recovered_rgb, alpha, torso)),
        _sprite("head", "head", 0.010, _masked(recovered_rgb, alpha, head)),
    ]
    return source.size, sprites
