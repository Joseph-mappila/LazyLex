
"""LazyLex application entry point."""

import signal
import argparse
import sys
import os

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from pynput.keyboard import GlobalHotKeys

from lazylex import __app_name__
from lazylex.overlay import Overlay
from lazylex.selection import get_selected_text
from lazylex.lookup import lookup


SERVER_NAME = "LazyLex-Desktop-Companion"


class Signals(QObject):
    """Signals for thread-safe UI communication."""

    hotkey = pyqtSignal()


class LookupWorker(QThread):
    """Run API lookups in a background thread."""

    finished_lookup = pyqtSignal(str, object)

    def __init__(self, term):
        super().__init__()
        self.term = term

    def run(self):
        result = lookup(self.term)
        self.finished_lookup.emit(self.term, result)


class LazyLexApp:
    """Main LazyLex application controller."""

    def __init__(self, app):

        self.app = app
        self.overlay = Overlay()

        self.signals = Signals()
        self.signals.hotkey.connect(self.toggle_lookup)

        # Connect the search field to the same lookup system.
        self.overlay.search_requested.connect(
            self.search_lookup
        )

        self.workers = []
        self.lookup_id = 0
        self.listener = None

        self.server = QLocalServer(app)

        # Remove a stale socket from a previous crash.
        QLocalServer.removeServer(SERVER_NAME)

        if not self.server.listen(SERVER_NAME):
            raise RuntimeError(
                self.server.errorString()
            )

        self.server.newConnection.connect(
            self.handle_connection
        )

    def start_hotkey_listener(self):
        """Register global hotkeys where supported."""

        # Wayland does not reliably support global pynput shortcuts.
        is_wayland = (
            os.environ.get("XDG_SESSION_TYPE") == "wayland"
            or "WAYLAND_DISPLAY" in os.environ
        )

        if is_wayland:
            print("Wayland detected.")
            print("Configure LazyLex using your desktop's native shortcut.")
            return

        # Use portable shortcuts on platforms supported by pynput.
        hotkeys = {
            "<ctrl>+<alt>+d": self.request_toggle,
        }

        try:
            self.listener = GlobalHotKeys(hotkeys)
            self.listener.start()

            print("LazyLex is running.")
            print("Shortcut: Ctrl + Alt + D")

        except Exception as error:
            print("Global hotkey unavailable:", error)
            print("Configure a native desktop shortcut instead.")

    def request_toggle(self):
        """Send a toggle signal to the Qt main thread."""

        self.signals.hotkey.emit()

    def handle_connection(self):
        """Accept connections from other LazyLex processes."""

        while self.server.hasPendingConnections():

            socket = self.server.nextPendingConnection()

            if socket is None:
                continue

            socket.readyRead.connect(
                lambda s=socket: self.read_command(s)
            )

            socket.disconnected.connect(
                socket.deleteLater
            )

    def read_command(self, socket):
        """Read a local toggle command."""

        command = bytes(socket.readAll()).decode(
            "utf-8",
            errors="replace"
        ).strip()

        if command == "toggle":
            self.request_toggle()

        socket.disconnectFromServer()

    def toggle_lookup(self):
        """Capture the current selection and update the overlay."""

        selected_text = get_selected_text()

        if not selected_text:
            # Invalidate any older lookup still running.
            self.lookup_id += 1

            self.overlay.show_no_selection()
            return

        self.start_lookup(selected_text)

    """def search_lookup(self, term):
        Start a lookup for text entered manually.

        term = term.strip()

        if not term:
            return

        self.start_lookup(term)"""
    def search_lookup(self, term):
        """Start a lookup for text entered manually."""

        print("MAIN RECEIVED SEARCH:", repr(term))

        term = term.strip()

        if not term:
            return

        self.start_lookup(term)

    def start_lookup(self, term):
        """Start a background lookup for the given term."""

        # Give this lookup a unique ID.
        self.lookup_id += 1
        current_id = self.lookup_id

        # Immediately update the existing popup.
        self.overlay.show_loading(term)

        # Start a new lookup, even if an older one is running.
        worker = LookupWorker(term)
        self.workers.append(worker)

        worker.finished_lookup.connect(
            lambda result_term, result, lookup_id=current_id:
                self.on_lookup_finished(
                    lookup_id,
                    result_term,
                    result
                )
        )

        worker.finished.connect(
            lambda w=worker: self.on_worker_finished(w)
        )

        worker.start()

    def on_lookup_finished(self, lookup_id, term, result):
        """Display only the result of the latest lookup."""

        if lookup_id != self.lookup_id:
            return

        if self.overlay.isVisible():
            self.overlay.show_result(term, result)

    def on_worker_finished(self, worker):
        """Clean up a completed lookup thread."""

        if worker in self.workers:
            self.workers.remove(worker)

        worker.deleteLater()

    def stop(self):
        """Clean up application resources."""

        if self.listener is not None:
            self.listener.stop()
            self.listener.join(timeout=1)

        for worker in self.workers:
            worker.wait(12000)

        self.workers.clear()

        self.overlay.stop_pronunciation()
        self.overlay.hide()
        self.server.close()


def send_toggle_command():
    """Send a command to an existing LazyLex instance."""

    socket = QLocalSocket()

    socket.connectToServer(SERVER_NAME)

    if not socket.waitForConnected(1000):
        return False

    socket.write(b"toggle")
    socket.flush()
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()

    return True


def main():
    """Start LazyLex."""

    parser = argparse.ArgumentParser(
        description="LazyLex desktop dictionary companion."
    )

    parser.add_argument(
        "--toggle",
        action="store_true",
        help="Toggle an existing LazyLex instance."
    )

    args = parser.parse_args()

    app = QApplication(sys.argv)

    app.setApplicationName(__app_name__)
    app.setQuitOnLastWindowClosed(False)

    # Handle Ctrl+C from the terminal.
    signal.signal(
        signal.SIGINT,
        lambda signum, frame: app.quit()
    )

    # Allow Python to process interrupts while Qt is running.
    app._interrupt_timer = QTimer()
    app._interrupt_timer.timeout.connect(lambda: None)
    app._interrupt_timer.start(200)

    # Used by the Hyprland shortcut.
    if args.toggle:

        if send_toggle_command():
            return 0

        print("LazyLex is not running.")
        return 1

    # Avoid launching multiple instances.
    if send_toggle_command():
        return 0

    controller = LazyLexApp(app)

    controller.start_hotkey_listener()

    app.aboutToQuit.connect(controller.stop)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
