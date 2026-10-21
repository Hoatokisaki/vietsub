import os
import json
import shutil
from app.core import highlight_manager
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QCheckBox)
from PyQt6.QtCore import (Qt, pyqtSignal, QTimer)
from PyQt6.QtGui import QPixmap, QImage
from qfluentwidgets import (ScrollArea, PushButton, InfoBar, InfoBarPosition, PrimaryPushButton, CheckBox, CaptionLabel, SubtitleLabel, SimpleCardWidget, FluentIcon as FIF)
import cv2
from app.common.config_manager import get_config
from app.components.highlight_card import HighlightCard

class HighlightInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('HighlightInterface')
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setStyleSheet('QScrollArea, #HighlightInterface { background-color: transparent; border: none; }')
        self.main_layout = QHBoxLayout(self.view)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        self.col1_widget = SimpleCardWidget(self.view)
        self.col1_layout = QVBoxLayout(self.col1_widget)
        self.col1_layout.setContentsMargins(16, 16, 16, 16)
        self.col1_layout.setSpacing(15)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        title_lbl = SubtitleLabel('✂️ Quản Lý Cắt Video Ngắn Chỉ Với 1 Click', self.col1_widget)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)
        self.chk_all = CheckBox('Chọn tất cả', self.col1_widget)
        self.chk_all.setChecked(True)
        self.chk_all.stateChanged.connect(self._toggle_all)
        self.btn_delete = PushButton(FIF.DELETE, 'XÓA MỤC ĐÃ CHỌN', self.col1_widget)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_start = PushButton('BẮT ĐẦU CẮT (AUTO)', self.col1_widget)
        self.btn_start.setFixedHeight(32)
        self.btn_start.setStyleSheet('\n            QPushButton {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);\n                color: white; font-weight: bold; border-radius: 4px; border: none; padding: 0 16px;\n            }\n            QPushButton:hover {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);\n            }\n            QPushButton:disabled { background: #475569; color: #94A3B8; }\n        ')
        self.btn_start.clicked.connect(self._start_batch)
        header_layout.addWidget(self.chk_all)
        header_layout.addWidget(self.btn_delete)
        header_layout.addWidget(self.btn_start)
        self.col1_layout.addLayout(header_layout)
        from qfluentwidgets import FlowLayout
        self.grid_widget = QWidget(self.col1_widget)
        self.grid_layout = FlowLayout(self.grid_widget, isTight=False)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.col1_layout.addWidget(self.grid_widget)
        self.col1_layout.addStretch(1)
        self.main_layout.addWidget(self.col1_widget)
        self.cards = []
        self.is_running = False
        self.queue = []

    def showEvent(self, event):
        super().showEvent(event)
        self._scan_videos()

    def _open_output_folder(self):
        target_dir = get_config('output_dir', '')
        if target_dir and os.path.exists(target_dir):
            os.startfile(target_dir)

    def _scan_videos(self):
        self.grid_layout.removeAllWidgets()
        for card in self.cards:
            card.cleanup()
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        target_dir = get_config('output_dir', '')
        if not target_dir or not os.path.exists(target_dir):
            print('Thư mục không tồn tại')
            lbl = QLabel('Vui lòng cấu hình thư mục Output trong Cài đặt.', self)
            self.grid_layout.addWidget(lbl)
            return
        valid_videos = highlight_manager.scan_highlight_videos(target_dir)
        if not valid_videos:
            lbl = QLabel('Không tìm thấy video nào đã xử lý xong! Vui lòng chạy AUTO FULL trước.', self)
            lbl.setStyleSheet('color: #FCA5A5; font-size: 14px;')
            self.grid_layout.addWidget(lbl)
            return
        for idx, item in enumerate(valid_videos):
            card = HighlightCard(item, self.grid_widget)
            self.grid_layout.addWidget(card)
            self.cards.append(card)
            QTimer.singleShot(10 * idx, card.load_thumbnail)

    def _toggle_all(self, state):
        for card in self.cards:
            if card.checkbox.isEnabled():
                card.checkbox.setChecked(state)

    def _delete_selected(self):
        from PyQt6.QtWidgets import QMessageBox
        selected = [c for c in self.cards if c.checkbox.isChecked() if c.data['existing_hl']]
        if not selected:
            InfoBar.warning('Thông báo', 'Hãy chọn ít nhất 1 video đã có Highlight để xóa!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        reply = QMessageBox.warning(self, 'Cảnh báo', f'Bạn có chắc muốn XÓA BỎ Highlight của {len(selected)} video ĐÃ CHỌN để làm lại không?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for card in selected:
                success = highlight_manager.delete_highlight_data(card.data['ws_dir'], card.data['data_dir'])
                if success:
                    card.data['existing_hl'] = []
                    card.btn_frame.hide()
                    card.lbl_status.setText('Chưa xử lý')
                    card.lbl_status.setStyleSheet('color: #94A3B8;')
                    card.setStyleSheet('\n                        #HighlightCard {\n                            background-color: #1E293B;\n                            border-radius: 8px;\n                            border: none;\n                        }\n                    ')
                    card.checkbox.setChecked(True)

    def _start_batch(self):
        selected = [c for c in self.cards if c.checkbox.isChecked() if not c.data['existing_hl']]
        if not selected:
            InfoBar.warning('Lỗi', 'Vui lòng chọn ít nhất 1 video chưa cắt!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        main_win = self.window()
        api_keys = main_win.settingInterface.get_gemini_keys() if hasattr(main_win, 'settingInterface') else []
        if not api_keys:
            InfoBar.error('Lỗi', 'Vui lòng nhập API Key Gemini trong Cài đặt!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        self.queue = selected
        for c in selected:
            c.lbl_status.setText('Chờ xử lý')
            c.lbl_status.setStyleSheet('color: #CBD5E1;')
        self.btn_start.setEnabled(False)
        self.btn_start.setText('⏳ ĐANG CẮT...')
        self.chk_all.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.api_key = api_keys[0]
        self._process_next()

    def _process_next(self):
        if not self.queue:
            self.btn_start.setEnabled(True)
            self.btn_start.setText('✂️ BẮT ĐẦU CẮT (AUTO)')
            self.chk_all.setEnabled(True)
            self.btn_delete.setEnabled(True)
            InfoBar.success('Hoàn tất', 'Đã chạy xong toàn bộ danh sách Highlight!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        card = self.queue.pop(0)
        card.checkbox.setEnabled(False)
        card.lbl_status.setText('Đang xử lý...')
        card.lbl_status.setStyleSheet('color: #FBBF24;')
        from app.common.workers import HighlightAutoCutterWorker
        self.worker = HighlightAutoCutterWorker(card.data['dubbed_video'], card.data['srt_path'], self.api_key, card.data['ws_dir'], self)
        def on_finished(result):
            card.data['existing_hl'] = result
            card.btn_frame.show()
            card.lbl_status.setText(f'Hoàn thành ({len(result)} đoạn)!')
            card.lbl_status.setStyleSheet('color: #10B981; font-weight: bold;')
            card.setStyleSheet('\n                #HighlightCard {\n                    background-color: #1E293B;\n                    border-radius: 8px;\n                    border: 2px solid #10B981;\n                }\n            ')
            card.checkbox.setChecked(False)
            card.checkbox.setEnabled(True)
            if self.queue:
                next_card = self.queue[0]
                next_card.lbl_status.setText('Đang xử lý...')
                next_card.lbl_status.setStyleSheet('color: #FBBF24;')
            QTimer.singleShot(6000, self._process_next)

        def on_error(err):
            card.lbl_status.setText(f'Lỗi: {err}')
            card.lbl_status.setStyleSheet('color: #EF4444;')
            card.checkbox.setEnabled(True)
            if self.queue:
                next_card = self.queue[0]
                next_card.lbl_status.setText('Đang xử lý...')
                next_card.lbl_status.setStyleSheet('color: #FBBF24;')
            QTimer.singleShot(2000, self._process_next)

        self.worker.finished.connect(on_finished)
        self.worker.error.connect(on_error)
        self.worker.start()


