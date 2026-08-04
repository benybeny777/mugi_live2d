"""Checks applied to an image that came back from Photoshop.

The failure this guards against is specific and has already happened once: a
generative fill produced a woven fabric texture across a region that should
have been flat skin. Eyeballing a thumbnail did not catch it quickly, so the
texture and pattern checks here measure it numerically. No check in this module
can mark a result accepted; the best automated verdict is ``review_required``.

Only ``colour_match`` reads the manifest's fill mode; every other check means
the same thing for an edge extension and for an underlay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

from pipeline.fixedtopo import imaging
from pipeline.fixedtopo.imaging import Mask
from pipeline.sandbox import export as exporter
from pipeline.sandbox import manifest as mf
from pipeline.sandbox.export import LOCK_ALPHA

#: Discrete Laplacian used for the high-frequency energy measure.
LAPLACIAN = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float32)

#: Region border ignored by the texture measures, where a hard alpha edge would
#: otherwise read as detail.
INTERIOR_EROSION = 2.0

#: Radius over which colour is averaged before it is compared. Wide enough to
#: survive a hair/skin boundary in the artwork, narrow enough that a fill of
#: the wrong tone still stands out.
COLOUR_BLUR = 6.0

#: Smallest interior area worth running a texture or pattern measure on.
MIN_MEASURE_PIXELS = 64

#: Residual spread below which a region counts as flat. The periodicity measure
#: normalises by its own energy, so without this floor the rounding noise of a
#: perfectly flat fill would be measured as if it were a signal.
MIN_PATTERN_CONTRAST = 0.5

#: Blur radius separating fine detail from shading in the periodicity measure.
RESIDUAL_BLUR = 2.0

#: Lag range searched for a repeat, in pixels. Below the low end everything
#: correlates with itself; above the high end a fill region rarely holds enough
#: repeats to be sure.
MIN_LAG = 3
MAX_LAG = 40

#: Share of the region that must overlap itself for a lag to be read at all.
MIN_LAG_OVERLAP = 0.05


@dataclass(frozen=True, slots=True)
class Check:
    """One named verdict with the numbers behind it."""

    name: str
    ok: bool
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form."""
        return {"name": self.name, "ok": self.ok, "message": self.message, "detail": self.detail}


def luminance(rgb: NDArray[np.uint8]) -> NDArray[np.float32]:
    """Return Rec.601 luma as float in 0-255."""
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return (rgb[..., :3].astype(np.float32) * weights).sum(axis=-1)


def texture_energy(rgb: NDArray[np.uint8], region: Mask) -> float:
    """Return the mean absolute Laplacian of luma inside ``region``.

    Flat base colour lands near zero. Anything with weave, grain, noise or
    brush detail rises quickly, which is what separates an acceptable fill from
    the fabric texture that was generated before.
    """
    if not region.any():
        return 0.0
    energy = np.abs(ndimage.convolve(luminance(rgb), LAPLACIAN, mode="nearest"))
    return float(energy[region].mean())


def _residual(rgb: NDArray[np.uint8], region: Mask) -> NDArray[np.float32]:
    """Return the high-pass luma inside ``region``, blind to what lies outside.

    Dividing a blurred region by a blurred mask keeps the region's own outline
    out of the result, so what remains is the fine detail of the fill and
    nothing else.
    """
    luma = np.where(region, luminance(rgb), 0.0)
    weight = region.astype(np.float32)
    blurred = ndimage.gaussian_filter(luma, RESIDUAL_BLUR)
    coverage = ndimage.gaussian_filter(weight, RESIDUAL_BLUR)
    local = np.where(coverage > 1e-3, blurred / np.maximum(coverage, 1e-3), 0.0)
    return np.where(region, luminance(rgb) - local, 0.0).astype(np.float32)


def periodicity(rgb: NDArray[np.uint8], region: Mask) -> tuple[float, tuple[int, int]]:
    """Return how strongly the detail inside ``region`` repeats, from 0 to 1.

    A weave, knit or halftone repeats at a fixed spacing, so the autocorrelation
    of its high-pass residual stays high at that lag. Brush detail, film grain
    and a shading gradient do not: their autocorrelation collapses within a few
    pixels. The measure is normalised by the residual's own energy, so it
    catches a faint pattern as readily as a strong one.
    """
    box = imaging.bbox(region)
    if box is None:
        return 0.0, (0, 0)
    x0, y0, x1, y1 = box
    inside = region[y0:y1, x0:x1]
    if inside.size < MIN_MEASURE_PIXELS or min(inside.shape) < 2 * MIN_LAG:
        return 0.0, (0, 0)

    detail = _residual(rgb, region)[y0:y1, x0:x1]
    if float(detail[inside].std()) < MIN_PATTERN_CONTRAST:
        return 0.0, (0, 0)

    padded = (2 * inside.shape[0], 2 * inside.shape[1])
    counted = inside.astype(np.float32)
    energy = np.fft.irfft2(np.abs(np.fft.rfft2(detail, s=padded)) ** 2, s=padded)
    overlap = np.fft.irfft2(np.abs(np.fft.rfft2(counted, s=padded)) ** 2, s=padded)
    if energy[0, 0] <= 1e-9:
        return 0.0, (0, 0)

    # Only lags where enough of the region overlaps itself are worth reading.
    trusted = overlap > MIN_LAG_OVERLAP * overlap[0, 0]
    correlation = np.where(trusted, energy / np.maximum(overlap, 1e-6), 0.0)
    correlation = correlation / (energy[0, 0] / overlap[0, 0])

    dy = np.fft.fftfreq(padded[0], 1 / padded[0])[:, None]
    dx = np.fft.fftfreq(padded[1], 1 / padded[1])[None, :]
    radius = dy**2 + dx**2
    lags = trusted & (radius >= MIN_LAG**2) & (radius <= MAX_LAG**2)
    if not lags.any():
        return 0.0, (0, 0)

    index = np.unravel_index(int(np.argmax(np.where(lags, correlation, -1.0))), correlation.shape)
    return float(correlation[index]), (int(dy[index[0], 0]), int(dx[0, index[1]]))


def nearest_colour(rgb: NDArray[np.uint8], solid: Mask) -> NDArray[np.uint8]:
    """Return, for every pixel, the RGB of the closest pixel inside ``solid``.

    An edge extension has no single reference colour. Mugi's face layer carries
    hair-toned shading along its upper edge and flat skin below, so a fill that
    grows that silhouette is only comparable to the artwork it directly
    continues. An underlay is the opposite case and does not come through here.
    """
    _, indices = ndimage.distance_transform_edt(~solid, return_indices=True)
    return rgb[indices[0], indices[1], :3]


def _local_mean(rgb: NDArray[np.uint8], region: Mask, sigma: float) -> NDArray[np.float32]:
    """Return the average colour around each pixel, counting only ``region``."""
    weight = region.astype(np.float32)
    inside = rgb[..., :3].astype(np.float32) * weight[..., None]
    total = ndimage.gaussian_filter(inside, (sigma, sigma, 0))
    coverage = ndimage.gaussian_filter(weight, sigma)
    return total / np.maximum(coverage, 1e-6)[..., None]


def _median_colour(rgb: NDArray[np.uint8], region: Mask) -> list[float]:
    """Return the median RGB of a region, or zeros when it is empty."""
    if not region.any():
        return [0.0, 0.0, 0.0]
    return [float(value) for value in np.median(rgb[region][:, :3], axis=0)]


def _load_rgba(path: Path) -> NDArray[np.uint8]:
    """Read an image, keeping the original mode available for the size check."""
    with Image.open(path) as opened:
        return np.asarray(opened.convert("RGBA"), dtype=np.uint8)


def _check_size(filled: NDArray[np.uint8], manifest: mf.Manifest) -> Check:
    """The returned image must be the same crop that was handed over."""
    width, height = manifest.size
    actual = (int(filled.shape[1]), int(filled.shape[0]))
    ok = actual == (width, height)
    return Check(
        "return_size",
        ok,
        "returned image matches the sandbox crop"
        if ok
        else f"returned {actual[0]}x{actual[1]}, expected {width}x{height}; "
        "the document was resized or cropped in Photoshop",
        {"expected": [width, height], "actual": list(actual)},
    )


def _check_inputs(manifest: mf.Manifest, directory: Path) -> Check:
    """The sandbox inputs must still be the ones the manifest describes."""
    problems = mf.verify_files(manifest, directory)
    return Check(
        "inputs_intact",
        not problems,
        "sandbox inputs match their recorded SHA-256"
        if not problems
        else "; ".join(problems),
        {"problems": problems},
    )


def _check_locked(
    base: NDArray[np.uint8], filled: NDArray[np.uint8], locked: Mask, manifest: mf.Manifest
) -> Check:
    """Nothing under the locked mask may change."""
    total = int(locked.sum())
    if total == 0:
        return Check("locked_untouched", True, "no locked pixels in this sandbox", {"locked": 0})
    delta = np.abs(base.astype(np.int16) - filled.astype(np.int16)).max(axis=-1)
    changed = int((delta[locked] > manifest.tolerance("locked_channel_delta")).sum())
    ratio = changed / total
    ok = ratio <= manifest.tolerance("locked_pixel_ratio")
    return Check(
        "locked_untouched",
        ok,
        f"{changed} of {total} locked pixels changed"
        + ("" if ok else "; existing artwork was repainted"),
        {"locked": total, "changed": changed, "ratio": round(ratio, 6)},
    )


def _check_silhouette(
    base: NDArray[np.uint8], filled: NDArray[np.uint8], editable: Mask, manifest: mf.Manifest
) -> tuple[Check, Mask]:
    """New opaque pixels must stay inside the editable region, and none may be erased."""
    was = base[..., 3] > 0
    now = filled[..., 3] > 0
    added = now & ~was
    spill = int((added & ~editable).sum())
    removed = int((was & ~now).sum())
    limit = manifest.tolerance("spill_pixels")
    ok = spill <= limit and removed <= limit
    return (
        Check(
            "silhouette",
            ok,
            f"{spill} new pixels outside the editable region, {removed} erased"
            + ("" if ok else "; the fill left the region it was given"),
            {"added": int(added.sum()), "spill": spill, "erased": removed, "limit": limit},
        ),
        added & editable,
    )


def _reference_colour(
    base: NDArray[np.uint8], new: Mask, mode: str
) -> tuple[NDArray[np.float32], list[float], str] | None:
    """Return the colour every new pixel is measured against, and where it came from.

    The two fill modes ask different questions of the same artwork.

    ``extend`` grows the silhouette outward, so each new pixel is judged
    against the artwork it touches: a single reference colour per layer would
    call a correct continuation of Mugi's hair-toned face edge a 200 unit
    error.

    ``underlay`` completes a shape *beneath* the artwork, and there the
    silhouette is the wrong thing to look at. Every edge of the face layer is a
    drawn rim, hair-toned and up to 20 px deep, painted on top of the skin. An
    underlay that correctly continues the skin borders that rim everywhere, so
    comparing it with what it borders rejects exactly the fill that is wanted -
    which is what happened on 2026-08-04: median distance 74 against a fill
    whose colour was already the artwork's own [250, 235, 215].
    """
    # ``LOCK_ALPHA`` excludes transparent and anti-aliased pixels from every
    # reference: their stored RGB is not a colour anyone painted.
    reference = base[..., 3] >= LOCK_ALPHA
    if not reference.any():
        return None
    if mode == exporter.UNDERLAY:
        tone = exporter.base_colour(base)
        if tone is None:
            return None
        flat = np.array(tone, dtype=np.float32)
        return np.broadcast_to(flat, base.shape[:2] + (3,)), list(flat), "the layer base colour"

    # Compare local averages, not single pixels. A fill that correctly
    # continues a hair/skin boundary would otherwise show a 100 unit error
    # wherever the nearest artwork pixel sits on the other side of that edge.
    expected = _local_mean(nearest_colour(base, reference), new, COLOUR_BLUR)
    return expected, _median_colour(base, reference), "the artwork they border"


def _check_colour(
    base: NDArray[np.uint8], filled: NDArray[np.uint8], new: Mask, manifest: mf.Manifest
) -> Check:
    """The fill must carry a colour the artwork actually has."""
    if not new.any():
        return Check("colour_match", True, "not enough pixels to compare colour", {})
    against = _reference_colour(base, new, manifest.fill_mode)
    if against is None:
        return Check("colour_match", True, "not enough pixels to compare colour", {})
    expected, art_rgb, described = against

    actual = _local_mean(filled, new, COLOUR_BLUR)
    gap = np.linalg.norm(actual - expected, axis=-1)
    limit = manifest.tolerance("colour_distance")
    ratio_limit = manifest.tolerance("colour_outlier_ratio")
    gaps = gap[new]
    ratio = float((gaps > limit).mean())
    ok = ratio <= ratio_limit
    return Check(
        "colour_match",
        ok,
        f"{ratio:.1%} of filled pixels are more than {limit:.0f} RGB from {described} "
        f"(limit {ratio_limit:.0%})"
        + ("" if ok else f"; the fill does not carry {described}"),
        {
            "mode": manifest.fill_mode,
            "compared_with": described,
            "fill_rgb": [round(v, 2) for v in _median_colour(filled, new)],
            "art_rgb": [round(v, 2) for v in art_rgb],
            "distance_median": round(float(np.median(gaps)), 3),
            "distance_p95": round(float(np.percentile(gaps, 95)), 3),
            "outlier_ratio": round(ratio, 6),
            "limit": limit,
            "ratio_limit": ratio_limit,
        },
    )


def _check_texture(
    base: NDArray[np.uint8], filled: NDArray[np.uint8], new: Mask, manifest: mf.Manifest
) -> Check:
    """The fill must not be more detailed than the artwork around it."""
    interior = imaging.erode(new, INTERIOR_EROSION)
    if int(interior.sum()) < MIN_MEASURE_PIXELS:
        return Check("texture_flatness", True, "filled region too small to measure texture", {})
    reference = imaging.erode(base[..., 3] >= LOCK_ALPHA, INTERIOR_EROSION)

    fill_energy = texture_energy(filled, interior)
    art_energy = texture_energy(base, reference) if reference.any() else 0.0
    ratio = fill_energy / art_energy if art_energy > 1e-3 else float("inf")

    absolute_limit = manifest.tolerance("texture_energy_absolute")
    ratio_limit = manifest.tolerance("texture_energy_ratio")
    ok = fill_energy <= absolute_limit and (art_energy <= 1e-3 or ratio <= ratio_limit)
    return Check(
        "texture_flatness",
        ok,
        f"filled Laplacian energy {fill_energy:.2f} vs artwork {art_energy:.2f}"
        + ("" if ok else "; the fill carries invented detail such as fabric or grain"),
        {
            "fill_energy": round(fill_energy, 4),
            "artwork_energy": round(art_energy, 4),
            "ratio": None if ratio == float("inf") else round(ratio, 4),
            "absolute_limit": absolute_limit,
            "ratio_limit": ratio_limit,
        },
    )


def _check_pattern(filled: NDArray[np.uint8], new: Mask, manifest: mf.Manifest) -> Check:
    """The fill must not repeat: a weave, knit or halftone is a rejection."""
    interior = imaging.erode(new, INTERIOR_EROSION)
    if int(interior.sum()) < MIN_MEASURE_PIXELS:
        return Check("pattern_free", True, "filled region too small to measure a pattern", {})
    repeat, lag = periodicity(filled, interior)
    limit = manifest.tolerance("pattern_periodicity")
    ok = repeat <= limit
    return Check(
        "pattern_free",
        ok,
        f"detail repeats at {repeat:.3f} correlation, {lag[1]}x{lag[0]} px apart (limit {limit})"
        + ("" if ok else "; the fill contains a woven or repeating pattern"),
        {"periodicity": round(repeat, 6), "lag": list(lag), "limit": limit},
    )


def _check_alpha(
    filled: NDArray[np.uint8], new: Mask, manifest: mf.Manifest
) -> Check:
    """New pixels must be solid except at their outer edge."""
    interior = imaging.erode(new, 1.0)
    total = int(interior.sum())
    if total == 0:
        return Check("alpha_solid", True, "no interior pixels to check", {})
    alpha = filled[..., 3]
    soft = int(((alpha[interior] > 0) & (alpha[interior] < LOCK_ALPHA)).sum())
    ratio = soft / total
    limit = manifest.tolerance("soft_alpha_ratio")
    ok = ratio <= limit
    return Check(
        "alpha_solid",
        ok,
        f"{soft} of {total} interior pixels are partly transparent"
        + ("" if ok else "; the fill left a soft or speckled alpha edge"),
        {"interior": total, "soft": soft, "ratio": round(ratio, 6), "limit": limit},
    )


def evaluate(manifest: mf.Manifest, directory: Path, filled_path: Path) -> dict[str, Any]:
    """Run every check and return the report document."""
    base = _load_rgba(manifest.path("base", directory))
    filled = _load_rgba(filled_path)

    checks = [_check_inputs(manifest, directory), _check_size(filled, manifest)]
    if checks[-1].ok:
        editable = _load_rgba(manifest.path("editable", directory))[..., 0] > 127
        locked = _load_rgba(manifest.path("locked", directory))[..., 0] > 127
        silhouette, new = _check_silhouette(base, filled, editable, manifest)
        checks += [
            _check_locked(base, filled, locked, manifest),
            silhouette,
            _check_colour(base, filled, new, manifest),
            _check_texture(base, filled, new, manifest),
            _check_pattern(filled, new, manifest),
            _check_alpha(filled, new, manifest),
        ]

    failed = [check.name for check in checks if not check.ok]
    return {
        "schema": "mugi-live2d/sandbox-qa@1",
        "sandbox": manifest.id,
        "layer": manifest.source["layer"],
        "returned": filled_path.name,
        "returned_sha256": mf.sha256_file(filled_path),
        # A generated image is never accepted by measurement alone. Passing
        # every check only means it is worth a human looking at it.
        "status": "review_required" if not failed else "rejected",
        "failed": failed,
        "checks": [check.to_json() for check in checks],
    }
