from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.audio.importer import is_youtube_url


class AddMusicDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Music")
        self.setMinimumWidth(520)
        self.mode = ""
        self.files: list[str] = []
        self.youtube_url = ""
        self.optional_name = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        title = QLabel("ADD MUSIC")
        title.setObjectName("Eyebrow")
        layout.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(self._local_tab(), "From Files")
        tabs.addTab(self._youtube_tab(), "From YouTube")
        layout.addWidget(tabs)
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        cancel_row.addWidget(cancel)
        layout.addLayout(cancel_row)

    def _local_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(14)
        message = QLabel(
            "Choose one or more MP3 files. Music HandControl copies them safely into the /music folder."
        )
        message.setWordWrap(True)
        message.setObjectName("Muted")
        layout.addWidget(message)
        self.file_summary = QLabel("No files selected")
        self.file_summary.setWordWrap(True)
        layout.addWidget(self.file_summary)
        choose = QPushButton("Choose MP3 Files…")
        choose.clicked.connect(self._choose_files)
        layout.addWidget(choose)
        import_button = QPushButton("Add Selected Files")
        import_button.setObjectName("PrimaryAction")
        import_button.clicked.connect(self._accept_files)
        layout.addWidget(import_button)
        return tab

    def _youtube_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(10)
        url_label = QLabel("YouTube video link")
        layout.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        layout.addWidget(self.url_input)
        name_label = QLabel("MP3 filename (optional)")
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Leave blank to use the YouTube title")
        self.name_input.setMaxLength(120)
        layout.addWidget(self.name_input)
        legal = QLabel(
            "Only download audio you own or have permission to use. YouTube availability may vary by region."
        )
        legal.setWordWrap(True)
        legal.setObjectName("Muted")
        layout.addWidget(legal)
        download = QPushButton("Download and Convert to MP3")
        download.setObjectName("PrimaryAction")
        download.clicked.connect(self._accept_youtube)
        layout.addWidget(download)
        return tab

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose MP3 Files", "", "MP3 Audio (*.mp3)")
        if paths:
            self.files = paths
            self.file_summary.setText(f"{len(paths)} file{'s' if len(paths) != 1 else ''} selected")

    def _accept_files(self) -> None:
        if not self.files:
            QMessageBox.information(self, "Add Music", "Choose at least one MP3 file first.")
            return
        self.mode = "files"
        self.accept()

    def _accept_youtube(self) -> None:
        url = self.url_input.text().strip()
        if not is_youtube_url(url):
            QMessageBox.warning(self, "Add Music", "Enter a valid youtube.com or youtu.be video link.")
            return
        self.mode = "youtube"
        self.youtube_url = url
        self.optional_name = self.name_input.text().strip()
        self.accept()
