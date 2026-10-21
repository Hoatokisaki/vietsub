from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from qfluentwidgets import ScrollArea, SubtitleLabel
from app.components.splitter_card import SplitterCard

class VideoSplitterInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('VideoSplitterInterface')
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setStyleSheet('QScrollArea, #VideoSplitterInterface { background-color: transparent; border: none; }')
        self.layout = QVBoxLayout(self.view)
        self.layout.setContentsMargins(36, 20, 36, 20)
        self.layout.setSpacing(24)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_title = SubtitleLabel('Chia tập cho Video', self)
        self.layout.addWidget(self.lbl_title)
        self.card = SplitterCard(self)
        self.layout.addWidget(self.card)
        self.layout.addStretch(1)


