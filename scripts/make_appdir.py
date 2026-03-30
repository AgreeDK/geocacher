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
    if not os.path.exists("dist/OpenSAK"):
        print("FEJL: dist/OpenSAK ikke fundet")
        sys.exit(1)
    shutil.copytree("dist/OpenSAK", "AppDir/usr/bin", dirs_exist_ok=True)
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

    # Lav ikon
    icon_path = "AppDir/usr/share/icons/hicolor/256x256/apps/opensak.png"
    result = subprocess.run([
        "convert", "-size", "256x256", "xc:#2a6496",
        "-fill", "white", "-pointsize", "48", "-gravity", "center",
        "-annotate", "0", "OpenSAK", icon_path
    ])
    if result.returncode != 0:
        png1x1 = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        open(icon_path, "wb").write(png1x1)
        print("Ikon: bruger fallback PNG")
    else:
        print("Ikon genereret")

    shutil.copy(icon_path, "AppDir/opensak.png")

    # Lav .desktop fil
    desktop = "\n".join([
        "[Desktop Entry]",
        "Name=OpenSAK",
        "Comment=Open Source geocaching management tool",
        "Exec=OpenSAK",
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
        'exec "${HERE}/usr/bin/OpenSAK" "$@"',
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
