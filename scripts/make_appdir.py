"""
make_appdir.py — Bygger AppDir strukturen til AppImage
Køres af GitHub Actions under Linux-buildet.

Strategi: QtWebEngine pakkes MED i AppImage, men konfliktuerende
system-biblioteker (libstdc++, libGL, libEGL) fjernes fra pakken
så systemets egne bruges i stedet. Dette er standard praksis for
Qt AppImage distribution.
"""
import os
import shutil
import stat
import subprocess
import sys
import glob
import base64


def main():
    # Opret mappestruktur
    os.makedirs("AppDir/usr/bin", exist_ok=True)
    os.makedirs("AppDir/usr/share/applications", exist_ok=True)
    os.makedirs("AppDir/usr/share/icons/hicolor/256x256/apps", exist_ok=True)

    # Kopiér den byggede binær
    if not os.path.exists("dist/opensak"):
        print("FEJL: dist/opensak ikke fundet")
        sys.exit(1)
    shutil.copytree("dist/opensak", "AppDir/usr/bin", dirs_exist_ok=True)
    print("Binær kopieret til AppDir/usr/bin/")

    # -----------------------------------------------------------
    # Fjern libs der konflikter med systemets OpenGL/libstdc++
    # PyInstaller bundler disse, men de passer ikke til alle
    # Linux distros. Uden dem bruger AppImage systemets versioner.
    # -----------------------------------------------------------
    libs_to_remove = [
        "libstdc++.so*",
        "libGL.so*",
        "libGLX.so*",
        "libGLdispatch.so*",
        "libEGL.so*",
        "libgbm.so*",
        "libdrm.so*",
    ]

    removed = []
    for search_dir in ["AppDir/usr/bin/_internal", "AppDir/usr/bin"]:
        for pattern in libs_to_remove:
            for f in glob.glob(os.path.join(search_dir, pattern)):
                os.remove(f)
                removed.append(os.path.basename(f))

    if removed:
        print(f"Fjernet {len(removed)} konfliktuerende libs: {', '.join(removed)}")

    # Brug det rigtige ikon fra assets hvis det findes
    icon_src = "assets/icons/opensak.png"
    icon_dst = "AppDir/usr/share/icons/hicolor/256x256/apps/opensak.png"

    if os.path.exists(icon_src):
        shutil.copy(icon_src, icon_dst)
        print("Ikon kopieret fra assets/icons/opensak.png")
    else:
        # Fallback: generer med ImageMagick
        result = subprocess.run([
            "convert", "-size", "256x256", "xc:#1a2332",
            "-fill", "white", "-pointsize", "48", "-gravity", "center",
            "-annotate", "0", "OpenSAK", icon_dst
        ])
        if result.returncode != 0:
            png1x1 = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            )
            open(icon_dst, "wb").write(png1x1)
            print("Ikon: bruger fallback PNG")
        else:
            print("Ikon genereret med ImageMagick")

    shutil.copy(icon_dst, "AppDir/opensak.png")

    # Lav .desktop fil
    desktop = "\n".join([
        "[Desktop Entry]",
        "Name=OpenSAK",
        "Comment=Open Source geocaching management tool",
        "Exec=opensak",
        "Icon=opensak",
        "Type=Application",
        "Categories=Utility;Science;",
        "Terminal=false",
        "",
    ])
    open("AppDir/opensak.desktop", "w").write(desktop)
    open("AppDir/usr/share/applications/opensak.desktop", "w").write(desktop)
    print(".desktop fil skrevet")

    # Lav AppRun script
    apprun_lines = [
        "#!/bin/bash",
        'HERE="$(dirname "$(readlink -f "${0}")")"',
        "",
        "# Brug systemets OpenGL/EGL (undgaar version-konflikter med GPU drivere)",
        'export LD_LIBRARY_PATH="${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH}"',
        'export PATH="${HERE}/usr/bin:${PATH}"',
        "",
        "# QtWebEngine Chromium flags til AppImage kontekst",
        'export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu-sandbox"',
        "",
        "# Software rendering fallback",
        'export QT_QUICK_BACKEND=software',
        "",
        "# Filtrer harmloese systemadvarsler fra stderr",
        "# (xapp-gtk3-module, gvfs, atk-bridge - ikke relateret til OpenSAK)",
        'exec "${HERE}/usr/bin/opensak" "$@" 2> >(grep -vE "xapp-gtk3-module|libgvfscommon|libgvfsdbus|atk-bridge|g_task_set_static_name" >&2)',
        "",
    ]
    open("AppDir/AppRun", "w").write("\n".join(apprun_lines))
    os.chmod(
        "AppDir/AppRun",
        stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
    )
    print("AppRun script skrevet")
    print("\nAppDir klar til appimagetool")


if __name__ == "__main__":
    main()
