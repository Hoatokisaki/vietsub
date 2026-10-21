import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from qfluentwidgets import (PushButton, CheckBox, CaptionLabel, SimpleCardWidget)

class HighlightCard(SimpleCardWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.thumb_worker = None
        self.setFixedSize(260, 250)
        self.setObjectName('HighlightCard')
        self.setStyleSheet('\n            #HighlightCard {\n                background-color: #1E293B;\n                border-radius: 8px;\n                border: 1px solid #334155;\n            }\n            #HighlightCard:hover {\n                border: 1px solid #0EA5E9;\n            }\n        ')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.lbl_thumb = QLabel(self)
        self.lbl_thumb.setFixedHeight(146)
        self.lbl_thumb.setStyleSheet('background-color: #0F172A; border-top-left-radius: 8px; border-top-right-radius: 8px; color: #475569;')
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setText('⏳ Đang tải...')
        layout.addWidget(self.lbl_thumb)
        info_container = QWidget(self)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(12, 10, 12, 12)
        info_layout.setSpacing(6)
        name_short = data['name']
        if len(name_short) > 20:
            name_short = name_short[:17] + '...'
        self.checkbox = CheckBox(name_short, self)
        self.checkbox.setChecked(True)
        info_layout.addWidget(self.checkbox)
        self.lbl_status = CaptionLabel('Chưa xử lý', self)
        self.lbl_status.setStyleSheet('color: #94A3B8;')
        info_layout.addWidget(self.lbl_status)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)
        self.btn_details = PushButton('Chi Tiết', self)
        self.btn_details.setFixedHeight(28)
        self.btn_details.setStyleSheet('\n            QPushButton { background-color: #F59E0B; color: white; border-radius: 4px; border: none; font-weight: bold; }\n            QPushButton:hover { background-color: #D97706; }\n        ')
        from qfluentwidgets import TransparentToolButton, FluentIcon as FIF
        self.btn_folder = TransparentToolButton(FIF.FOLDER, self)
        self.btn_folder.setToolTip('Mở thư mục')
        self.btn_folder.setFixedSize(28, 28)
        btn_layout.addWidget(self.btn_details, stretch=1)
        btn_layout.addWidget(self.btn_folder)
        self.btn_frame = QWidget()
        self.btn_frame.setLayout(btn_layout)
        info_layout.addWidget(self.btn_frame)
        layout.addWidget(info_container)
        if not data['existing_hl']:
            self.btn_frame.hide()
        else:
            self.checkbox.setChecked(False)
            self.lbl_status.setText(f'Hoàn thành ({len(data["existing_hl"])} đoạn)!')
            self.lbl_status.setStyleSheet('color: #10B981; font-weight: bold;')
            self.setStyleSheet('\n                #HighlightCard {\n                    background-color: #1E293B;\n                    border-radius: 8px;\n                    border: 2px solid #10B981;\n                }\n            ')
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_details.clicked.connect(self._show_details)

    def load_thumbnail(self):
        from app.views.library_interface import ThumbnailWorker
        self.thumb_worker = ThumbnailWorker(self.data['dubbed_video'], self)
        self.thumb_worker.thumbnail_ready.connect(self._on_thumb_ready)
        self.thumb_worker.start()

    def _on_thumb_ready(self, path, qimage):
        pixmap = QPixmap.fromImage(qimage)
        self.lbl_thumb.setPixmap(pixmap.scaled(258, 146, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def cleanup(self):
        if self.thumb_worker and self.thumb_worker.isRunning():
            try:
                self.thumb_worker.safe_stop()
                self.thumb_worker.quit()
                self.thumb_worker.wait(500)
            except:
                pass
        self.thumb_worker = None

    def _open_folder(self):
        hl_dir = os.path.join(self.data['ws_dir'], 'Highlights')
        if os.path.exists(hl_dir):
            os.startfile(hl_dir)
            return
        os.startfile(self.data['ws_dir'])

    def _show_details(self):
        from app.views.ai_dialogs import HighlightDialog
        dlg = HighlightDialog(self.data['existing_hl'], self.data['ws_dir'], self.window())
        dlg.exec()


