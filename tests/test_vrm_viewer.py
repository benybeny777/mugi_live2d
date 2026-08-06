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
