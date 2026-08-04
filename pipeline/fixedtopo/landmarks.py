"""Measure where a character actually is, so it can be mapped onto the contract.

Normalising by scaling the whole canvas is not enough: the master rig fixes the
face, eye and mouth boxes, so the input has to be measured at those same
features and then fitted onto them. Every measurement below is a deterministic
function of the pixels and the settings — no sampling, no iteration limits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from pipeline.fixedtopo import imaging
from pipeline.fixedtopo.imaging import Box, Mask
from pipeline.fixedtopo.palette import ColourIndex, Palette

Point = tuple[float, float]


class LandmarkError(RuntimeError):
    """Raised when the input does not expose the features the contract needs."""


@dataclass(frozen=True, slots=True)
class DetectSettings:
    """Thresholds that steer measurement. Candidate presets vary these."""

    alpha_threshold: int = 8
    #: Palette slack applied before classification, as (hue, saturation, value).
    palette_slack: tuple[float, float, float] = (0.0, 0.0, 0.0)
    #: Radius used to close eye/brow/mouth holes when solidifying the face.
    face_close_radius: float = 9.0
    #: Rows searched for the neck, as fractions of the subject height.
    neck_band: tuple[float, float] = (0.05, 0.45)
    #: Rows below the neck still searched for the chin, as a head-height fraction.
    chin_search_span: float = 0.18
    #: Rows averaged before reading a width profile, to ignore anti-aliasing.
    profile_smoothing: int = 5
    #: How close to the narrowest row below the cheeks still counts as the jaw.
    jaw_tolerance: float = 0.05
    #: Ignore head columns thinner than this fraction when finding the crown.
    crown_width_ratio: float = 0.14
    #: Smallest accepted eye cluster, as a fraction of the face bounding box area.
    eye_min_area_ratio: float = 0.0008
    #: Radius that joins iris fragments split by highlights.
    eye_bridge_radius: float = 3.0
    #: Vertical search window for eyes, as fractions of the face box height
    #: measured from its top. Negative values reach up behind the fringe.
    eye_band: tuple[float, float] = (-0.12, 0.78)
    #: Vertical search window for the mouth, between the eye line and the chin.
    mouth_band: tuple[float, float] = (0.05, 0.85)
    #: Horizontal half-width of the mouth search window, as a face-width fraction.
    mouth_half_width: float = 0.26
    #: Pixels darker than this and outside the skin family form the mouth line.
    mouth_value_max: float = 0.85
    #: Radius that joins the broken strokes of a thin closed-mouth line.
    mouth_bridge_radius: float = 8.0
    #: Rows of slack when deciding that two strokes belong to the same mouth.
    mouth_row_slack: int = 6
    #: Smallest accepted mouth cluster in pixels.
    mouth_min_area: int = 24


@dataclass(frozen=True, slots=True)
class Landmarks:
    """Measured feature geometry in the source image's own pixel space."""

    canvas: tuple[int, int]
    subject: Box
    head: Box
    head_core: Box
    face: Box
    eye_left: Point
    eye_right: Point
    eye_left_box: Box
    eye_right_box: Box
    mouth: Point
    mouth_box: Box
    chin: Point
    crown: Point
    quality: dict[str, float] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serialisable view rounded to stable precision."""
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, tuple) and value and isinstance(value[0], float):
                data[key] = [round(item, 3) for item in value]
            elif isinstance(value, tuple):
                data[key] = list(value)
        data["quality"] = {key: round(value, 4) for key, value in self.quality.items()}
        return data

    @property
    def eye_span(self) -> float:
        """Return the horizontal distance between the two eye centres."""
        return abs(self.eye_right[0] - self.eye_left[0])

    @property
    def face_height(self) -> float:
        """Return the measured face height in pixels."""
        return float(self.face[3] - self.face[1])


@dataclass(frozen=True, slots=True)
class Regions:
    """Intermediate masks kept so the splitter does not classify twice."""

    index: ColourIndex
    subject: Mask
    skin: Mask
    hair: Mask
    head: Mask
    face: Mask
    eye_left: Mask
    eye_right: Mask
    mouth: Mask


def detect(
    rgba: np.ndarray, palette: Palette, settings: DetectSettings | None = None
) -> tuple[Landmarks, Regions]:
    """Measure the character's feature geometry and return the masks behind it."""
    settings = settings or DetectSettings()
    index = ColourIndex(rgba, palette.widened(*settings.palette_slack), settings.alpha_threshold)
    height, width = index.shape

    subject = imaging.largest_component(imaging.fill_holes(index.alpha))
    subject_box = imaging.bbox(subject)
    if subject_box is None:
        raise LandmarkError("input has no opaque subject")

    head, head_box, neck_y = _head_from_silhouette(subject, subject_box, settings)
    search = _band(index.shape, head_box, settings.chin_search_span)

    hair = imaging.remove_small(imaging.close(index.family("hair") & subject, 5.0), 64)
    if not (hair & head).any():
        raise LandmarkError("no hair-coloured region found on the head; check the palette")

    skin = index.family("skin") & subject
    face, chin_y = _face_from_skin(skin, search, settings)
    face_box = imaging.bbox(face)
    if face_box is None:
        raise LandmarkError("no skin region found inside the head box; check the palette")

    crown_y, head_core = _crown(head, head_box, settings)

    eye_left, eye_right = _eyes(index, face_box, settings)
    mouth = _mouth(index, face_box, chin_y, eye_left, eye_right, settings)

    left_box, right_box, mouth_box = (
        imaging.bbox(eye_left),
        imaging.bbox(eye_right),
        imaging.bbox(mouth),
    )
    if left_box is None or right_box is None:
        raise LandmarkError("could not find two eye clusters inside the face box")
    if mouth_box is None:
        raise LandmarkError("could not find a mouth cluster below the eye line")

    left_centre = imaging.centroid(eye_left)
    right_centre = imaging.centroid(eye_right)
    mouth_centre = imaging.centroid(mouth)
    assert left_centre is not None and right_centre is not None and mouth_centre is not None

    chin_x = _chin_x(face, chin_y)
    landmarks = Landmarks(
        canvas=(width, height),
        subject=subject_box,
        head=head_box,
        head_core=head_core,
        face=face_box,
        eye_left=left_centre,
        eye_right=right_centre,
        eye_left_box=left_box,
        eye_right_box=right_box,
        mouth=mouth_centre,
        mouth_box=mouth_box,
        chin=(chin_x, float(chin_y)),
        crown=((head_box[0] + head_box[2]) / 2.0, float(crown_y)),
        quality={
            "eye_area_ratio": float(eye_left.sum() + eye_right.sum()) / max(1.0, float(face.sum())),
            "eye_balance": float(min(eye_left.sum(), eye_right.sum()))
            / max(1.0, float(max(eye_left.sum(), eye_right.sum()))),
            "mouth_pixels": float(mouth.sum()),
            "face_pixels": float(face.sum()),
            "hair_pixels": float(hair.sum()),
        },
    )
    regions = Regions(
        index=index,
        subject=subject,
        skin=skin,
        hair=hair,
        head=head,
        face=face,
        eye_left=eye_left,
        eye_right=eye_right,
        mouth=mouth,
    )
    return landmarks, regions


def _head_from_silhouette(
    subject: Mask, subject_box: Box, settings: DetectSettings
) -> tuple[Mask, Box, int]:
    """Cut the head off the silhouette at the neck, independently of colour.

    Character art narrows sharply at the neck, so the strongest narrowing below
    the crown separates head from torso without trusting any palette. Doing this
    first keeps cardigan cream, which shares skin's hue and value, out of the
    face search.
    """
    x0, y0, x1, y1 = subject_box
    widths = subject[y0:y1, x0:x1].sum(axis=1).astype(np.float64)
    height = widths.size
    top = max(1, int(round(height * settings.neck_band[0])))
    bottom = min(height, max(top + 1, int(round(height * settings.neck_band[1]))))
    crown_run = np.maximum.accumulate(np.maximum(widths, 1.0))
    narrowing = widths[top:bottom] / crown_run[top:bottom]
    neck_y = y0 + top + int(np.argmin(narrowing))

    head = subject.copy()
    head[neck_y + 1 :, :] = False
    head = imaging.largest_component(head)
    head_box = imaging.bbox(head)
    if head_box is None:
        raise LandmarkError("could not separate a head from the silhouette")
    return head, head_box, neck_y


def _band(shape: tuple[int, int], box: Box, extra_below: float) -> Mask:
    """Return the head box grown downwards so the jaw stays inside the search."""
    x0, y0, x1, y1 = box
    bottom = y1 + int(round((y1 - y0) * extra_below))
    return imaging.box_mask(shape, (x0, y0, x1, bottom))


def _face_from_skin(skin: Mask, search: Mask, settings: DetectSettings) -> tuple[Mask, int]:
    """Isolate the face from the neck by cutting at the narrowest row below the cheeks.

    Face and neck share one skin region, so a plain connected component reaches
    the chest. The jaw line is the local minimum of the skin row-width profile
    below the widest cheek row, which is stable for front-facing art.
    """
    candidate = imaging.largest_component(imaging.remove_small(skin & search, 256))
    # Eyes and mouth punch holes in the skin. Closing them first keeps the row
    # width profile a measure of the face outline rather than of the features.
    candidate = imaging.fill_holes(imaging.close(candidate, settings.face_close_radius))
    widths = _smooth(candidate.sum(axis=1).astype(np.float64), settings.profile_smoothing)
    if not widths.any():
        raise LandmarkError("skin region inside the head box is empty")

    widest = int(np.argmax(widths))
    tail = widths[widest:]
    positive = np.flatnonzero(tail > 0)
    last = widest + int(positive[-1]) if positive.size else widest
    window = widths[widest : last + 1]
    # Below the cheeks the face keeps narrowing until the jaw, where it either
    # ends or opens into the neck at a steady width. Either way the jaw is the
    # first row that reaches the narrowest width in that stretch.
    floor = float(window.min())
    reached = np.flatnonzero(window <= floor + max(1.0, floor * settings.jaw_tolerance))
    chin_y = widest + int(reached[0])

    face = candidate.copy()
    face[chin_y + 1 :, :] = False
    face = imaging.fill_holes(
        imaging.close(imaging.largest_component(face), settings.face_close_radius)
    )
    return face, chin_y


def _smooth(profile: np.ndarray, window: int) -> np.ndarray:
    """Return a centred moving average, keeping the profile's length."""
    if window <= 1 or profile.size < window:
        return profile
    kernel = np.ones(window, dtype=np.float64) / window
    padded = np.pad(profile, window // 2, mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: profile.size]


def _chin_x(face: Mask, chin_y: int) -> float:
    """Return the horizontal centre of the jaw row."""
    row = face[min(chin_y, face.shape[0] - 1)]
    columns = np.flatnonzero(row)
    if columns.size == 0:
        box = imaging.bbox(face)
        return float((box[0] + box[2]) / 2.0) if box else 0.0
    return float((columns[0] + columns[-1] + 1) / 2.0)


def _crown(head: Mask, head_box: Box, settings: DetectSettings) -> tuple[int, Box]:
    """Return the crown row, ignoring single strands such as an ahoge."""
    widths = head.sum(axis=1)
    threshold = max(1.0, widths.max() * settings.crown_width_ratio)
    rows = np.flatnonzero(widths >= threshold)
    crown_y = int(rows[0]) if rows.size else head_box[1]
    core = head.copy()
    core[:crown_y, :] = False
    core_box = imaging.bbox(core) or head_box
    return crown_y, core_box


def _eyes(index: ColourIndex, face_box: Box, settings: DetectSettings) -> tuple[Mask, Mask]:
    """Return the left and right eye clusters inside the face box.

    Irises anchor the search because their hue is unique on the face; the
    surrounding lashes are then picked up as whatever line art touches an iris.
    Eyebrows are line art too, but they do not touch a lash, so they stay out.
    """
    x0, y0, x1, y1 = face_box
    face_height = y1 - y0
    band = imaging.box_mask(
        index.shape,
        (
            x0,
            y0 + int(round(face_height * settings.eye_band[0])),
            x1,
            y0 + int(round(face_height * settings.eye_band[1])),
        ),
    )
    min_area = max(16, int(round((x1 - x0) * face_height * settings.eye_min_area_ratio)))
    iris = imaging.remove_small(imaging.close(index.family("iris") & band, 3.0), min_area)
    if not iris.any():
        raise LandmarkError("no iris-coloured region found inside the face box")

    # A mid-tone rim separates the iris from the lashes, so the two are bridged
    # before labelling; without it each eye splits into unrelated components.
    core = imaging.close((iris | index.family("line")) & band, settings.eye_bridge_radius)
    labels, _ = imaging.label(core)
    centre = (x0 + x1) / 2.0
    columns = np.arange(index.shape[1], dtype=np.float32)[None, :]

    sides = []
    for side in (iris & (columns < centre), iris & (columns >= centre)):
        touched = np.unique(labels[side])
        cluster = imaging.fill_holes(np.isin(labels, touched[touched > 0]))
        sides.append(imaging.remove_small(cluster, min_area))
    return sides[0], sides[1]


def _mouth(
    index: ColourIndex,
    face_box: Box,
    chin_y: int,
    eye_left: Mask,
    eye_right: Mask,
    settings: DetectSettings,
) -> Mask:
    """Return the mouth cluster between the eye line and the chin.

    Several dark clusters live in that band — jaw shading, collar, stray hair —
    so the cluster nearest the face's vertical axis is taken rather than the
    largest one.
    """
    x0, _, x1, _ = face_box
    eye_box = imaging.bbox(eye_left | eye_right)
    eye_bottom = eye_box[3] if eye_box else face_box[1]
    span = max(1.0, float(chin_y - eye_bottom))
    centre = (x0 + x1) / 2.0
    half = (x1 - x0) * settings.mouth_half_width
    band = imaging.box_mask(
        index.shape,
        (
            int(round(centre - half)),
            eye_bottom + int(round(span * settings.mouth_band[0])),
            int(round(centre + half)),
            eye_bottom + int(round(span * settings.mouth_band[1])),
        ),
    )

    dark = index.alpha & ~index.family("skin") & (index.value <= settings.mouth_value_max)
    cluster = imaging.remove_small(
        imaging.close(dark & band, settings.mouth_bridge_radius), settings.mouth_min_area
    )
    labels, sizes = imaging.label(cluster)
    if sizes.size == 0:
        return cluster

    spans = [imaging.bbox(labels == item + 1) for item in range(sizes.size)]
    offsets = [abs((span[0] + span[2]) / 2.0 - centre) for span in spans]
    anchor = spans[int(np.argmin(offsets))]
    # A closed smile is drawn as two separate strokes on the same rows, so every
    # stroke sharing the anchor's rows is kept and anything above, such as the
    # nose, is dropped.
    keep = [
        item + 1
        for item, span in enumerate(spans)
        if span[1] < anchor[3] + settings.mouth_row_slack
        and span[3] > anchor[1] - settings.mouth_row_slack
    ]
    return np.isin(labels, keep)
