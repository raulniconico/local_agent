"""Cable sync: the agent moves the bundle itself, over USB, with no server.

WHY THIS EXISTS. `sync_tools` can build a bundle and merge one, but until now
a human had to carry the file between the two machines. These tools close that
gap without introducing the one thing the whole architecture forbids: a server
holding user content. `specs/legal-accounts.md` §3.8 is a binding statement
that none exists, and the app says so to the user in three languages. A USB
cable is the strongest possible form of that promise -- the bytes go from one
device the user owns to another device the user owns, over a wire, and no
network is involved at any point.

HOW A CABLE ASKS AN APP TO DO SOMETHING. `adb` can put a file on the phone but
cannot make the app read it: only the app may touch its own Room database. So
each direction is two steps -- move the file, then fire an intent that tells
`MainActivity` what to do with it (`SyncBundle.ACTION_IMPORT` /
`ACTION_EXPORT`).

WHY THE DROP BOX IS `Android/data/<pkg>/files/sync/`. It is the one directory
both sides can reach unaided: `adb` runs as the shell user and may write there,
and an app can always read its **own** external files dir without holding a
permission. Anywhere else costs a runtime storage permission or a hand-driven
SAF picker, which is exactly the manual step being removed. Since Android 11 it
is also closed to every *other* app on the phone.

WHAT THIS DOES NOT DO. It does not make the phone's conflict model any smarter:
a push still merges additively on the phone (new bean names land, existing ones
are left alone), because that is `SyncBundle.importFrom`'s guarantee and the
cable does not change it. Pulling the other way still goes through
`inspect_coffee_bundle` / `apply_coffee_bundle` and still asks the user per
conflicting bean.
"""

import shutil
import subprocess
import time
from pathlib import Path

from langchain_core.tools import tool

from config import ADB_PATH, ANDROID_PACKAGE
from sync_tools import _export_to, _read_bundle

#: Where the phone and the desktop meet. Mirrors `SyncBundle.usbDir`.
_REMOTE_DIR = f"/sdcard/Android/data/{ANDROID_PACKAGE}/files/sync"
_REMOTE_IN = f"{_REMOTE_DIR}/incoming.zip"
_REMOTE_OUT = f"{_REMOTE_DIR}/outgoing.zip"

_ACTION_IMPORT = "app.coffeecan.action.IMPORT_BUNDLE"
_ACTION_EXPORT = "app.coffeecan.action.EXPORT_BUNDLE"

#: How long to wait for the app to finish writing its side of the bundle. A
#: cold start plus a few hundred beans is comfortably under this; the poll
#: below exits as soon as the file stops growing, so the ceiling only matters
#: when something has genuinely gone wrong.
_EXPORT_TIMEOUT_S = 45


class AdbError(RuntimeError):
    """Anything that went wrong at the cable, phrased for the user."""


def _adb_binary() -> str:
    if ADB_PATH:
        return ADB_PATH
    found = shutil.which("adb")
    if found:
        return found
    fallback = Path.home() / "android-sdk" / "platform-tools" / "adb"
    if fallback.exists():
        return str(fallback)
    raise AdbError(
        "adb isn't installed, or isn't on PATH. It ships with the Android "
        "SDK platform-tools; set ADB_PATH in coffee_agent/.env to point at it."
    )


def _adb(*args: str, timeout: int = 120) -> str:
    proc = subprocess.run(
        [_adb_binary(), *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise AdbError((proc.stderr or proc.stdout).strip() or f"adb {args[0]} failed")
    return proc.stdout


def _require_phone() -> str:
    """The one attached device, or a sentence explaining which of the several
    ways this can fail actually happened."""
    out = _adb("devices", timeout=30)
    devices, unauthorized = [], []
    for line in out.splitlines()[1:]:
        if not line.strip():
            continue
        serial, _, state = line.partition("\t")
        state = state.strip()
        if state == "device":
            devices.append(serial.strip())
        elif state == "unauthorized":
            unauthorized.append(serial.strip())

    if unauthorized and not devices:
        raise AdbError(
            "The phone is plugged in but hasn't authorised this computer. "
            "Unlock it and tap 'Allow' on the USB debugging prompt."
        )
    if not devices:
        raise AdbError(
            "No phone is connected. Plug it in over USB and turn on USB "
            "debugging (Settings > Developer options)."
        )
    if len(devices) > 1:
        raise AdbError(
            f"More than one device is attached ({', '.join(devices)}). "
            f"Unplug the ones you don't want to sync with."
        )

    installed = _adb("shell", "pm", "list", "packages", ANDROID_PACKAGE, timeout=30)
    if ANDROID_PACKAGE not in installed:
        raise AdbError(
            f"{ANDROID_PACKAGE} isn't installed on the phone, so there is "
            f"nothing to sync with."
        )
    return devices[0]


def _wake_app_and_wait_for_dropbox() -> None:
    """Launch the app so it creates the drop box, and wait until it has.

    THE DESKTOP MUST NOT `mkdir` THIS ITSELF, and the reason cost a debugging
    session worth recording: a directory created over adb is owned by the
    *shell* user, while everything else under `files/` is owned by the app.
    The app then gets `EACCES` writing its own export into it and cannot even
    stat the bundle pushed there -- `File.exists()` simply returns false, so
    the failure looks like "the desktop never sent anything" rather than like
    a permission problem. Launching the app first costs a second and makes the
    ownership correct by construction.
    """
    _adb("shell", "am", "start", "-W", "-n", f"{ANDROID_PACKAGE}/.MainActivity")
    deadline = time.time() + 20
    while time.time() < deadline:
        out = _adb("shell", f"ls -d {_REMOTE_DIR} 2>/dev/null || true", timeout=30)
        if _REMOTE_DIR in out:
            return
        time.sleep(0.5)
    raise AdbError(
        "the app didn't create its sync folder. Open Coffee Can on the phone "
        "once, then try again -- and check the phone is unlocked, since "
        "Android won't start an app while the screen is locked."
    )


def _remote_size(path: str) -> int:
    """Size in bytes, or -1 when the file isn't there.

    `ls -l` rather than `stat`: toybox and busybox disagree about `stat`'s
    flags across vendor ROMs, and this only needs one number.
    """
    out = _adb("shell", f"ls -l {path} 2>/dev/null || true", timeout=30)
    for line in out.split("\n"):
        parts = line.split()
        if len(parts) >= 5 and parts[-1].endswith(".zip"):
            for token in parts:
                if token.isdigit() and int(token) > 0:
                    return int(token)
    return -1


# ------------------------------------------------------------ desktop -> phone --

@tool
def send_coffee_data_to_phone() -> str:
    """Package this machine's coffee-can data and copy it to the phone over
    USB, then tell the app to import it. No file for the user to carry.

    Requires the phone plugged in with USB debugging on. The phone merges
    additively -- beans it doesn't have are added, beans it already has are
    left untouched -- so this will not push an edit onto a bean the phone
    already knows about.
    """
    try:
        _require_phone()
        staged = _export_to(Path.home() / ".cache" / "coffee-can-sync" / "outgoing.zip")
        _wake_app_and_wait_for_dropbox()
        _adb("push", str(staged.path), _REMOTE_IN)
        # -W waits for the launch to complete, so a failure to start the
        # activity surfaces here rather than as a silent no-op.
        _adb("shell", "am", "start", "-W", "-a", _ACTION_IMPORT,
             "-n", f"{ANDROID_PACKAGE}/.MainActivity")
    except AdbError as exc:
        return f"Couldn't sync to the phone: {exc}"
    except subprocess.TimeoutExpired:
        return "Couldn't sync to the phone: adb stopped responding."

    return (
        f"Sent {staged.beans} beans, {staged.sessions} sessions and "
        f"{staged.images} images to the phone over USB, and asked the app to "
        f"import them. The phone shows what it added; beans it already had "
        f"were left untouched."
    )


# ------------------------------------------------------------ phone -> desktop --

@tool
def fetch_coffee_data_from_phone(destination: str = "from-phone.zip") -> str:
    """Ask the phone to package its coffee log, pull it over USB, and report
    what it contains. Does not change anything on this machine.

    `destination` is a path inside the agent workspace. Follow this with
    inspect_coffee_bundle to see what would change, then apply_coffee_bundle
    once the user has resolved any conflicts -- pulling a bundle is not the
    same as importing it, and this tool deliberately stops short.
    """
    from tools import _resolve  # local: keeps the sandbox chokepoint in one place

    target = _resolve(destination)
    if target.suffix != ".zip":
        target = target.with_suffix(".zip")

    try:
        _require_phone()
        _wake_app_and_wait_for_dropbox()
        # Clear any bundle from a previous run first. Otherwise a failed
        # export would be invisible: the pull would succeed against a stale
        # file and report yesterday's data as though it were fresh.
        _adb("shell", f"rm -f {_REMOTE_OUT}")
        _adb("shell", "am", "start", "-W", "-a", _ACTION_EXPORT,
             "-n", f"{ANDROID_PACKAGE}/.MainActivity")

        deadline = time.time() + _EXPORT_TIMEOUT_S
        size, stable = -1, 0
        while time.time() < deadline:
            time.sleep(1.0)
            current = _remote_size(_REMOTE_OUT)
            if current > 0 and current == size:
                stable += 1
                # Two consecutive equal readings: the zip is closed, not
                # merely part-written. Pulling mid-write yields a truncated
                # archive that fails much later, at parse time.
                if stable >= 2:
                    break
            else:
                stable = 0
            size = current
        else:
            raise AdbError(
                "the app didn't produce a bundle in time. Check the phone is "
                "unlocked -- Android won't start the app's export while the "
                "screen is locked."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        _adb("pull", _REMOTE_OUT, str(target))
    except AdbError as exc:
        return f"Couldn't fetch from the phone: {exc}"
    except subprocess.TimeoutExpired:
        return "Couldn't fetch from the phone: adb stopped responding."

    try:
        beans = _read_bundle(target)
    except ValueError as exc:
        return f"Pulled {target}, but it isn't readable: {exc}"

    sessions = sum(len(b.get("sessions", [])) for b in beans)
    return (
        f"Pulled the phone's log to {target} — {len(beans)} beans, "
        f"{sessions} sessions. Nothing on this machine has changed yet: run "
        f"inspect_coffee_bundle on it to see what would."
    )


USB_TOOLS = [send_coffee_data_to_phone, fetch_coffee_data_from_phone]
