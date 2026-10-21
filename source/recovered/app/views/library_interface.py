import os
import shutil
import cv2
from PyQt6.QtCore import (Qt, pyqtSignal, QThread, QTimer)
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QSizePolicy)
from PyQt6.QtGui import QImage, QPixmap
from qfluentwidgets import (ScrollArea, SimpleCardWidget, PushButton, PrimaryPushButton, TransparentToolButton, SubtitleLabel, BodyLabel, InfoBar, InfoBarPosition, FlowLayout)
from qfluentwidgets import FluentIcon as FIF
from app.common.config_manager import get_config

class ThumbnailWorker(QThread):
    thumbnail_ready = pyqtSignal(str, QImage)
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self._stopped = False

    def run(self):
        if self._stopped:
            return
        try:
            cap = cv2.VideoCapture(self.video_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                return
            cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
            ret, frame = cap.read()
            cap.release()
            if ret:
                if not self._stopped:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame.shape
                    bytes_per_line = ch * w
                    qt_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    qt_img_copy = qt_img.copy()
                    if not self._stopped:
                        self.thumbnail_ready.emit(self.video_path, qt_img_copy)
                        return
                        return
                        return
        except Exception:
            pass

    def safe_stop(self):
        self._stopped = True
        self.thumbnail_ready.disconnect()


class VideoCard(SimpleCardWidget):
    card_clicked = pyqtSignal(str)
    deleted = pyqtSignal(str)
    title_requested = pyqtSignal(object, str)
    def __init__(self, video_path, workspace_path, status='completed', parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.workspace_path = workspace_path
        self.status = status
        self.thumb_worker = None
        self.setFixedSize(260, 250)
        self.setStyleSheet('\n            VideoCard {\n                background-color: #1E293B;\n                border-radius: 8px;\n                border: 1px solid #334155;\n            }\n            VideoCard:hover {\n                border: 1px solid #0EA5E9;\n            }\n        ')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.lbl_thumb = QLabel(self)
        self.lbl_thumb.setFixedHeight(146)
        self.lbl_thumb.setStyleSheet('background-color: #0F172A; border-top-left-radius: 8px; border-top-right-radius: 8px; color: #475569; font-size: 12px;')
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setText('⏳ Đang tải...')
        layout.addWidget(self.lbl_thumb)
        info_container = QWidget(self)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(12, 10, 12, 12)
        info_layout.setSpacing(8)
        if self.status == 'processing':
            name = os.path.basename(workspace_path).replace('_vietsub_', '')
        else:
            name = os.path.basename(video_path)
        if len(name) > 30:
            name = name[:27] + '...'
        self.lbl_name = BodyLabel(name, self)
        self.lbl_name.setWordWrap(False)
        self.lbl_name.setStyleSheet('font-weight: 600; font-size: 13px; color: #F1F5F9;')
        info_layout.addWidget(self.lbl_name)
        btn_row1 = QHBoxLayout()
        btn_row1.setContentsMargins(0, 0, 0, 0)
        btn_row1.setSpacing(8)
        self.btn_open_folder = TransparentToolButton(FIF.FOLDER, self)
        self.btn_open_folder.setToolTip('Mở thư mục')
        self.btn_open_folder.setFixedSize(28, 28)
        self.btn_open_folder.clicked.connect(self._open_folder)
        if self.status == 'processing':
            self.lbl_thumb.setText('⏳ Đang xử lý dở...')
            self.lbl_thumb.setStyleSheet('background-color: #450A0A; border-top-left-radius: 8px; border-top-right-radius: 8px; color: #FCA5A5; font-size: 12px; font-weight: bold;')
            self.btn_play = PushButton('Xóa Cache', self)
            self.btn_play.setFixedHeight(28)
            self.btn_play.setStyleSheet('\n                QPushButton { background-color: #7F1D1D; color: #FCA5A5; font-weight: bold; border-radius: 4px; border: none; }\n                QPushButton:hover { background-color: #991B1B; }\n            ')
            self.btn_play.clicked.connect(self._delete_workspace)
        else:
            self.btn_play = PrimaryPushButton(FIF.PLAY, 'Phát', self)
            self.btn_play.setFixedHeight(28)
            self.btn_play.clicked.connect((lambda: self.card_clicked.emit(self.video_path)))
        self.btn_delete = TransparentToolButton(FIF.DELETE, self)
        self.btn_delete.setToolTip('Xóa dự án')
        self.btn_delete.setFixedSize(28, 28)
        self.btn_delete.clicked.connect(self._delete_workspace)
        btn_row1.addWidget(self.btn_open_folder)
        btn_row1.addWidget(self.btn_play, stretch=1)
        if self.status != 'processing':
            btn_row1.addWidget(self.btn_delete)
        else:
            self.btn_delete.hide()
        info_layout.addLayout(btn_row1)
        title_cache = os.path.join(self.workspace_path, 'Data', 'title_idea_cache.json')
        has_title = os.path.exists(title_cache)
        self.btn_title = PushButton('👁️ Xem Tiêu Đề' if has_title else '🪄 Tạo Tiêu Đề', self)
        self.btn_title.setFixedHeight(28)
        if has_title:
            self.btn_title.setStyleSheet('\n                QPushButton {\n                    background-color: #064E3B; color: #34D399; font-weight: bold;\n                    border-radius: 4px; font-size: 12px; padding: 0 8px; border: none;\n                }\n                QPushButton:hover { background-color: #065F46; }\n            ')
        else:
            self.btn_title.setStyleSheet('\n                QPushButton {\n                    background-color: #164E63; color: #22D3EE; font-weight: bold;\n                    border-radius: 4px; font-size: 12px; padding: 0 8px; border: none;\n                }\n                QPushButton:hover { background-color: #155E75; }\n            ')
        self.btn_title.clicked.connect((lambda: self.title_requested.emit(self, self.workspace_path)))
        if self.status == 'processing':
            self.btn_title.setEnabled(False)
            self.btn_title.setText('')
            self.btn_title.setIcon(FIF.CANCEL)
            self.btn_title.setStyleSheet('background-color: #334155; color: #64748B; border-radius: 4px;')
        info_layout.addWidget(self.btn_title)
        layout.addWidget(info_container)
        if self.status == 'completed' and self.video_path:
            self._start_thumb_load()

    def _start_thumb_load(self):
        self.thumb_worker = ThumbnailWorker(self.video_path, self)
        self.thumb_worker.thumbnail_ready.connect(self._on_thumb_ready)
        self.thumb_worker.start()

    def _on_thumb_ready(self, path, qimage):
        pixmap = QPixmap.fromImage(qimage)
        pixmap = pixmap.scaled(258, 146, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self.lbl_thumb.setPixmap(pixmap)

    def _open_folder(self):
        import subprocess
        if getattr(self, 'video_path', None) and os.path.exists(self.video_path):
            subprocess.run(['explorer', '/select,', os.path.normpath(self.video_path)])
            return
        os.startfile(self.workspace_path)

    def _delete_workspace(self):
        self.deleted.emit(self.workspace_path)

    def cleanup(self):
        '''Dừng thread thumbnail an toàn trước khi widget bị xóa.'''

        if self.thumb_worker and self.thumb_worker.isRunning():
            try:
                self.thumb_worker.safe_stop()
                self.thumb_worker.quit()
                self.thumb_worker.wait(500)
            except RuntimeError:
                pass
        self.thumb_worker = None


class LibraryInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.hBoxLayout = QHBoxLayout(self.view)
        self._cards = []
        self.view.setObjectName('libraryInterface')
        self.setObjectName('libraryInterface')
        self.ai_queue = []
        self.is_ai_running = False
        self.current_ai_worker = None
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.view.setMinimumWidth(900)
        self._initWidget()
        self.setWidget(self.view)
        self.setStyleSheet('QScrollArea, #libraryInterface { background-color: transparent; border: none; }')

    def _initWidget(self):
        self.hBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.hBoxLayout.setSpacing(20)
        self.col1_widget = SimpleCardWidget(self.view)
        self.col1_layout = QVBoxLayout(self.col1_widget)
        self.col1_layout.setContentsMargins(16, 16, 16, 16)
        header_layout = QHBoxLayout()
        lbl_header = SubtitleLabel('📂 Danh Sách Video Đã Dịch', self.col1_widget)
        header_layout.addWidget(lbl_header)
        header_layout.addStretch(1)
        self.btn_refresh = PushButton(FIF.SYNC, 'Làm mới', self.col1_widget)
        self.btn_refresh.clicked.connect(self._safe_reload)
        header_layout.addWidget(self.btn_refresh)
        self.btn_open_all = PushButton(FIF.FOLDER, 'Mở thư mục', self.col1_widget)
        self.btn_open_all.clicked.connect(self._open_output_folder)
        header_layout.addWidget(self.btn_open_all)
        self.col1_layout.addLayout(header_layout)
        self.col1_layout.addSpacing(10)
        self.grid_scroll = ScrollArea(self.col1_widget)
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setStyleSheet('QScrollArea { background-color: transparent; border: none; }')
        from qfluentwidgets import FlowLayout
        self.grid_container = QWidget()
        self.grid_layout = FlowLayout(self.grid_container, isTight=False)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.grid_scroll.setWidget(self.grid_container)
        self.col1_layout.addWidget(self.grid_scroll, stretch=1)
        self.hBoxLayout.addWidget(self.col1_widget)
        self.load_videos()

    def _open_output_folder(self):
        output_dir = get_config('output_dir', '')
        if output_dir and os.path.exists(output_dir):
            os.startfile(output_dir)
            return
        InfoBar.warning(title='Lỗi', content='Thư mục đầu ra chưa tồn tại hoặc chưa được thiết lập.', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self.window())

    def _safe_reload(self):
        '''
        Dừng toàn bộ QThread thumbnail trước, sau đó mới xóa widget.
        Tránh crash do Qt hủy object đang chạy thread.
        '''

        self.btn_refresh.setEnabled(False)
        self._cleanup_cards()
        QTimer.singleShot(100, self._do_reload)

    def _do_reload(self):
        self.load_videos()
        self.btn_refresh.setEnabled(True)

    def _cleanup_cards(self):
        '''Dọn dẹp toàn bộ VideoCard + thread thumbnail an toàn.'''

        self.grid_layout.removeAllWidgets()
        for card in self._cards:
            card.cleanup()
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def load_videos(self):
        self._cleanup_cards()
        output_dir = get_config('output_dir', '')
        if not output_dir or not os.path.exists(output_dir):
            lbl = BodyLabel('Chưa có thư mục xuất file hoặc thư mục trống.')
            lbl.setStyleSheet('color: #94A3B8; font-size: 14px;')
            self.grid_layout.addWidget(lbl)
            return
        valid_projects = []
        for d in os.listdir(output_dir):
            ws_path = os.path.join(output_dir, d)
            if os.path.isdir(ws_path):
                try:
                    mp4s = [f for f in os.listdir(ws_path)
                         if f.lower().endswith('.mp4')
                         if '_dubbed' in f.lower()]
                    if mp4s:
                        valid_projects.append((os.path.join(ws_path, mp4s[0]), ws_path, 'completed'))
                    elif os.path.exists(os.path.join(ws_path, 'Data')):
                        valid_projects.append((None, ws_path, 'processing'))
                except (PermissionError, OSError):
                    pass
        valid_projects.sort(key=(lambda x: os.path.getmtime(x[1])), reverse=True)
        if not valid_projects:
            lbl = BodyLabel('Chưa có dự án nào hoàn thành!')
            lbl.setStyleSheet('color: #94A3B8; font-size: 14px;')
            self.grid_layout.addWidget(lbl)
            return
        for idx, (video_path, ws_path, status) in enumerate(valid_projects):
            card = VideoCard(video_path, ws_path, status, self.grid_container)
            card.card_clicked.connect(self.play_video)
            card.deleted.connect(self.delete_workspace)
            card.title_requested.connect(self.request_ai_titles)
            self.grid_layout.addWidget(card)
            self._cards.append(card)

    def play_video(self, video_path):
        try:
            os.startfile(video_path)
        except Exception as e:
            InfoBar.error('Lỗi', f'Không thể mở video: {e}', parent=self.window(), position=InfoBarPosition.TOP)
            return

    def delete_workspace(self, ws_path):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self.window(), 'Xác nhận', 'Bạn có chắc muốn xóa dự án này không?\n\nToàn bộ thư mục dự án sẽ bị xóa vĩnh viễn!', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(ws_path)
                InfoBar.success('Thành công', 'Đã xóa dự án!', parent=self.window(), position=InfoBarPosition.TOP)
                self._safe_reload()
            except Exception as e:
                InfoBar.error('Lỗi', f'Không thể xóa: {e}', parent=self.window(), position=InfoBarPosition.TOP)
                return

    def _get_api_keys(self):
        main_win = self.window()
        if hasattr(main_win, 'settingInterface'):
            return main_win.settingInterface.get_gemini_keys()
        return []

    def process_next_ai_task(self):
        if self.is_ai_running or not self.ai_queue:
            return
        self.is_ai_running = True
        task = self.ai_queue.pop(0)
        if task['type'] == 'title':
            self._run_title_worker(task)

    def finish_ai_task(self):
        '''Called when an AI worker finishes (success or error).
           Sets a cooldown timer to respect Gemini API rate limits (15 RPM = 4s/req).'''

        if self.ai_queue:
            QTimer.singleShot(6000, self._release_cooldown_and_next)
            return
        self.is_ai_running = False

    def _release_cooldown_and_next(self):
        self.is_ai_running = False
        self.process_next_ai_task()

    def request_ai_titles(self, card, ws_path):
        import json
        cache_file = os.path.join(ws_path, 'Data', 'title_idea_cache.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                from app.views.ai_dialogs import TitleDialog
                dlg = TitleDialog(data, ws_path, self.window())
                def on_regen():
                    if card:
                        try:
                            card.btn_title.setStyleSheet('\n                                QPushButton {\n                                    background-color: #164E63; color: #22D3EE; font-weight: bold;\n                                    border-radius: 6px; font-size: 12px; padding: 0 8px;\n                                }\n                                QPushButton:hover { background-color: #155E75; }\n                            ')
                        except RuntimeError:
                            pass
                    self.request_ai_titles(card, ws_path)

                dlg.regenerate_requested.connect(on_regen)
                dlg.exec()
                return
            except Exception:
                pass
        if card:
            try:
                card.btn_title.setEnabled(False)
                card.btn_title.setText('Chờ xử lý')
            except RuntimeError:
                pass
        self.ai_queue.append({'type': 'title', 'ws_path': ws_path, 'card': card})
        if self.is_ai_running:
            InfoBar.success('Đã xếp hàng', 'Yêu cầu tạo Tiêu Đề đã được đưa vào hàng chờ.', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        self.process_next_ai_task()

    def _run_title_worker(self, task):
        ws_path = task['ws_path']
        card = task.get('card')
        api_keys = self._get_api_keys()
        if not api_keys:
            self.is_ai_running = False
            self.process_next_ai_task()
            if card:
                try:
                    card.btn_title.setEnabled(True)
                    card.btn_title.setText('🪄 Tiêu Đề AI')
                except RuntimeError:
                    pass
            InfoBar.warning('Lỗi', 'Vui lòng nhập API Key Gemini trong Cài đặt!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        srt_path = os.path.join(ws_path, 'Data', 'temp_translated.srt')
        if not os.path.exists(srt_path):
            self.is_ai_running = False
            self.process_next_ai_task()
            if card:
                try:
                    card.btn_title.setEnabled(True)
                    card.btn_title.setText('🪄 Tiêu Đề AI')
                except RuntimeError:
                    pass
            InfoBar.error('Lỗi', 'Không tìm thấy file kịch bản dịch của video này!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            return
        from app.common.workers import TitleWorker
        self.current_ai_worker = TitleWorker(srt_path, api_keys[0], ws_path, self)
        self.btn_refresh.setEnabled(False)
        if card:
            try:
                card.btn_title.setText('Chờ xử lý')
            except RuntimeError:
                pass
        InfoBar.info('Đang xử lý', f'AI đang suy nghĩ tiêu đề... (Còn {len(self.ai_queue)} tác vụ chờ)', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
        def on_finished(result):
            self.btn_refresh.setEnabled(True)
            if card:
                try:
                    card.btn_title.setEnabled(True)
                    card.btn_title.setText('👁️ Xem Tiêu Đề')
                    card.btn_title.setStyleSheet('\n                        QPushButton {\n                            background-color: #064E3B; color: #34D399; font-weight: bold;\n                            border-radius: 6px; font-size: 12px; padding: 0 8px;\n                        }\n                        QPushButton:hover { background-color: #065F46; }\n                    ')
                except RuntimeError:
                    pass
            self.finish_ai_task()
            InfoBar.success('Hoàn tất', 'Đã tạo xong Tiêu Đề AI!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)

        def on_error(err):
            self.btn_refresh.setEnabled(True)
            if card:
                try:
                    card.btn_title.setEnabled(True)
                    card.btn_title.setText('🪄 Tạo Tiêu Đề')
                except RuntimeError:
                    pass
            self.finish_ai_task()
            InfoBar.error('Lỗi AI', err, parent=self.window(), position=InfoBarPosition.TOP, duration=7000)

        def on_log(msg, overwrite):
            pass

        def on_progress(val):
            if card:
                try:
                    card.btn_title.setText(f'⏳ T.Đề {val}%')
                except RuntimeError:
                    pass

        self.current_ai_worker.finished.connect(on_finished)
        self.current_ai_worker.error.connect(on_error)
        self.current_ai_worker.log.connect(on_log)
        self.current_ai_worker.progress.connect(on_progress)
        self.current_ai_worker.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._safe_reload()


