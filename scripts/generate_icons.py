#!/usr/bin/env python3
"""Generate MenuMind app icons: white fork+knife on brand red (#C0392B).

Writes the icon set into mobile/assets/images/ (main icon, Android adaptive
foreground/background/monochrome, splash, favicon). Drawn at 4x and downscaled
for crisp edges. Re-run anytime to regenerate.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "mobile" / "assets" / "images"
RED = (192, 57, 43, 255)
WHITE = (255, 255, 255, 255)
SS = 4  # supersample factor


def draw_cutlery(size: int, color=WHITE, content_scale: float = 1.0) -> Image.Image:
    """RGBA image with a centered white fork + knife on a transparent ground."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    base = s / 1024.0
    cx_px = s / 2

    # Map logical (1024-grid) coords to pixels, scaled about the centre.
    def P(x: float, y: float) -> tuple[float, float]:
        px = cx_px + (x - 512) * base * content_scale
        py = (s / 2) + (y - 512 - 12) * base * content_scale  # nudge up 12
        return px, py

    def rr(x0, y0, x1, y1, r):
        a = P(x0, y0)
        b = P(x1, y1)
        d.rounded_rectangle([a[0], a[1], b[0], b[1]], radius=r * base * content_scale, fill=color)

    # Fork (centre x=430)
    fcx = 430
    for off in (-54, -18, 18, 54):
        rr(fcx + off - 10, 250, fcx + off + 10, 442, 10)
    rr(fcx - 66, 408, fcx + 66, 470, 18)   # tine connector
    rr(fcx - 28, 450, fcx + 28, 800, 28)   # handle

    # Knife (centre x=620)
    kcx = 620
    rr(kcx - 30, 250, kcx + 30, 800, 30)

    return img.resize((size, size), Image.LANCZOS)


def on_bg(fg: Image.Image, bg, size: int) -> Image.Image:
    base = Image.new("RGBA", (size, size), bg)
    base.alpha_composite(fg)
    return base


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    icon_cut = draw_cutlery(1024, WHITE, content_scale=1.3)
    on_bg(icon_cut, RED, 1024).save(OUT / "icon.png")

    # Android adaptive: foreground stays inside the safe zone (smaller).
    safe_cut = draw_cutlery(1024, WHITE, content_scale=1.0)
    safe_cut.save(OUT / "android-icon-foreground.png")
    safe_cut.save(OUT / "android-icon-monochrome.png")
    Image.new("RGBA", (1024, 1024), RED).save(OUT / "android-icon-background.png")

    draw_cutlery(512, WHITE, content_scale=1.1).save(OUT / "splash-icon.png")
    on_bg(draw_cutlery(256, WHITE, content_scale=1.3), RED, 256).save(OUT / "favicon.png")

    print(f"icons written to {OUT}")


if __name__ == "__main__":
    main()
