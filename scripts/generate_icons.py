#!/usr/bin/env python3
"""
Generate OpenSAK icon files for Linux, Windows, and macOS
from the source SVG.

Requirements:
    pip install Pillow cairosvg
    (cairosvg requires libcairo — on Ubuntu: sudo apt install libcairo2-dev)

Usage:
    python generate_icons.py

Output:
    icons/
    ├── opensak.png        (256x256 — Linux desktop)
    ├── opensak_512.png    (512x512 — Linux stores / high-DPI)
    ├── opensak_64.png     (64x64)
    ├── opensak_32.png     (32x32)
    ├── opensak_16.png     (16x16)
    ├── opensak.ico        (Windows — multi-size: 16/32/48/64/128/256)
    └── opensak.icns       (macOS — built from pngs via iconutil or Pillow)
"""

import os
import struct
import sys
import zlib
from pathlib import Path

try:
    from PIL import Image
    import io
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

SVG_SOURCE = Path(__file__).parent / "opensak.svg"
OUTPUT_DIR = Path(__file__).parent / "icons"


def svg_to_pil(svg_path: Path, size: int) -> Image.Image:
    """Convert SVG to PIL Image at given size."""
    try:
        import cairosvg
        png_bytes = cairosvg.svg2png(
            url=str(svg_path),
            output_width=size,
            output_height=size,
        )
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except ImportError:
        pass

    # Fallback: try inkscape CLI
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["inkscape", "--export-type=png",
             f"--export-width={size}", f"--export-height={size}",
             f"--export-filename={tmp_path}", str(svg_path)],
            capture_output=True, timeout=30
        )
        if result.returncode == 0:
            img = Image.open(tmp_path).convert("RGBA")
            os.unlink(tmp_path)
            return img
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Fallback: use rsvg-convert
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size),
             "-o", tmp_path, str(svg_path)],
            capture_output=True, timeout=30
        )
        if result.returncode == 0:
            img = Image.open(tmp_path).convert("RGBA")
            os.unlink(tmp_path)
            return img
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    raise RuntimeError(
        "No SVG renderer found!\n"
        "Install one of:\n"
        "  pip install cairosvg\n"
        "  sudo apt install inkscape\n"
        "  sudo apt install librsvg2-bin"
    )


def generate_png_sizes(svg_path: Path, output_dir: Path) -> dict[int, Image.Image]:
    """Generate PNG files at all required sizes. Returns dict of size->Image."""
    sizes = [16, 32, 48, 64, 128, 256, 512, 1024]
    images = {}

    print(f"Converting SVG → PNG at {len(sizes)} sizes...")
    for size in sizes:
        print(f"  Rendering {size}×{size}...", end=" ", flush=True)
        img = svg_to_pil(svg_path, size)
        images[size] = img

        if size in (16, 32, 64, 256, 512):
            name = "opensak.png" if size == 256 else f"opensak_{size}.png"
            out_path = output_dir / name
            img.save(out_path, "PNG", optimize=True)
            print(f"→ {name}")
        else:
            print("(intermediate)")

    return images


def generate_ico(images: dict[int, Image.Image], output_dir: Path):
    """Generate Windows .ico file with multiple embedded sizes."""
    ico_sizes = [16, 32, 48, 64, 128, 256]
    out_path = output_dir / "opensak.ico"

    # Pillow can write .ico with multiple sizes
    ico_images = []
    for size in ico_sizes:
        if size in images:
            img = images[size].copy()
        else:
            # Resize from nearest larger
            src = min((s for s in images if s >= size), default=256)
            img = images[src].resize((size, size), Image.LANCZOS)
        ico_images.append(img)

    # Save with all sizes embedded
    ico_images[0].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_images[1:],
    )
    print(f"  → opensak.ico  ({', '.join(str(s) for s in ico_sizes)}px embedded)")


def generate_icns(images: dict[int, Image.Image], output_dir: Path):
    """
    Generate macOS .icns file.
    Tries iconutil (macOS only) first, then falls back to manual ICNS writing.
    """
    out_path = output_dir / "opensak.icns"

    # Try iconutil (only available on macOS)
    import subprocess
    import tempfile
    iconset_dir = Path(tempfile.mkdtemp()) / "opensak.iconset"
    iconset_dir.mkdir()

    icns_map = {
        16:   ("icon_16x16.png",     "icon_16x16@2x.png"),    # @2x = 32
        32:   ("icon_32x32.png",     "icon_32x32@2x.png"),    # @2x = 64
        64:   None,
        128:  ("icon_128x128.png",   "icon_128x128@2x.png"),  # @2x = 256
        256:  ("icon_256x256.png",   "icon_256x256@2x.png"),  # @2x = 512
        512:  ("icon_512x512.png",   "icon_512x512@2x.png"),  # @2x = 1024
    }

    wrote_iconset = False
    try:
        for base_size, names in icns_map.items():
            if names is None:
                continue
            normal_name, retina_name = names
            double_size = base_size * 2

            if base_size in images:
                images[base_size].save(iconset_dir / normal_name, "PNG")
            if double_size in images:
                images[double_size].save(iconset_dir / retina_name, "PNG")

        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(out_path)],
            capture_output=True, timeout=30
        )
        if result.returncode == 0:
            wrote_iconset = True
            print(f"  → opensak.icns  (via iconutil)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not wrote_iconset:
        # Manual ICNS writing (cross-platform fallback)
        _write_icns_manually(images, out_path)
        print(f"  → opensak.icns  (manual, cross-platform)")

    # Cleanup
    import shutil
    shutil.rmtree(iconset_dir.parent, ignore_errors=True)


def _write_icns_manually(images: dict[int, Image.Image], out_path: Path):
    """Write a valid .icns file manually without iconutil."""
    import io as _io

    # ICNS OSType codes for PNG data (ic07..ic14)
    ostype_map = {
        16:   b"icp4",
        32:   b"icp5",
        64:   b"icp6",
        128:  b"ic07",
        256:  b"ic08",
        512:  b"ic09",
        1024: b"ic10",
    }

    entries = []
    for size, ostype in ostype_map.items():
        if size not in images:
            continue
        buf = _io.BytesIO()
        images[size].save(buf, "PNG")
        png_data = buf.getvalue()
        # Each entry: 4-byte OSType + 4-byte length (including 8-byte header) + data
        entry_len = 8 + len(png_data)
        entries.append(ostype + struct.pack(">I", entry_len) + png_data)

    total_len = 8 + sum(len(e) for e in entries)
    with open(out_path, "wb") as f:
        f.write(b"icns")                        # magic
        f.write(struct.pack(">I", total_len))   # file size
        for entry in entries:
            f.write(entry)


def install_linux_desktop(output_dir: Path):
    """
    Print instructions for installing the icon on Linux.
    Optionally, actually install it if running as the user.
    """
    print()
    print("Linux desktop icon installation:")
    print("  Copy to XDG icon directory:")
    print(f"    sudo cp {output_dir}/opensak.png /usr/share/pixmaps/opensak.png")
    print(f"    cp {output_dir}/opensak.png ~/.local/share/icons/opensak.png")
    print()
    print("  For hicolor theme (recommended):")
    icon_sizes = [16, 32, 48, 64, 128, 256]
    for size in icon_sizes:
        src = "opensak.png" if size == 256 else f"opensak_{size}.png"
        if (output_dir / src).exists():
            dest = f"~/.local/share/icons/hicolor/{size}x{size}/apps/opensak.png"
            print(f"    cp {output_dir}/{src} {dest}")
    print()
    print("  Then update icon cache:")
    print("    gtk-update-icon-cache ~/.local/share/icons/hicolor/")


def main():
    if not SVG_SOURCE.exists():
        print(f"ERROR: SVG source not found: {SVG_SOURCE}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"OpenSAK Icon Generator")
    print(f"Source: {SVG_SOURCE}")
    print(f"Output: {OUTPUT_DIR}/")
    print()

    # Generate all PNG sizes
    images = generate_png_sizes(SVG_SOURCE, OUTPUT_DIR)

    print()
    print("Generating platform-specific formats...")

    # Windows .ico
    generate_ico(images, OUTPUT_DIR)

    # macOS .icns
    generate_icns(images, OUTPUT_DIR)

    print()
    print("Done! Files generated:")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name:<30} {size_kb:6.1f} KB")

    install_linux_desktop(OUTPUT_DIR)


if __name__ == "__main__":
    main()
