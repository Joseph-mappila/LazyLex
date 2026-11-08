
"""LazyLex antique dictionary overlay."""

import os
import subprocess
import tempfile

import httpx

from PyQt6.QtCore import (
    Qt,
    QPoint,
    QEvent,
    QUrl,
    QThread,
    pyqtSignal,
)
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QLineEdit,
)


def cleanup_old_audio_files():
    """Remove leftover LazyLex audio files from previous sessions."""

    temp_dir = tempfile.gettempdir()

    for filename in os.listdir(temp_dir):
        if filename.startswith("lazylex-") and filename.endswith(".mp3"):
            file_path = os.path.join(temp_dir, filename)

            try:
                os.remove(file_path)
            except OSError:
                pass


class AudioDownloadWorker(QThread):
    """Download and normalize pronunciation audio."""

    downloaded = pyqtSignal(str, str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        source_path = ""
        output_path = ""

        try:
            response = httpx.get(
                self.url,
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": "LazyLex/0.1"},
            )
            response.raise_for_status()

            if not response.content:
                raise ValueError("The audio server returned an empty file.")

            with tempfile.NamedTemporaryFile(
                prefix="lazylex-source-",
                suffix=".mp3",
                delete=False,
            ) as audio_file:
                source_path = audio_file.name
                audio_file.write(response.content)

            with tempfile.NamedTemporaryFile(
                prefix="lazylex-",
                suffix=".mp3",
                delete=False,
            ) as audio_file:
                output_path = audio_file.name

            # Try to normalize the audio.
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel", "error",
                        "-y",
                        "-i", source_path,
                        "-af",
                        "dynaudnorm=f=150:g=15:p=0.9,volume=2.0,alimiter=limit=0.95",
                        "-codec:a", "libmp3lame",
                        "-q:a", "2",
                        output_path,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if os.path.getsize(output_path) == 0:
                    raise RuntimeError("FFmpeg produced an empty audio file.")

                os.remove(source_path)
                source_path = ""

            except Exception as error:
                print(
                    "Audio normalization failed; using original audio:",
                    error,
                )

                if output_path and os.path.exists(output_path):
                    os.remove(output_path)

                output_path = source_path
                source_path = ""

            self.downloaded.emit(output_path, "")
            output_path = ""

        except Exception as error:
            print("Audio download failed:", error)
            self.downloaded.emit("", str(error))

        finally:
            for path in (source_path, output_path):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass


class Overlay(QWidget):
    """Floating antique-style dictionary window."""

    # Emitted when the user submits a term through the search field.
    search_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        cleanup_old_audio_files()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setFixedWidth(390)
        self.setMinimumHeight(180)
        self.setMaximumHeight(460)

        # Audio player.
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        self.audio_url = None
        self.audio_worker = None
        self.audio_file = None

        self.player.mediaStatusChanged.connect(
            self.handle_media_status
        )

        self.player.errorOccurred.connect(
            self.handle_audio_error
        )

        self.setStyleSheet("""
            QWidget {
                font-family: Georgia, 'Times New Roman', serif;
            }

            QFrame#paper {
                background-color: #eadcbb;
                border: 2px solid #a58a60;
                border-radius: 5px;
            }

            QLabel#word {
                color: #302317;
                font-size: 29px;
                font-weight: bold;
            }

            QLabel#phonetic {
                color: #70583e;
                font-size: 13px;
                font-style: italic;
            }

            QLabel#brand {
                color: #684323;
                font-size: 11px;
                font-weight: bold;
            }

            QLabel#ornament {
                color: #92734e;
                font-size: 13px;
            }

            QLineEdit#search {
                background-color: #f4ead4;
                color: #302317;
                border: 1px solid #b49a70;
                border-radius: 4px;
                padding: 9px 10px;
                font-family: Georgia, 'Times New Roman', serif;
                font-size: 13px;
            }

            QLineEdit#search:focus {
                border: 1px solid #806344;
                background-color: #fff5df;
            }

            QLineEdit#search::placeholder {
                color: #9a8567;
            }

            QPushButton {
                background: transparent;
                color: #806344;
                border: none;
                font-size: 16px;
                padding: 5px 9px;
            }

            QPushButton:hover {
                color: #9a352b;
                background-color: #d9c7a2;
                border-radius: 4px;
            }
        """)

        self.build_ui()
        self.hide()

        app = QApplication.instance()

        if app is not None:
            app.installEventFilter(self)

    def build_ui(self):
        """Construct the antique dictionary card."""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.paper = QFrame()
        self.paper.setObjectName("paper")

        layout = QVBoxLayout(self.paper)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(9)

        # Masthead.
        header = QHBoxLayout()

        brand = QLabel("LAZYLEX  ·  THE POCKET LEXICON")
        brand.setObjectName("brand")

        close_button = QPushButton("×")
        close_button.setFixedSize(28, 28)
        close_button.clicked.connect(self.hide)

        header.addWidget(brand)
        header.addStretch()
        header.addWidget(close_button)

        layout.addLayout(header)

        # Decorative divider.
        ornament = QLabel("✦  ─────────────────────  ✦")
        ornament.setObjectName("ornament")
        ornament.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(ornament)

        # Search field.
        self.search_input = QLineEdit()
        self.search_input.setObjectName("search")
        self.search_input.setPlaceholderText(
            "Search any word or phrase..."
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(
            self.submit_search
        )

        layout.addWidget(self.search_input)

        # Word heading.
        self.word_label = QLabel("LazyLex")
        self.word_label.setObjectName("word")
        self.word_label.setWordWrap(True)

        layout.addWidget(self.word_label)

        # Pronunciation row.
        pronunciation_row = QHBoxLayout()

        self.phonetic_label = QLabel("")
        self.phonetic_label.setObjectName("phonetic")

        self.audio_button = QPushButton("🔊  Listen")
        self.audio_button.setToolTip("Play pronunciation")
        self.audio_button.clicked.connect(
            self.play_pronunciation
        )
        self.audio_button.hide()

        pronunciation_row.addWidget(self.phonetic_label)
        pronunciation_row.addStretch()
        pronunciation_row.addWidget(self.audio_button)

        layout.addLayout(pronunciation_row)

        # Second divider.
        self.separator = QLabel(
            "────────────────────────────"
        )
        self.separator.setObjectName("ornament")

        layout.addWidget(self.separator)

        # Scrollable definition.
        self.content_label = QTextBrowser()
        self.content_label.setObjectName("content")
        self.content_label.setReadOnly(True)
        self.content_label.setOpenExternalLinks(True)
        self.content_label.setFrameShape(QFrame.Shape.NoFrame)

        self.content_label.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #302317;
                font-family: Georgia, 'Times New Roman', serif;
                font-size: 15px;
                selection-background-color: #a58a60;
                selection-color: #fff8e8;
            }

            QScrollBar:vertical {
                background: #e2d2ae;
                width: 7px;
                margin: 2px;
            }

            QScrollBar::handle:vertical {
                background: #92734e;
                border-radius: 3px;
                min-height: 22px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.content_label.setAutoFillBackground(False)
        self.content_label.viewport().setAutoFillBackground(False)

        self.content_label.viewport().setStyleSheet(
            "background-color: transparent; border: none;"
        )

        self.content_label.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.content_label.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.content_label.setMinimumHeight(100)
        self.content_label.setMaximumHeight(290)

        self.content_label.document().setDocumentMargin(2)

        layout.addWidget(self.content_label)

        # Copy button.
        footer_actions = QHBoxLayout()

        self.copy_button = QPushButton("⧉  Copy definition")
        self.copy_button.setToolTip(
            "Copy the complete definition"
        )
        self.copy_button.clicked.connect(
            self.copy_definition
        )

        footer_actions.addStretch()
        footer_actions.addWidget(self.copy_button)
        footer_actions.addStretch()

        layout.addLayout(footer_actions)

        # Footer.
        footer = QLabel("—  A WORD WELL WORTH KNOWING  —")
        footer.setObjectName("brand")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(footer)

        outer.addWidget(self.paper)

    """def submit_search(self):
        Submit the text entered in the search field."

        term = self.search_input.text().strip()

        if not term:
            return

        self.search_requested.emit(term)"""
    def submit_search(self):
        """Submit the text entered in the search field."""

        term = self.search_input.text().strip()

        print("SEARCH BUTTON ENTERED:", repr(term))

        if not term:
            print("Search field is empty.")
            return

        print("Emitting search request...")
        self.search_requested.emit(term)

    def copy_definition(self):
        """Copy the displayed definition to the clipboard."""

        text = self.content_label.toPlainText().strip()

        if not text:
            return

        QGuiApplication.clipboard().setText(text)
        self.copy_button.setText("✓  Copied!")

    def play_pronunciation(self):
        """Download and play the pronunciation."""

        if not self.audio_url:
            return

        if (
            self.audio_worker is not None
            and self.audio_worker.isRunning()
        ):
            return

        self.stop_pronunciation()

        self.audio_button.setText("Downloading...")

        self.audio_worker = AudioDownloadWorker(
            self.audio_url
        )

        worker = self.audio_worker

        worker.downloaded.connect(
            self.start_downloaded_audio
        )

        worker.finished.connect(
            lambda: self.clear_audio_worker(worker)
        )

        worker.start()

    def clear_audio_worker(self, worker):
        """Release the completed download worker."""

        if self.audio_worker is worker:
            self.audio_worker = None

        worker.deleteLater()

    def start_downloaded_audio(self, path, error):
        """Start playback after the MP3 has downloaded."""

        self.audio_button.setText("🔊  Listen")

        if error or not path:
            self.phonetic_label.setText(
                "Unable to download pronunciation."
            )
            return

        self.audio_file = path

        self.player.setSource(
            QUrl.fromLocalFile(self.audio_file)
        )

        self.player.play()

    def handle_media_status(self, status):
        """Clean up audio after playback finishes."""

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.cleanup_audio_file()

    def handle_audio_error(self, error, error_string):
        """Handle pronunciation playback errors."""

        if error == QMediaPlayer.Error.NoError:
            return

        print("Pronunciation playback error:", error_string)

        self.cleanup_audio_file()

        self.phonetic_label.setText(
            "Unable to play pronunciation."
        )

    def cleanup_audio_file(self):
        """Remove the downloaded temporary audio file."""

        if self.audio_file and os.path.exists(self.audio_file):
            try:
                os.remove(self.audio_file)
            except OSError:
                pass

        self.audio_file = None

    def stop_pronunciation(self):
        """Stop playback and remove temporary audio."""

        self.player.stop()
        self.cleanup_audio_file()

    def show_no_selection(self):
        """Display a clear message when no text is selected."""

        self.stop_pronunciation()
        self.audio_url = None

        self.word_label.setText("No word selected")

        self.phonetic_label.clear()
        self.audio_button.hide()

        self.content_label.setHtml(
            '<p style="color:#913D32; font-size:15px;">'
            '<b>No word selected.</b>'
            '</p>'
            '<p style="color:#70583E; font-size:14px;">'
            'Select a word in any application, '
            'then press your LazyLex shortcut.'
            '</p>'
        )

        self.copy_button.setText("⧉  Copy definition")

        self.adjustSize()
        self.show_bottom_right()

    def show_loading(self, term):
        """Show the lookup loading state."""

        self.stop_pronunciation()
        self.audio_url = None

        self.word_label.setText(term[:60])
        self.phonetic_label.clear()
        self.audio_button.hide()

        self.content_label.setText(
            '<p style="color:#806344; font-style:italic;">'
            'Consulting the old lexicon...</p>'
        )

        self.copy_button.setText("⧉  Copy definition")

        self.adjustSize()
        self.show_bottom_right()

    def show_result(self, term, result):
        """Display the definition, phonetic spelling and audio."""

        self.word_label.setText(term[:60])

        if isinstance(result, dict):
            html_content = result.get("html", "")
            phonetic = result.get("phonetic", "")
            audio_url = result.get("audio_url", "")
        else:
            html_content = str(result)
            phonetic = ""
            audio_url = ""

        self.content_label.setHtml(html_content)
        self.phonetic_label.setText(phonetic)

        self.audio_url = audio_url or None

        if self.audio_url:
            self.audio_button.show()
        else:
            self.audio_button.hide()

        self.copy_button.setText("⧉  Copy definition")

        self.adjustSize()
        self.show_bottom_right()

    def show_bottom_right(self):
        """Place the overlay in the bottom-right corner."""

        app = QApplication.instance()

        if app is None:
            self.show()
            return

        screen = app.primaryScreen()

        if screen is None:
            self.show()
            return

        area = screen.availableGeometry()

        x = area.x() + area.width() - self.width() - 24
        y = area.y() + area.height() - self.height() - 24

        self.move(QPoint(x, y))

        self.show()
        self.raise_()
        self.activateWindow()

    def eventFilter(self, watched, event):
        """Hide when another Qt window is clicked."""

        if (
            self.isVisible()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            if isinstance(watched, QWidget):
                if (
                    watched.window() is not self
                    and not self.isAncestorOf(watched)
                ):
                    self.hide()

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        """Dismiss the overlay with Escape."""

        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return

        super().keyPressEvent(event)

    def closeEvent(self, event):
        """Hide rather than destroy the overlay."""

        self.stop_pronunciation()

        event.ignore()
        self.hide()
