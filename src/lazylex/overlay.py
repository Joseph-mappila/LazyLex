
"""LazyLex antique dictionary overlay."""

from PyQt6.QtCore import Qt, QPoint, QEvent
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser
)
from PyQt6.QtGui import QGuiApplication


class Overlay(QWidget):
    """Floating antique-style dictionary window."""

    def __init__(self):
        super().__init__()

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

            QLabel#brand {
                color: #684323;
                font-size: 11px;
                font-weight: bold;
            }

            QLabel#ornament {
                color: #92734e;
                font-size: 13px;
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

        # Masthead
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

        # Decorative divider
        ornament = QLabel("✦  ─────────────────────  ✦")
        ornament.setObjectName("ornament")
        ornament.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(ornament)

        # Word heading
        self.word_label = QLabel("LazyLex")
        self.word_label.setObjectName("word")
        self.word_label.setWordWrap(True)

        layout.addWidget(self.word_label)

        # Second divider
        self.separator = QLabel(
            "────────────────────────────"
        )
        self.separator.setObjectName("ornament")

        layout.addWidget(self.separator)

        # Scrollable definition
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

        # Copy button
        footer_actions = QHBoxLayout()

        self.copy_button = QPushButton("⧉  Copy definition")
        self.copy_button.setToolTip("Copy the complete definition")
        self.copy_button.clicked.connect(self.copy_definition)

        footer_actions.addStretch()
        footer_actions.addWidget(self.copy_button)
        footer_actions.addStretch()

        layout.addLayout(footer_actions)

        # Footer
        footer = QLabel("—  A WORD WELL WORTH KNOWING  —")
        footer.setObjectName("brand")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(footer)

        outer.addWidget(self.paper)

    def copy_definition(self):
        """Copy the displayed definition to the clipboard."""

        text = self.content_label.toPlainText().strip()

        if not text:
            return

        QGuiApplication.clipboard().setText(text)

        self.copy_button.setText("✓  Copied!")

    def show_loading(self, term):
        """Show the lookup loading state."""

        self.word_label.setText(term[:60])

        self.content_label.setText(
            '<p style="color:#806344; font-style:italic;">'
            'Consulting the old lexicon...</p>'
        )

        self.copy_button.setText("⧉  Copy definition")

        self.adjustSize()
        self.show_bottom_right()

    def show_result(self, term, result):
        """Display the definition or summary."""

        self.word_label.setText(term[:60])
        self.content_label.setText(result)

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

        event.ignore()
        self.hide()
