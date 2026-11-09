
"""Cross-platform selected text capture."""

import os
import platform
import shutil
import subprocess
import time

import pyperclip
from pynput.keyboard import Controller, Key


MAX_SELECTION_LENGTH = 200


def is_wayland():
    return (
        platform.system() == "Linux"
        and bool(os.environ.get("WAYLAND_DISPLAY"))
    )


def run_command(command, timeout=2, input_text=None):
    """Run a system command safely."""

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout,
            check=True,
        )
        return result.stdout

    except (subprocess.SubprocessError, OSError):
        return None


def get_primary_selection():
    """Read text highlighted with the mouse on Wayland."""

    if not is_wayland() or not shutil.which("wl-paste"):
        return None

    text = run_command(
        ["wl-paste", "--primary", "--no-newline"]
    )

    return text[:MAX_SELECTION_LENGTH].strip() if text else None


def get_wayland_clipboard():
    """Read the regular Wayland clipboard."""

    if not shutil.which("wl-paste"):
        return None

    text = run_command(
        ["wl-paste", "--no-newline"]
    )

    return text[:MAX_SELECTION_LENGTH].strip() if text else None


def restore_wayland_clipboard(old_clipboard):
    """Restore the previous Wayland clipboard contents."""

    if old_clipboard is None:
        run_command(["wl-copy", "--clear"], timeout=3)
    else:
        run_command(
            ["wl-copy", "--type", "text/plain"],
            input_text=old_clipboard,
            timeout=3,
        )


def copy_selection_wayland():
    """Copy highlighted text using the Wayland virtual keyboard."""

    if not shutil.which("wtype") or not shutil.which("wl-copy"):
        return None

    # Save the clipboard before simulating Ctrl+C.
    old_clipboard = run_command(
        ["wl-paste", "--no-newline"]
    )

    try:
        result = run_command(
            ["wtype", "-M", "ctrl", "c", "-m", "ctrl"]
        )

        if result is None:
            return None

        time.sleep(0.25)

        selected_text = run_command(
            ["wl-paste", "--no-newline"]
        )

        if not selected_text or selected_text == old_clipboard:
            return None

        return selected_text[:MAX_SELECTION_LENGTH].strip() or None

    finally:
        # Restore the original clipboard, even if copying fails.
        restore_wayland_clipboard(old_clipboard)


def simulate_copy():
    """Fallback copy method for other desktop environments."""

    keyboard = Controller()

    try:
        old_clipboard = pyperclip.paste()
    except pyperclip.PyperclipException:
        # Do not modify the clipboard if we cannot save it.
        return None

    copied_text = None

    try:
        pyperclip.copy("")

        modifier = (
            Key.cmd
            if platform.system() == "Darwin"
            else Key.ctrl
        )

        with keyboard.pressed(modifier):
            keyboard.press("c")
            keyboard.release("c")

        time.sleep(0.3)

        copied_text = pyperclip.paste().strip()

    except Exception:
        copied_text = None

    finally:
        # Always attempt to restore the previous clipboard.
        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass

    if copied_text:
        return copied_text[:MAX_SELECTION_LENGTH]

    return None


def get_selected_text():
    """Retrieve selected text using the best available method."""

    if is_wayland():

        # First try the mouse-highlighted primary selection.
        text = get_primary_selection()

        if text:
            return text

        # Otherwise simulate Ctrl+C through Wayland.
        return copy_selection_wayland()

    # Other platforms.
    return simulate_copy()
