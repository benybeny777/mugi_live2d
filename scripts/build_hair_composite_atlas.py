"""Place a hair-only PSD composite in a verified-empty atlas rectangle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from scipy import ndimage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--psd", type=Path, required=True)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--rect", default="4096,0,2048,2048")
    parser.add_argument("--padding", type=int, default=8)
    parser.add_argument("--close-radius", type=int, default=0)
    parser.add_argument("--ellipse-underlay", action="store_true")
    args = parser.parse_args()

    left, top, width, height = (int(value) for value in args.rect.split(","))
    psd = PSDImage.open(args.psd)
    canvas = Image.new("RGBA", psd.size, (0, 0, 0, 0))
    face_protect = Image.new("L", psd.size, 0)
    selected = {"髪（後ろ）", "髪（前・横）"}
    found: list[str] = []
    for layer in reversed(list(psd)):
        if layer.name not in selected:
            continue
        rendered = layer.composite()
        if rendered is None:
            raise RuntimeError(f"failed to composite PSD group: {layer.name}")
        canvas.alpha_composite(rendered.convert("RGBA"), (layer.left, layer.top))
        found.append(layer.name)
    if set(found) != selected:
        raise RuntimeError(f"missing hair groups: {sorted(selected - set(found))}")

    protected_groups = {"顔", "身体", "アクセサリー"}
    for group in psd:
        if group.name not in protected_groups:
            continue
        rendered = group.composite()
        if rendered is None:
            raise RuntimeError(f"failed to composite protection group: {group.name}")
        alpha = rendered.convert("RGBA").getchannel("A")
        face_protect.paste(alpha, (group.left, group.top), alpha)

    if args.close_radius > 0 or args.ellipse_underlay:
        pixels = np.asarray(canvas).copy()
        opaque = pixels[:, :, 3] > 8
        distance_to_hair = ndimage.distance_transform_edt(~opaque)
        if args.ellipse_underlay:
            ys, xs = np.nonzero(opaque)
            center_x = (xs.min() + xs.max()) / 2.0
            center_y = (ys.min() + ys.max()) / 2.0
            radius_x = max(1.0, (xs.max() - xs.min()) / 2.0)
            radius_y = max(1.0, (ys.max() - ys.min()) / 2.0)
            yy, xx = np.ogrid[: opaque.shape[0], : opaque.shape[1]]
            ellipse = ((xx - center_x) / radius_x) ** 2 + ((yy - center_y) / radius_y) ** 2 <= 1.0
            closed = ellipse & (distance_to_hair <= max(1, args.close_radius))
            closed |= opaque
        else:
            dilated = distance_to_hair <= args.close_radius
            distance_inside_dilation = ndimage.distance_transform_edt(dilated)
            closed = (distance_inside_dilation > args.close_radius) | opaque
        protected = np.asarray(face_protect) > 8
        protected = ndimage.binary_dilation(protected, iterations=6)
        closed &= ~protected
        closed |= opaque
        added = closed & ~opaque
        nearest = ndimage.distance_transform_edt(
            ~opaque, return_distances=False, return_indices=True
        )
        for channel in range(3):
            source = pixels[:, :, channel]
            source[added] = source[nearest[0][added], nearest[1][added]]
        pixels[:, :, 3][added] = 255
        canvas = Image.fromarray(pixels, "RGBA")

    bbox = canvas.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("hair composite is empty")
    crop = canvas.crop(bbox)
    usable_width = width - args.padding * 2
    usable_height = height - args.padding * 2
    scale = min(usable_width / crop.width, usable_height / crop.height)
    resized_size = (round(crop.width * scale), round(crop.height * scale))
    resized = crop.resize(resized_size, Image.Resampling.LANCZOS)
    paste_x = left + (width - resized.width) // 2
    paste_y = top + (height - resized.height) // 2

    atlas = Image.open(args.atlas).convert("RGBA")
    reserve = atlas.getchannel("A").crop((left, top, left + width, top + height))
    if reserve.getbbox() is not None:
        raise RuntimeError("reserved atlas rectangle is not empty")
    atlas.alpha_composite(resized, (paste_x, paste_y))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(args.output)

    atlas_width, atlas_height = atlas.size
    metadata = {
        "source_bbox": list(bbox),
        "atlas_rect": [paste_x, paste_y, resized.width, resized.height],
        "uv": {
            "left": paste_x / atlas_width,
            "right": (paste_x + resized.width) / atlas_width,
            "top": 1.0 - paste_y / atlas_height,
            "bottom": 1.0 - (paste_y + resized.height) / atlas_height,
        },
        "groups": sorted(found),
        "close_radius": args.close_radius,
        "ellipse_underlay": args.ellipse_underlay,
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
