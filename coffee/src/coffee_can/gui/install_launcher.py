"""One-time installer for a Coffee Can entry in the Ubuntu app menu.

Run as `coffeecan-install-launcher` after `pipx install .` so the app shows up
in the GNOME/Ubuntu app grid and never needs a terminal again.
"""

import shutil
import subprocess
from pathlib import Path

from ..assets import icon_path

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Coffee Can
Comment=Log hand-brew coffee profiles and brewing sessions
Exec={exec_path}
Icon={icon_path}
Terminal=false
Categories=Utility;
"""

# Pre-rename filenames this app used to install under; cleaned up so renaming
# doesn't leave a stale duplicate "Coffee Journal" entry in the app menu.
_OLD_DESKTOP_FILE = "coffee-journal.desktop"
_OLD_ICON_FILE = "coffee-journal.svg"


def _remove_old_launcher(apps_dir: Path, icons_dir: Path) -> None:
    old_desktop = apps_dir / _OLD_DESKTOP_FILE
    old_icon = icons_dir / _OLD_ICON_FILE
    old_desktop.unlink(missing_ok=True)
    old_icon.unlink(missing_ok=True)


def main():
    exe = shutil.which("coffeecan-gui")
    if exe is None:
        raise SystemExit(
            "coffeecan-gui was not found on PATH. Install this package first "
            "(pipx install .) and make sure pipx's bin directory is on PATH."
        )

    icons_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icons_dir.mkdir(parents=True, exist_ok=True)
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)

    _remove_old_launcher(apps_dir, icons_dir)

    icon_dest = None
    icon_source = icon_path()
    if icon_source:
        icon_dest = icons_dir / "coffee-can.svg"
        shutil.copy2(icon_source, icon_dest)

    desktop_file = apps_dir / "coffee-can.desktop"
    desktop_file.write_text(
        DESKTOP_ENTRY.format(exec_path=exe, icon_path="coffee-can" if icon_dest else "utilities-terminal")
    )
    desktop_file.chmod(0o755)

    try:
        subprocess.run(["update-desktop-database", str(apps_dir)], check=False)
    except FileNotFoundError:
        pass

    print(f"Installed app launcher: {desktop_file}")
    print('Look for "Coffee Can" in your application menu (log out/in once if it does not show up yet).')


if __name__ == "__main__":
    main()
