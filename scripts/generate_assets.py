"""Regenerate the simple paw placeholders using Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    for filename, background in (
        ("logo.png", "#EAF3FF"),
        ("placeholder_product.png", "#FFFFFF"),
    ):
        image = Image.new("RGB", (256, 256), background)
        draw = ImageDraw.Draw(image)
        for bounds in (
            (77, 119, 179, 208),
            (36, 85, 85, 144),
            (78, 39, 124, 106),
            (135, 39, 181, 106),
            (180, 85, 229, 144),
        ):
            draw.ellipse(bounds, fill="#2F80ED")
        image.save(assets / filename)


if __name__ == "__main__":
    main()
