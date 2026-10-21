import os
from app.core.video_utils import get_video_duration
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFileDialog)
from PyQt6.QtCore import Qt
from qfluentwidgets import (PushButton, InfoBar, InfoBarPosition, PrimaryPushButton, CaptionLabel, SimpleCardWidget, SpinBox, BodyLabel, ProgressBar)
from qfluentwidgets import FluentIcon as FIF
from app.common.workers import SplitterWorker

class SplitterCard(SimpleCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet('\n            SimpleCardWidget {\n                background-color: #1E293B;\n                border-radius: 8px;\n                border: 1px solid #334155;\n            }\n        ')
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(20)
        layout_file = QHBoxLayout()
        self.btn_select = PushButton(FIF.FOLDER, 'Chọn Video MP4', self)
        self.btn_select.clicked.connect(self._select_video)
        self.lbl_file_path = BodyLabel('Chưa có tệp nào được chọn.', self)
        self.lbl_file_path.setStyleSheet('color: #94A3B8;')
        layout_file.addWidget(self.btn_select)
        layout_file.addWidget(self.lbl_file_path, 1)
        card_layout.addLayout(layout_file)
        layout_save = QHBoxLayout()
        self.btn_save_dir = PushButton(FIF.DOWNLOAD, 'Chọn thư mục lưu.', self)
        self.btn_save_dir.clicked.connect(self._select_save_dir)
        self.lbl_save_dir = BodyLabel('Mặc định: Lưu cùng thư mục với video gốc', self)
        self.lbl_save_dir.setStyleSheet('color: #94A3B8;')
        layout_save.addWidget(self.btn_save_dir)
        layout_save.addWidget(self.lbl_save_dir, 1)
        card_layout.addLayout(layout_save)
        layout_params = QHBoxLayout()
        layout_params.addWidget(BodyLabel('Số tập cần chia:', self))
        self.spin_parts = SpinBox(self)
        self.spin_parts.setRange(2, 500)
        self.spin_parts.setValue(5)
        self.spin_parts.valueChanged.connect(self._update_preview)
        layout_params.addWidget(self.spin_parts)
        self.lbl_preview = BodyLabel('', self)
        self.lbl_preview.setStyleSheet('color: #F59E0B; font-weight: bold;')
        layout_params.addWidget(self.lbl_preview, 1)
        card_layout.addLayout(layout_params)
        self.btn_run = PrimaryPushButton(FIF.CUT, 'Bắt đầu cắt', self)
        self.btn_run.clicked.connect(self._run_split)
        card_layout.addWidget(self.btn_run)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.hide()
        card_layout.addWidget(self.progress_bar)
        self.lbl_status = CaptionLabel('', self)
        self.lbl_status.setStyleSheet('color: #10B981;')
        card_layout.addWidget(self.lbl_status)
        self.current_video_path = None
        self.current_save_dir = None
        self.current_duration = 0.0
        self.worker = None

    def _select_video(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn Video', '', 'Video Files (*.mp4 *.mkv *.mov *.avi)')
        if path:
            self.current_video_path = path
            self.lbl_file_path.setText(os.path.basename(path))
            self.current_duration = get_video_duration(path)
            self._update_preview()

    def _select_save_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục lưu tập tin', '')
        if dir_path:
            self.current_save_dir = dir_path
            self.lbl_save_dir.setText(dir_path)
            self.lbl_save_dir.setStyleSheet('color: #10B981;')

    def _update_preview(self):
        if not self.current_video_path or self.current_duration <= 0:
            self.lbl_preview.setText('')
            return
        n = self.spin_parts.value()
        if n < 2:
            self.lbl_preview.setText('Lỗi: Số tập phải >= 2.')
            self.lbl_preview.setStyleSheet('color: #EF4444; font-weight: bold;')
            return
        seg_time = self.current_duration / n
        mins = int(seg_time // 60)
        secs = int(seg_time % 60)
        if seg_time < 10:
            self.lbl_preview.setText(f'Cảnh báo: Mỗi tập chỉ dài {mins}p {secs}s (< 10 giây). KHÔNG HỢP LỆ!')
            self.lbl_preview.setStyleSheet('color: #EF4444; font-weight: bold;')
            return
        total_mins = int(self.current_duration // 60)
        total_secs = int(self.current_duration % 60)
        self.lbl_preview.setText(f'Video gốc: {total_mins}p {total_secs}s -> Mỗi tập dài: {mins}p {secs}s')
        self.lbl_preview.setStyleSheet('color: #10B981; font-weight: bold;')

    def _run_split(self):
        if not self.current_video_path:
            InfoBar.error(title='Lỗi', content='Vui lòng chọn video trước!', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self.window())
            return
        n = self.spin_parts.value()
        if n < 2:
            InfoBar.error(title='Lỗi', content='Số tập bét nhất phải là 2. Chia 1 tập thì chia làm gì ba!', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=4000, parent=self.window())
            return
        seg_time = self.current_duration / n
        if seg_time < 10:
            InfoBar.error(title='Số tập quá lớn', content=f'Thời lượng mỗi tập ({int(seg_time)}s) đang nhỏ hơn 10 giây. Hãy giảm số lượng tập xuống!', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=5000, parent=self.window())
            return
        self.btn_run.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_save_dir.setEnabled(False)
        self.spin_parts.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.lbl_status.setText('Đang khởi tạo...')
        self.worker = SplitterWorker(self.current_video_path, n, self.current_duration, self.current_save_dir, self)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect((lambda msg, _: self.lbl_status.setText(msg)))
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_error(self, err):
        self.lbl_status.setText(f'Lỗi: {err}')
        self.lbl_status.setStyleSheet('color: #EF4444;')
        self._reset_ui()
        InfoBar.error(title='Lỗi khi cắt', content=str(err), orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=5000, parent=self.window())

    def _on_finished(self, out_dir):
        n = self.spin_parts.value()
        self.lbl_status.setText(f'Cắt thành công {n} tập!')
        self.lbl_status.setStyleSheet('color: #10B981;')
        self.progress_bar.setValue(100)
        self._reset_ui()
        InfoBar.success(title='Hoàn tất', content=f'Đã chia video thành công {n} tập!\nLưu tại: {out_dir}', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=6000, parent=self.window())

    def _reset_ui(self):
        self.btn_run.setEnabled(True)
        self.btn_select.setEnabled(True)
        self.btn_save_dir.setEnabled(True)
        self.spin_parts.setEnabled(True)


