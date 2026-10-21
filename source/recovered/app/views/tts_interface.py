import os
import re
import time
import base64
import random
import requests
import wave
import subprocess
import concurrent.futures
from PyQt6.QtCore import (Qt, pyqtSignal, QThread, QUrl)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QLabel)
from qfluentwidgets import (ScrollArea, SubtitleLabel, BodyLabel, PlainTextEdit, PushButton, FluentIcon as FIF, InfoBar, InfoBarPosition, SimpleCardWidget, PrimaryPushButton, ComboBox, LineEdit, DoubleSpinBox, ProgressBar, ListWidget, Slider)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import imageio_ffmpeg
from app.common.config_manager import get_config, set_config
from app.common.language_data import LANGUAGE_VOICES
from app.core.audio_generator import fix_pronunciation
from app.core.tts_core import TTSWorker

class TTSInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('ttsInterface')
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(40, 40, 40, 40)
        self.vBoxLayout.setSpacing(20)
        title = SubtitleLabel('Công Cụ Chuyển Văn Bản Thành Giọng Nói (TTS)', self.view)
        font = title.font()
        font.setPointSize(24)
        title.setFont(font)
        self.vBoxLayout.addWidget(title)
        self.card = SimpleCardWidget(self.view)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)
        lbl_text = BodyLabel('Nội dung cần đọc:', self.card)
        card_layout.addWidget(lbl_text)
        self.text_edit = PlainTextEdit(self.card)
        self.text_edit.setPlaceholderText('Nhập văn bản vào đây...')
        self.text_edit.setMinimumHeight(200)
        self.text_edit.textChanged.connect(self._on_text_changed)
        card_layout.addWidget(self.text_edit)
        self.char_count_lbl = BodyLabel('0 / 10000 ký tự', self.card)
        self.char_count_lbl.setStyleSheet('color: gray; font-size: 12px;')
        card_layout.addWidget(self.char_count_lbl, 0, Qt.AlignmentFlag.AlignRight)
        opt_layout = QHBoxLayout()
        opt_layout.setSpacing(20)
        lang_layout = QVBoxLayout()
        lang_layout.addWidget(BodyLabel('Ngôn ngữ:', self.card))
        self.cb_lang = ComboBox(self.card)
        self.cb_lang.addItems(list(LANGUAGE_VOICES.keys()))
        self.cb_lang.currentTextChanged.connect(self._on_lang_changed)
        lang_layout.addWidget(self.cb_lang)
        opt_layout.addLayout(lang_layout, 1)
        voice_layout = QVBoxLayout()
        voice_layout.addWidget(BodyLabel('Loại giọng:', self.card))
        self.cb_voice = ComboBox(self.card)
        voice_layout.addWidget(self.cb_voice)
        opt_layout.addLayout(voice_layout, 2)
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(BodyLabel('Tốc độ (0.5x - 2.0x):', self.card))
        self.spin_speed = DoubleSpinBox(self.card)
        self.spin_speed.setRange(0.5, 2.0)
        self.spin_speed.setSingleStep(0.1)
        self.spin_speed.setValue(1.0)
        speed_layout.addWidget(self.spin_speed)
        opt_layout.addLayout(speed_layout, 1)
        card_layout.addLayout(opt_layout)
        out_layout = QHBoxLayout()
        out_layout.addWidget(BodyLabel('Thư mục lưu:', self.card))
        self.line_output = LineEdit(self.card)
        default_dir = get_config('tts_output_dir', os.path.join(os.path.expanduser('~'), 'Desktop'))
        self.line_output.setText(default_dir)
        out_layout.addWidget(self.line_output, 1)
        btn_browse = PushButton(FIF.FOLDER, 'Chọn nơi lưu', self.card)
        btn_browse.clicked.connect(self._browse_output)
        out_layout.addWidget(btn_browse)
        btn_open = PushButton(FIF.DOCUMENT, 'Mở thư mục', self.card)
        btn_open.clicked.connect(self._open_output_dir)
        out_layout.addWidget(btn_open)
        card_layout.addLayout(out_layout)
        run_layout = QHBoxLayout()
        self.progress_bar = ProgressBar(self.card)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.lbl_status = BodyLabel('', self.card)
        self.btn_run = PrimaryPushButton(FIF.PLAY, 'Tạo Audio', self.card)
        self.btn_run.setFixedWidth(150)
        self.btn_run.clicked.connect(self._start_tts)
        run_layout.addWidget(self.progress_bar, 1)
        run_layout.addWidget(self.lbl_status)
        run_layout.addWidget(self.btn_run)
        card_layout.addLayout(run_layout)
        self.vBoxLayout.addWidget(self.card)
        self.history_card = SimpleCardWidget(self.view)
        history_layout = QVBoxLayout(self.history_card)
        history_layout.setContentsMargins(20, 20, 20, 20)
        history_layout.setSpacing(15)
        history_layout.addWidget(SubtitleLabel('Lịch sử File đã tạo', self.history_card))
        from qfluentwidgets import CaptionLabel
        lbl_hint = CaptionLabel('Gợi ý: Dùng phím Ctrl + Click, Shift + Click hoặc Ctrl + A để chọn nhiều file khi xóa. Nhấp đúp (Double-click) để phát nhanh.', self.history_card)
        lbl_hint.setStyleSheet('color: gray;')
        history_layout.addWidget(lbl_hint)
        self.list_history = ListWidget(self.history_card)
        self.list_history.setFixedHeight(150)
        from PyQt6.QtWidgets import QAbstractItemView
        self.list_history.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_history.itemDoubleClicked.connect(self._toggle_play)
        self.list_history.currentItemChanged.connect(self._stop_audio)
        history_layout.addWidget(self.list_history)
        hist_btn_layout = QHBoxLayout()
        self.btn_play = PushButton(FIF.PLAY, 'Phát', self.history_card)
        self.btn_delete = PushButton(FIF.DELETE, 'Xóa', self.history_card)
        self.btn_refresh = PushButton(FIF.SYNC, 'Làm mới', self.history_card)
        self.slider_vol = Slider(Qt.Orientation.Horizontal, self.history_card)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(100)
        self.slider_vol.setFixedWidth(100)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_refresh.clicked.connect(self._refresh_history)
        self.slider_vol.valueChanged.connect((lambda v: None))
        hist_btn_layout.addWidget(self.btn_play)
        hist_btn_layout.addWidget(self.btn_delete)
        hist_btn_layout.addWidget(self.btn_refresh)
        hist_btn_layout.addStretch(1)
        hist_btn_layout.addWidget(BodyLabel('Âm lượng:', self.history_card))
        hist_btn_layout.addWidget(self.slider_vol)
        history_layout.addLayout(hist_btn_layout)
        self.vBoxLayout.addWidget(self.history_card)
        self.vBoxLayout.addStretch(1)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setStyleSheet('QScrollArea, #ttsInterface { background-color: transparent; border: none; }')
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._on_lang_changed(self.cb_lang.currentText())
        self.worker = None
        self._refresh_history()

    def _on_text_changed(self):
        text = self.text_edit.toPlainText()
        max_length = 10000
        current_len = len(text)
        self.char_count_lbl.setText(f'{current_len} / {max_length} ký tự')
        if current_len > max_length:
            self.char_count_lbl.setStyleSheet('color: red; font-weight: bold; font-size: 12px;')
            self.btn_run.setEnabled(False)
            return
        self.char_count_lbl.setStyleSheet('color: gray; font-size: 12px;')
        self.btn_run.setEnabled(True)

    def _on_lang_changed(self, lang):
        self.cb_voice.clear()
        voices = LANGUAGE_VOICES.get(lang, [])
        for v in voices:
            self.cb_voice.addItem(v['name'], userData=v['code'])

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục lưu Audio', self.line_output.text())
        if path:
            self.line_output.setText(path)
            set_config('tts_output_dir', path)
            self._refresh_history()

    def _open_output_dir(self):
        path = self.line_output.text().strip()
        if os.path.exists(path):
            try:
                os.startfile(path)
            except:
                pass
            return
        InfoBar.warning('Lỗi', 'Thư mục không tồn tại!', parent=self.window(), position=InfoBarPosition.TOP)

    def _start_tts(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_run.setText('Tạo Audio')
            self.btn_run.setIcon(FIF.PLAY)
            self.lbl_status.setText('Đã hủy.')
            self.progress_bar.hide()
            return
        text = self.text_edit.toPlainText().strip()
        if not text:
            InfoBar.warning('Lỗi', 'Vui lòng nhập nội dung!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        out_dir = self.line_output.text().strip()
        if not out_dir:
            InfoBar.warning('Lỗi', 'Vui lòng chọn thư mục lưu file!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        set_config('tts_output_dir', out_dir)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(out_dir, f'sir_audio_{timestamp}.mp3')
        voice_code = self.cb_voice.currentData()
        lang = self.cb_lang.currentText()
        speed = self.spin_speed.value()
        session_id = get_config('tiktok_session', '')
        self.btn_run.setText('Hủy')
        self.btn_run.setIcon(FIF.CANCEL)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.lbl_status.setText('Đang khởi tạo...')
        self.worker = TTSWorker(text, lang, voice_code, speed, out_path, session_id)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.lbl_status.setText(f'{val}%')

    def _on_finished(self, result, success):
        self.btn_run.setText('Tạo Audio')
        self.btn_run.setIcon(FIF.PLAY)
        self.progress_bar.hide()
        self.lbl_status.setText('')
        if success:
            InfoBar.success('Thành công', f'Đã lưu tại:\n{result}', parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
            self._refresh_history()
            return
        InfoBar.error('Lỗi', f'Không thể tạo âm thanh:\n{result}', parent=self.window(), position=InfoBarPosition.TOP, duration=6000)

    def _refresh_history(self):
        self.list_history.clear()
        out_dir = self.line_output.text().strip()
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import Qt
        if not out_dir or not os.path.exists(out_dir):
            item = QListWidgetItem('Thư mục lưu chưa tồn tại hoặc không hợp lệ.')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_history.addItem(item)
            return
        return
        files.sort(key=(lambda x: os.path.getmtime(os.path.join(out_dir, x))), reverse=True)
        from PyQt6.QtCore import QSize
        for f in files:
            item = QListWidgetItem(self.list_history)
            item.setText(f)
            item.setSizeHint(QSize(0, 40))
            w = QWidget()
            w.setStyleSheet('background: transparent;')
            l = QHBoxLayout(w)
            l.setContentsMargins(10, 0, 10, 0)
            l.addStretch(1)
            btn = TransparentToolButton(FIF.FOLDER, w)
            btn.setToolTip('Mở vị trí file này')
            btn.setFixedSize(30, 30)
            btn.clicked.connect((lambda checked, name=f: self._open_file_location(name)))
            l.addWidget(btn)
            self.list_history.setItemWidget(item, w)
            if files:
                self.list_history.setCurrentRow(0)
                return
            try:
                files = []
                for f in os.listdir(out_dir):
                    if f.endswith('.mp3') or f.endswith('.wav'):
                        files.append(f)
                from qfluentwidgets import TransparentToolButton
                from PyQt6.QtCore import QSize
                if not files:
                    item = QListWidgetItem('Chưa có file âm thanh nào trong thư mục này.')
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.list_history.addItem(item)
            except:
                pass

    def _open_file_location(self, filename):
        out_dir = self.line_output.text().strip()
        path = os.path.join(out_dir, filename)
        if os.path.exists(path):
            subprocess.run(['explorer', '/select,', os.path.normpath(path)])

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
            return
        items = self.list_history.selectedItems()
        if not items:
            item = self.list_history.currentItem()
            if not item:
                InfoBar.warning('Chú ý', 'Vui lòng chọn 1 file để phát!', parent=self.window(), position=InfoBarPosition.TOP)
                return
        else:
            if len(items) > 1:
                InfoBar.warning('Chú ý', 'Chỉ được chọn 1 file để nghe thử!', parent=self.window(), position=InfoBarPosition.TOP)
                return
            item = items[0]
        out_dir = self.line_output.text().strip()
        path = os.path.join(out_dir, item.text())
        if os.path.exists(path):
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setIcon(FIF.PAUSE)
            self.btn_play.setText('Dừng')
            return
        self.btn_play.setIcon(FIF.PLAY)
        self.btn_play.setText('Phát')

    def _stop_audio(self):
        self.player.stop()

    def _delete_selected(self):
        items = self.list_history.selectedItems()
        if not items:
            InfoBar.warning('Chú ý', 'Vui lòng chọn ít nhất 1 file để xóa!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        from qfluentwidgets import MessageBox
        msg_box = MessageBox('Xác nhận xóa', f'Bạn có chắc chắn muốn xóa vĩnh viễn {len(items)} file âm thanh đã chọn không?', self.window())
        msg_box.yesButton.setText('Xóa')
        msg_box.cancelButton.setText('Hủy')
        if not msg_box.exec():
            return
        out_dir = self.line_output.text().strip()
        self.player.stop()
        self.player.setSource(QUrl())
        time.sleep(0.1)
        success_count = 0
        failed_items = []
        for item in items:
            path = os.path.join(out_dir, item.text())
            try:
                if os.path.exists(path):
                    os.remove(path)
                success_count += 1
            except Exception:
                failed_items.append(item.text())
                continue
        self._refresh_history()
        if success_count > 0:
            InfoBar.success('Đã xóa', f'Xóa thành công {success_count} file.', parent=self.window(), position=InfoBarPosition.TOP)
        if failed_items:
            InfoBar.error('Lỗi xóa file', f'Không thể xóa {len(failed_items)} file (có thể đang được mở).', parent=self.window(), position=InfoBarPosition.TOP)


