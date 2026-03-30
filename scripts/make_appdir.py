"""
make_appdir.py — Bygger AppDir strukturen til AppImage
Køres af GitHub Actions under Linux-buildet.
"""
import os
import shutil
import stat
import subprocess
import sys


def main():
    # Opret mappestruktur
    os.makedirs("AppDir/usr/bin", exist_ok=True)
    os.makedirs("AppDir/usr/share/applications", exist_ok=True)
    os.makedirs("AppDir/usr/share/icons/hicolor/256x256/apps", exist_ok=True)

    # Kopiér den byggede binær
    if not os.path.exists("dist/OpenSAK"):
        print("FEJL: dist/OpenSAK ikke fundet — kør PyInstaller først")
        sys.exit(1)
    shutil.copytree("dist/OpenSAK", "AppDir/usr/bin", dirs_exist_ok=True)
    print("✓ Binær kopieret til AppDir/usr/bin/")

    # Lav ikon med ImageMagick
    icon_path = "AppDir/usr/share/icons/hicolor/256x256/apps/opensak.png"
    result = subprocess.run([
        "convert", "-size", "256x256", "xc:#2a6496",
        "-fill", "white", "-pointsize", "48", "-gravity", "center",
        "-annotate", "0", "OpenSAK",
        icon_path
    ])
    if result.returncode != 0:
        print("ADVARSEL: ImageMagick fejlede — laver tomt ikon som fallback")
        open(icon_path, "wb").write(b"")
    else:
        print("✓ Ikon genereret")

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
    print("✓ .desktop fil skrevet")

    # Lav AppRun script
    apprun = "\n".join([
        "#!/bin/bash",
        'HERE="$(dirname "$(readlink -f "${0}")")"',
        'export PATH="${HERE}/usr/bin:${PATH}"',
        'export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/bin:${LD_LIBRARY_PATH}"',
        'export QT_PLUGIN_PATH="${HERE}/usr/bin/PySide6/Qt/plugins"',
        'exec "${HERE}/usr/bin/OpenSAK" "$@"',
        "",
    ])
    open("AppDir/AppRun", "w").write(apprun)
    os.chmod("AppDir/AppRun", stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    print("✓ AppRun script skrevet")

    print("\nAppDir klar til appimagetool")


if __name__ == "__main__":
    main()
