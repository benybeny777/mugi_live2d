import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vrm_viewer_uses_local_pinned_runtime() -> None:
    html = (ROOT / "vrm-viewer" / "index.html").read_text(encoding="utf-8")
    setup = (ROOT / "vrm-viewer" / "setup-runtime.ps1").read_text(encoding="utf-8")

    assert "https://" not in html
    assert "three@0.180.0" in setup
    assert "@pixiv/three-vrm@3.5.3" in setup
    assert "../exports/vrm/mugi.vrm" in (ROOT / "vrm-viewer" / "viewer.js").read_text(
        encoding="utf-8"
    )


def test_vrm_viewer_can_open_the_isolated_tpose_experiment() -> None:
    viewer = (ROOT / "vrm-viewer" / "viewer.js").read_text(encoding="utf-8")

    assert 'modelVariant === "tpose"' in viewer
    assert '"../temp/mugi-tpose-experiment.vrm"' in viewer
    assert 'leftUpperArm: modelVariant === "tpose" ? -1.05 : 0' in viewer
    assert 'rightUpperArm: modelVariant === "tpose" ? 1.05 : 0' in viewer


def test_recording_uses_high_density_opaque_background() -> None:
    viewer = (ROOT / "vrm-viewer" / "viewer.js").read_text(encoding="utf-8")

    assert "renderer.setPixelRatio(2)" in viewer
    assert "renderer.setClearColor(0x111827, 1)" in viewer
    assert "renderer.setPixelRatio(defaultPixelRatio)" in viewer
    assert "renderer.setClearColor(0x000000, 0)" in viewer


def test_manual_neutral_keeps_natural_resting_eyelids() -> None:
    viewer = (ROOT / "vrm-viewer" / "viewer.js").read_text(encoding="utf-8")

    assert "const manualNeutralBlink = 0.15" in viewer
    assert '!autoMotion.checked && !emotion.value ? manualNeutralBlink : 0' in viewer


def test_motion_timeline_is_contiguous_and_loopable() -> None:
    timeline = json.loads(
        (ROOT / "vrm-viewer" / "motions" / "mugi-timeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert timeline["version"] == 1
    assert [segment["name"] for segment in timeline["segments"]] == [
        "idle",
        "greet",
        "talk",
    ]
    assert timeline["segments"][0]["start"] == 0.0
    assert timeline["segments"][-1]["end"] == timeline["duration"]
    assert all(
        current["end"] == following["start"]
        for current, following in zip(timeline["segments"], timeline["segments"][1:])
    )
    for keyframes in timeline["tracks"].values():
        assert keyframes[0][0] == 0.0
        assert keyframes[-1][0] == timeline["duration"]
        assert keyframes[0][1] == keyframes[-1][1]
        assert [frame[0] for frame in keyframes] == sorted(frame[0] for frame in keyframes)
