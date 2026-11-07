
"""LazyLex application entry point."""
import signal
import argparse
import sys

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

    finished_lookup = pyqtSignal(str, str)

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

        self.worker = None
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

        hotkeys = {
            "<ctrl>+<alt>+d": self.request_toggle,
            "<super>+<shift>+d": self.request_toggle,
        }

        try:
            self.listener = GlobalHotKeys(hotkeys)
            self.listener.start()

            print("LazyLex is running.")
            print("Shortcut: Ctrl + Alt + D")

        except Exception as error:
            print("Global hotkey unavailable:", error)
            print("Use the native desktop shortcut.")

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
        """Capture text and show the definition."""

        if self.overlay.isVisible():
            self.overlay.hide()
            return

        selected_text = get_selected_text()

        if not selected_text:

            self.overlay.word_label.setText("LazyLex")

            self.overlay.content_label.setText(
                '<p style="color:#f38ba8;">'
                'No text selected. '
                'Please select a word and try again.'
                '</p>'
            )

            self.overlay.adjustSize()
            self.overlay.show_bottom_right()
            return

        self.overlay.show_loading(selected_text)

        if self.worker is not None:
            if self.worker.isRunning():
                self.overlay.content_label.setText(
                    "Another lookup is already running."
                )
                return

        self.worker = LookupWorker(selected_text)

        self.worker.finished_lookup.connect(
            self.on_lookup_finished
        )

        self.worker.finished.connect(
            self.on_worker_finished
        )

        self.worker.start()

    def on_lookup_finished(self, term, result):
        """Display the lookup result."""

        if self.overlay.isVisible():
            self.overlay.show_result(term, result)

    def on_worker_finished(self):
        """Clean up the finished background thread."""

        worker = self.worker

        if worker is not None:
            self.worker = None
            worker.deleteLater()

    def stop(self):
        """Clean up application resources."""

        if self.listener is not None:
            self.listener.stop()
            self.listener.join(timeout=1)

        if self.worker is not None:
            self.worker.wait(12000)

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
