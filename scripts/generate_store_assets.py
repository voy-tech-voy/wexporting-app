"""
Generate all required Microsoft Store / MSIX visual assets
from a single high-resolution source PNG (1240x1240).

Output folder: <project_root>/Assets/
Manifest must reference: Assets\SquareXXXLogo.scale-YYY.png etc.
"""

from pathlib import Path
from PIL import Image

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "client" / "assets" / "icons" / "app_icon_1240.png"
OUT = ROOT / "Assets"
OUT.mkdir(exist_ok=True)

# ── Asset definitions ─────────────────────────────────────────────────────────
# Format: (base_name, base_width, base_height, [scale_percentages])
SQUARE_ASSETS = [
    ("Square44x44Logo",   44,  44,  [100, 125, 150, 200, 400]),
    ("Square71x71Logo",   71,  71,  [100, 125, 150, 200, 400]),
    ("Square150x150Logo", 150, 150, [100, 125, 150, 200, 400]),
    ("Square310x310Logo", 310, 310, [100, 125, 150, 200, 400]),
    ("StoreLogo",         50,  50,  [100, 125, 150, 200, 400]),
]

WIDE_ASSETS = [
    # Wide tile - keep subject centred with letterbox padding
    ("Wide310x150Logo",   310, 150, [100, 125, 150, 200, 400]),
]

SPLASH_ASSETS = [
    ("SplashScreen",      620, 300, [100, 125, 150, 200, 400]),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def scale_size(base_w, base_h, scale_pct):
    """Return pixel dimensions for a given scale percentage."""
    factor = scale_pct / 100
    return round(base_w * factor), round(base_h * factor)


def fit_onto_canvas(src: Image.Image, canvas_w: int, canvas_h: int) -> Image.Image:
    """Fit src proportionally onto a canvas_w×canvas_h RGBA canvas."""
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    src_copy = src.copy()
    src_copy.thumbnail((canvas_w, canvas_h), Image.LANCZOS)
    offset_x = (canvas_w - src_copy.width) // 2
    offset_y = (canvas_h - src_copy.height) // 2
    canvas.paste(src_copy, (offset_x, offset_y), src_copy if src_copy.mode == "RGBA" else None)
    return canvas


def generate(base_name, base_w, base_h, scales, source_img):
    for scale in scales:
        w, h = scale_size(base_w, base_h, scale)
        img = fit_onto_canvas(source_img, w, h)
        filename = f"{base_name}.scale-{scale}.png"
        path = OUT / filename
        img.save(path, "PNG")
        print(f"  [OK] {filename}  ({w}x{h})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source icon not found: {SOURCE}")

    print(f"Loading source: {SOURCE}")
    src = Image.open(SOURCE).convert("RGBA")
    print(f"Source size: {src.width}x{src.height}\n")

    all_assets = SQUARE_ASSETS + WIDE_ASSETS + SPLASH_ASSETS
    for base_name, base_w, base_h, scales in all_assets:
        print(f"[{base_name}]")
        generate(base_name, base_w, base_h, scales, src)

    print(f"\n[DONE] All assets written to: {OUT}")
    print(f"   Total files: {len(list(OUT.glob('*.png')))}")


if __name__ == "__main__":
    main()
