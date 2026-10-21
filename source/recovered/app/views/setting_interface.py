import os
import shutil
import subprocess
import psutil
from PyQt6.QtCore import (Qt, QTimer, QThread, pyqtSignal, QUrl)
import requests
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QButtonGroup, QApplication)
from qfluentwidgets import (ScrollArea, CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel, ComboBox, Slider, SwitchButton, PushButton, PrimaryPushButton, InfoBar, InfoBarPosition, LineEdit, TextEdit, CheckBox, SegmentedWidget, ToolButton, IconWidget, HorizontalSeparator, RadioButton)
from qfluentwidgets import FluentIcon as FIF
from app.common.config_manager import load_config, save_config
from app.common import security

class TikTokSessionCheckWorker(QThread):
    result = pyqtSignal(bool, str)
    def __init__(self, session_id, parent=None):
        super().__init__(parent)
        self.session_id = session_id

    def run(self):
        url = 'https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/'
        headers = {'User-Agent': 'com.zhiliaoapp.musically/2022600030', 'Cookie': f'sessionid={self.session_id}'}
        params = {'text_speaker': 'BV074_streaming', 'req_text': 'Test', 'speaker_map_type': 0, 'aid': 1233}
        self.result.emit(False, f'Lỗi kết nối tới TikTok: HTTP {res.status_code}')
        try:
            res = requests.post(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get('message') == 'success' and 'v_str' in data.get('data', {}):
                    self.result.emit(True, 'Session ID TikTok hoạt động!')
                    return
                err_msg = data.get('message', 'Lỗi không xác định')
                self.result.emit(False, f'Session ID đã hết hạn hoặc không hợp lệ. ({err_msg})')
            return
        except Exception as e:
            self.result.emit(False, f'Không thể kiểm tra: {str(e)}')
            return


class ModelDownloaderWorker(QThread):
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    def __init__(self, target_model='all', parent=None):
        super().__init__(parent)
        self.target_model = target_model

    def run(self):
        import subprocess
        import sys
        python_exe = sys.executable
        target_name = 'TẤT CẢ GÓI MỞ RỘNG'
        if self.target_model == 'whisper':
            target_name = 'TẤT CẢ GÓI CHẾ ĐỘ NGHE'
        elif self.target_model == 'whisper_tiny':
            target_name = 'GÓI CHẾ ĐỘ 1'
        elif self.target_model == 'whisper_base':
            target_name = 'GÓI CHẾ ĐỘ 2'
        elif self.target_model == 'whisper_small':
            target_name = 'GÓI CHẾ ĐỘ 3'
        elif self.target_model == 'whisper_medium':
            target_name = 'GÓI CHẾ ĐỘ 4'
        elif self.target_model == 'whisper_large-v3':
            target_name = 'GÓI CHẾ ĐỘ 5'
        elif self.target_model == 'paddleocr':
            target_name = 'GÓI CHẾ ĐỘ 6 (BÓC CHỮ)'
        elif self.target_model == 'demucs':
            target_name = 'GÓI CHẾ ĐỘ PHỤ (TÁCH NHẠC)'
        self.progress.emit(f'BẮT ĐẦU KIỂM TRA VÀ TẢI {target_name}...\n' + '----------------------------------------')
        self.progress.emit('⏳ LƯU Ý: Quá trình tải dữ liệu có thể mất từ 2 - 15 phút tùy tốc độ mạng.\nApp ĐANG TẢI NGẦM và KHÔNG BỊ TREO, vui lòng kiên nhẫn chờ đợi đến khi báo hoàn tất!\n----------------------------------------')
        if self.target_model in ('all', 'whisper', 'whisper_tiny', 'whisper_base', 'whisper_small', 'whisper_medium', 'whisper_large-v3'):
            if self.target_model == 'all':
                self.progress.emit('\n[1/3] Đang xử lý Chế độ Nghe (Lấy Sub)...')
            else:
                self.progress.emit('\nĐang xử lý Chế độ Nghe (Lấy Sub)...')
            from app.common.config_manager import get_hf_cache_dir
            hf_cache_dir = get_hf_cache_dir().replace('\\', '\\\\')
            script_whisper = f'import sys, os, warnings, logging\nos.environ[\'HF_HOME\'] = \'{hf_cache_dir}\'\nos.environ[\'HF_HUB_DISABLE_SYMLINKS\'] = \'1\'\nos.environ[\'HF_HUB_DISABLE_SYMLINKS_WARNING\'] = \'1\'\nos.environ[\'HF_HUB_DISABLE_TELEMETRY\'] = \'1\'\nwarnings.filterwarnings(\'ignore\')\nlogging.getLogger(\'huggingface_hub\').setLevel(logging.ERROR)\ntry:\n    from faster_whisper import WhisperModel\n'
            if self.target_model in ('all', 'whisper', 'whisper_tiny'):
                script_whisper += "    print('Dang kiem tra/tai goi du lieu che do 1...', flush=True)\n    WhisperModel('tiny', device='cpu', compute_type='int8')\n"
            if self.target_model in ('all', 'whisper', 'whisper_base'):
                script_whisper += "    print('Dang kiem tra/tai goi du lieu che do 2...', flush=True)\n    WhisperModel('base', device='cpu', compute_type='int8')\n"
            if self.target_model in ('all', 'whisper', 'whisper_small'):
                script_whisper += "    print('Dang kiem tra/tai goi du lieu che do 3...', flush=True)\n    WhisperModel('small', device='cpu', compute_type='int8')\n"
            if self.target_model in ('all', 'whisper', 'whisper_medium'):
                script_whisper += "    print('Dang kiem tra/tai goi du lieu che do 4...', flush=True)\n    WhisperModel('medium', device='cpu', compute_type='int8')\n"
            if self.target_model in ('all', 'whisper', 'whisper_large-v3'):
                script_whisper += "    print('Dang kiem tra/tai goi du lieu che do 5 (nang nhat)...', flush=True)\n    WhisperModel('large-v3', device='cpu', compute_type='int8')\n"
            script_whisper += "    print('Hoan tat tai Goi Che do Nghe!', flush=True)\nexcept Exception as e:\n    print(f'Loi tai du lieu: {e}', flush=True)\n"
            self._run_script(python_exe, script_whisper)
        if self.target_model in ('all', 'paddleocr'):
            if self.target_model == 'all':
                self.progress.emit('\n[2/3] Đang xử lý Chế độ Bóc chữ...')
            else:
                self.progress.emit('\nĐang xử lý Chế độ Bóc chữ...')
            from app.common.config_manager import get_paddleocr_cache_dir
            paddle_cache_dir = get_paddleocr_cache_dir().replace('\\', '\\\\')
            script_paddle = f'\nimport sys, os, warnings, logging\nos.environ[\'OMP_NUM_THREADS\'] = \'1\'\nos.environ[\'USERPROFILE\'] = \'{paddle_cache_dir}\'\nos.environ[\'HOME\'] = \'{paddle_cache_dir}\'\nos.environ[\'HF_HUB_DISABLE_SYMLINKS_WARNING\'] = \'1\'\nos.environ[\'HF_HUB_DISABLE_TELEMETRY\'] = \'1\'\nwarnings.filterwarnings(\'ignore\')\nlogging.getLogger(\'huggingface_hub\').setLevel(logging.ERROR)\ntry:\n    from paddleocr import PaddleOCR\n    print(\'Dang kiem tra/tai goi du lieu Quet chu (lang=vi)...\', flush=True)\n    PaddleOCR(use_angle_cls=True, lang=\'vi\', use_gpu=False, show_log=False)\n    print(\'Dang kiem tra/tai goi du lieu Quet chu (lang=en)...\', flush=True)\n    PaddleOCR(use_angle_cls=True, lang=\'en\', use_gpu=False, show_log=False)\n    print(\'Hoan tat tai Goi Che do Boc Chu!\', flush=True)\nexcept Exception as e:\n    print(f\'Loi tai du lieu: {{e}}\', flush=True)\n'
            self._run_script(python_exe, script_paddle)
        if self.target_model in ('all', 'demucs'):
            if self.target_model == 'all':
                self.progress.emit('\n[3/3] Đang xử lý Chế độ Tách Nhạc (Xóa tạp âm)...')
            else:
                self.progress.emit('\nĐang xử lý Chế độ Tách Nhạc (Xóa tạp âm)...')
            from app.common.config_manager import get_audio_sep_cache_dir
            audio_sep_cache_dir = get_audio_sep_cache_dir().replace('\\', '\\\\')
            script_demucs = f'\nimport sys, os, warnings\nwarnings.filterwarnings(\'ignore\')\ntry:\n    # Lấy _MEIPASS từ arg hoặc env (vì chạy qua subprocess)\n    ffmpeg_dir = os.environ.get(\'BUNDLE_FFMPEG_DIR\', \'\')\n    if ffmpeg_dir and os.path.exists(ffmpeg_dir):\n        os.environ[\'PATH\'] = ffmpeg_dir + os.pathsep + os.environ.get(\'PATH\', \'\')\n    \n    # Monkey-patch: redirect GitHub raw -> jsDelivr CDN để tránh lỗi 429\n    import urllib.request\n    _orig_urlopen = urllib.request.urlopen\n    def _patched_urlopen(url, *a, **kw):\n        s = url if isinstance(url, str) else (url.full_url if hasattr(url, \'full_url\') else str(url))\n        if \'raw.githubusercontent.com/TRvlvr/application_data\' in s:\n            s = s.replace(\'raw.githubusercontent.com/TRvlvr/application_data/main\', \'cdn.jsdelivr.net/gh/TRvlvr/application_data@main\')\n            if isinstance(url, str): url = s\n            else: url = urllib.request.Request(s, headers=dict(url.headers) if hasattr(url,\'headers\') else {{}})\n        return _orig_urlopen(url, *a, **kw)\n    urllib.request.urlopen = _patched_urlopen\n    \n    import requests as _rq\n    _orig_get = _rq.Session.get\n    def _patched_get(self, url, **kw):\n        if isinstance(url, str) and \'raw.githubusercontent.com/TRvlvr/application_data\' in url:\n            url = url.replace(\'raw.githubusercontent.com/TRvlvr/application_data/main\', \'cdn.jsdelivr.net/gh/TRvlvr/application_data@main\')\n        return _orig_get(self, url, **kw)\n    _rq.Session.get = _patched_get\n\n    from audio_separator.separator import Separator\n    print(\'Dang kiem tra/tai goi du lieu tach nhac (Khoang 250MB)...\', flush=True)\n    cache_dir = \'{audio_sep_cache_dir}\'\n    os.makedirs(cache_dir, exist_ok=True)\n    Separator(output_dir=cache_dir, model_file_dir=cache_dir).load_model(model_filename=\'model_bs_roformer_ep_317_sdr_12.9755.ckpt\')\n    print(\'Dang tai them loi Eco (Khoang 66MB)...\', flush=True)\n    Separator(output_dir=cache_dir, model_file_dir=cache_dir).load_model(model_filename=\'UVR-MDX-NET-Inst_HQ_3.onnx\')\n    print(\'Hoan tat tai Goi Che do Tach Nhac!\', flush=True)\nexcept Exception as e:\n    print(f\'Loi tai du lieu: {{e}}\', flush=True)\n'
            self._run_script(python_exe, script_demucs)
        self.progress.emit('\n========================================\nĐÃ HOÀN TẤT KIỂM TRA VÀ TẢI XUỐNG!')
        self.finished_signal.emit(True)

    def _run_script(self, python_exe, script):
        import subprocess
        import sys
        import os
        env = os.environ.copy()
        if hasattr(sys, '_MEIPASS'):
            ffmpeg_dir = os.path.join(sys._MEIPASS, 'ffmpeg')
            env['BUNDLE_FFMPEG_DIR'] = ffmpeg_dir
        process = subprocess.Popen([python_exe, '-c', script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        for line in process.stdout:
            if line:
                self.progress.emit(line.strip())
        process.wait()


class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('settingInterface')
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        self.scrollArea = ScrollArea(self)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet('QScrollArea, #settingInterface_scroll { background-color: transparent; border: none; }')
        self.view = QWidget(self.scrollArea)
        self.view.setObjectName('settingInterface_scroll')
        self.vBoxLayout = QVBoxLayout(self.view)
        self.view.setMinimumWidth(800)
        self.config = load_config()
        self._is_loading = True
        self.last_checked_session = ''
        self._suppress_popup = True
        self.check_timer = QTimer(self)
        self.check_timer.setSingleShot(True)
        self.check_timer.setInterval(1000)
        self.check_timer.timeout.connect(self._autoCheckTikTokSession)
        self.scrollArea.setWidget(self.view)
        self.mainLayout.addWidget(self.scrollArea)
        self._initWidget()
        self._connectSignals()
        self._loadConfigToUI()
        self._is_loading = False
        QTimer.singleShot(5000, self._enablePopup)

    def _enablePopup(self):
        self._suppress_popup = False

    def _initWidget(self):
        self.vBoxLayout.setContentsMargins(40, 40, 40, 40)
        self.vBoxLayout.setSpacing(20)
        title = SubtitleLabel('Cài đặt chung', self.view)
        font = title.font()
        font.setPointSize(24)
        title.setFont(font)
        self.vBoxLayout.addWidget(title)
        self.pivot = SegmentedWidget(self.view)
        self.vBoxLayout.addWidget(self.pivot)
        self.stackedWidget = QStackedWidget(self.view)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.page_account = QWidget()
        layout_acc = QVBoxLayout(self.page_account)
        layout_acc.setContentsMargins(0, 10, 0, 0)
        layout_acc.setSpacing(20)
        self.group_license = CardWidget(self.page_account)
        layout_license = QVBoxLayout(self.group_license)
        layout_license.setSpacing(15)
        layout_license.setContentsMargins(20, 20, 20, 20)
        acc_header = QHBoxLayout()
        acc_header.setSpacing(15)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'icon.ico')
        icon_widget = IconWidget(icon_path, self.group_license)
        icon_widget.setFixedSize(48, 48)
        acc_header.addWidget(icon_widget)
        acc_info = QVBoxLayout()
        acc_info.setSpacing(2)
        acc_title = SubtitleLabel('Tài khoản luaVietsup')
        self.lbl_license_status = BodyLabel('Trạng thái: Đang kiểm tra...')
        self.lbl_license_status.setStyleSheet('color: #EAB308; font-weight: bold; font-size: 14px;')
        acc_info.addWidget(acc_title)
        acc_info.addWidget(self.lbl_license_status)
        acc_header.addLayout(acc_info)
        acc_header.addStretch(1)
        layout_license.addLayout(acc_header)
        layout_license.addWidget(HorizontalSeparator())
        layout_acc.addWidget(self.group_license)
        self.group_tos = CardWidget(self.page_account)
        layout_tos = QVBoxLayout(self.group_tos)
        layout_tos.setSpacing(10)
        lbl_tos_title = SubtitleLabel('ĐIỀU KHOẢN & CHÍNH SÁCH SỬ DỤNG')
        lbl_tos_title.setStyleSheet('color: #EF4444;')
        layout_tos.addWidget(lbl_tos_title)
        tos_content = "<b>1. Chính Sách Hoàn Tiền:</b><br/>Phần mềm đã được hỗ trợ dùng thử trước khi mua. Việc thanh toán đồng nghĩa với việc bạn đã hiểu rõ và hài lòng với sản phẩm. Chúng tôi từ chối mọi yêu cầu hoàn tiền dưới bất kỳ lý do nào sau khi giao dịch thành công.<br/><br/><b>2. Rủi Ro Từ Nền Tảng Thứ 3:</b><br/>Tool hoạt động phụ thuộc một phần vào thuật toán của bên thứ 3 (TikTok, Google...). Nếu họ quét hoặc đổi thuật toán, chúng tôi không chịu trách nhiệm bồi thường nhưng sẽ nỗ lực ra bản update fix lỗi nhanh nhất có thể.<br/><br/><b>3. Chống Chia Sẻ & Crack:</b><br/>Mỗi bản quyền chỉ gắn với duy nhất 1 máy tính. Mọi hành vi dùng tool bẻ khóa, chia sẻ cho người khác hoặc bán lại phần mềm sẽ dẫn đến việc <span style='color: #EF4444; font-weight: bold;'>KHÓA TÀI KHOẢN VĨNH VIỄN</span> không cần báo trước.<br/><br/><b>4. Miễn Trừ Trách Nhiệm Nội Dung:</b><br/>Người dùng tự chịu trách nhiệm về tính hợp pháp và bản quyền của video/âm thanh khi đăng tải lên mạng xã hội."
        lbl_tos = BodyLabel(tos_content)
        lbl_tos.setWordWrap(True)
        lbl_tos.setStyleSheet('font-size: 13px; line-height: 1.6; color: #E2E8F0;')
        layout_tos.addWidget(lbl_tos)
        layout_acc.addWidget(self.group_tos)
        layout_acc.addStretch(1)
        self.stackedWidget.addWidget(self.page_account)
        self.page_general = QWidget()
        layout_general = QVBoxLayout(self.page_general)
        layout_general.setContentsMargins(0, 10, 0, 0)
        layout_general.setSpacing(20)
        self.group_ai = CardWidget(self.page_general)
        layout_ai = QVBoxLayout(self.group_ai)
        layout_ai.setSpacing(15)
        layout_ai.addWidget(SubtitleLabel('Cấu hình Trích xuất Phụ đề'))
        warning_lbl = BodyLabel('Lưu ý: Nếu App bị văng (Crash) trong lúc xử lý video dài, vui lòng hạ xuống Chế độ thấp hơn!')
        warning_lbl.setStyleSheet('color: #FF5C5C; font-weight: bold;')
        layout_ai.addWidget(warning_lbl)
        self.model_btn_group = QButtonGroup(self.group_ai)
        self.radio_model_1 = RadioButton('Chế độ 1 (Bóc Âm Thanh): Tốc Độ Bàn Thờ', self.group_ai)
        self.radio_model_1.setProperty('model_val', 'tiny')
        self.lbl_desc_1 = BodyLabel('Cần trống tối thiểu: > 0.3GB VRAM Card Đồ Họa (GPU) HOẶC > 0.5GB RAM Hệ thống (CPU)\n• Nhanh và Yếu: Nhẹ máy nhất, tốc độ siêu tốc. AI sơ cấp, hay bị lặp từ hoặc cắt vụn câu thoại.', self.group_ai)
        self.lbl_desc_1.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px;')
        self.lbl_desc_1.setWordWrap(True)
        self.radio_model_2 = RadioButton('Chế độ 2 (Bóc Âm Thanh): Siêu Tốc', self.group_ai)
        self.radio_model_2.setProperty('model_val', 'base')
        self.lbl_desc_2 = BodyLabel('Cần trống tối thiểu: > 0.5GB VRAM Card Đồ Họa (GPU) HOẶC > 1.0GB RAM Hệ thống (CPU)\n• Nhanh và Yếu: Bám sát tốt hơn Chế độ 1 nhưng vẫn có thể sai sót ở những đoạn có nhiều tạp âm.', self.group_ai)
        self.lbl_desc_2.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px;')
        self.lbl_desc_2.setWordWrap(True)
        self.radio_model_3 = RadioButton('Chế độ 3 (Bóc Âm Thanh): Cân Bằng', self.group_ai)
        self.radio_model_3.setProperty('model_val', 'small')
        self.lbl_desc_3 = BodyLabel('Cần trống tối thiểu: > 1.0GB VRAM Card Đồ Họa (GPU) HOẶC > 1.0GB RAM Hệ thống (CPU)\n• Tầm Trung Bình: Cân bằng hoàn hảo giữa Tốc độ và Độ chuẩn xác. Lấy chuẩn phần lớn lời thoại.', self.group_ai)
        self.lbl_desc_3.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px;')
        self.lbl_desc_3.setWordWrap(True)
        self.radio_model_4 = RadioButton('Chế độ 4 (Bóc Âm Thanh): Rõ Nét', self.group_ai)
        self.radio_model_4.setProperty('model_val', 'medium')
        self.lbl_desc_4 = BodyLabel('Cần trống tối thiểu: > 1.8GB VRAM Card Đồ Họa (GPU) HOẶC > 2.0GB RAM Hệ thống (CPU)\n• Chính xác ~95-96%: Độ chính xác kém hơn Chế độ 5 chút xíu nhưng được cái nhẹ hơn.', self.group_ai)
        self.lbl_desc_4.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px;')
        self.lbl_desc_4.setWordWrap(True)
        self.radio_model_5 = RadioButton('Chế độ 5 (Bóc Âm Thanh): Chính Xác Cao', self.group_ai)
        self.radio_model_5.setProperty('model_val', 'large-v3')
        self.lbl_desc_5 = BodyLabel('Cần trống tối thiểu: > 2.8GB VRAM Card Đồ Họa (GPU) HOẶC > 3.0GB RAM Hệ thống (CPU)\n• Chính xác đến 98%: Khuyên dùng cho máy khỏe. Dịch chuẩn xác, nối ghép câu hợp lý, bám sát âm thanh gốc nhất.', self.group_ai)
        self.lbl_desc_5.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px;')
        self.lbl_desc_5.setWordWrap(True)
        self.lbl_rec_1 = BodyLabel('', self.group_ai)
        self.lbl_rec_2 = BodyLabel('', self.group_ai)
        self.lbl_rec_3 = BodyLabel('', self.group_ai)
        self.lbl_rec_4 = BodyLabel('', self.group_ai)
        self.lbl_rec_5 = BodyLabel('', self.group_ai)
        for lbl in self.lbl_rec_1, self.lbl_rec_2, self.lbl_rec_3, self.lbl_rec_4, self.lbl_rec_5:
            lbl.setStyleSheet('color: #10b981; font-weight: bold; font-size: 13px; margin-left: 28px;')
            lbl.hide()
        try:
            out = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], creationflags=subprocess.CREATE_NO_WINDOW, text=True)
            vram_gb = float(out.split()[0]) / 1024.0
            msg = '[KHUYÊN DÙNG]'
            if vram_gb >= 3.8:
                self.lbl_rec_5.setText(msg)
                self.lbl_rec_5.show()
            elif vram_gb >= 2.8:
                self.lbl_rec_4.setText(msg)
                self.lbl_rec_4.show()
            elif vram_gb >= 1.8:
                self.lbl_rec_3.setText(msg)
                self.lbl_rec_3.show()
            elif vram_gb >= 1.2:
                self.lbl_rec_2.setText(msg)
                self.lbl_rec_2.show()
            else:
                self.lbl_rec_1.setText(msg)
                self.lbl_rec_1.show()
        except Exception:
            ram_available_gb = psutil.virtual_memory().available / 1073741824
            msg = '[KHUYÊN DÙNG]'
            if ram_available_gb >= 4.0:
                self.lbl_rec_5.setText(msg)
                self.lbl_rec_5.show()
            elif ram_available_gb >= 3.0:
                self.lbl_rec_4.setText(msg)
                self.lbl_rec_4.show()
            elif ram_available_gb >= 2.0:
                self.lbl_rec_3.setText(msg)
                self.lbl_rec_3.show()
            elif ram_available_gb >= 1.5:
                self.lbl_rec_2.setText(msg)
                self.lbl_rec_2.show()
            else:
                self.lbl_rec_1.setText(msg)
                self.lbl_rec_1.show()
        self.radio_model_6 = RadioButton('Chế độ 6 (Nhìn Màn Hình): Bóc Phụ Đề Gốc', self.group_ai)
        self.radio_model_6.setProperty('model_val', 'image_ocr')
        self.lbl_desc_6 = BodyLabel('Yêu cầu: Vẽ khung khoanh vùng phụ đề chuẩn xác trên Video.\n• Chính xác đến 99%: Quét kịch bản gốc bằng hình ảnh có sẵn trên video gốc. Dùng khi cần bắt trọn từng câu thoại gốc.', self.group_ai)
        self.lbl_desc_6.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px;')
        self.lbl_desc_6.setWordWrap(True)
        self.model_btn_group.addButton(self.radio_model_1)
        self.model_btn_group.addButton(self.radio_model_2)
        self.model_btn_group.addButton(self.radio_model_3)
        self.model_btn_group.addButton(self.radio_model_4)
        self.model_btn_group.addButton(self.radio_model_5)
        self.model_btn_group.addButton(self.radio_model_6)
        layout_ai.addWidget(self.radio_model_1)
        layout_ai.addWidget(self.lbl_rec_1)
        layout_ai.addWidget(self.lbl_desc_1)
        layout_ai.addSpacing(5)
        layout_ai.addWidget(self.radio_model_2)
        layout_ai.addWidget(self.lbl_rec_2)
        layout_ai.addWidget(self.lbl_desc_2)
        layout_ai.addSpacing(5)
        layout_ai.addWidget(self.radio_model_3)
        layout_ai.addWidget(self.lbl_rec_3)
        layout_ai.addWidget(self.lbl_desc_3)
        layout_ai.addSpacing(5)
        layout_ai.addWidget(self.radio_model_4)
        layout_ai.addWidget(self.lbl_rec_4)
        layout_ai.addWidget(self.lbl_desc_4)
        layout_ai.addSpacing(5)
        layout_ai.addWidget(self.radio_model_5)
        layout_ai.addWidget(self.lbl_rec_5)
        layout_ai.addWidget(self.lbl_desc_5)
        layout_ai.addSpacing(5)
        layout_ai.addWidget(self.radio_model_6)
        layout_ai.addWidget(self.lbl_desc_6)
        layout_ai.addWidget(BodyLabel('Ngôn ngữ video gốc:'))
        self.combo_lang = ComboBox(self.group_ai)
        self.combo_lang.addItem('Tự động nhận diện (Khuyên dùng)', userData='auto')
        self.combo_lang.addItem('Tiếng Anh (English)', userData='en')
        self.combo_lang.addItem('Tiếng Việt (Vietnamese)', userData='vi')
        self.combo_lang.addItem('Tiếng Trung (Chinese)', userData='zh')
        self.combo_lang.addItem('Tiếng Hàn (Korean)', userData='ko')
        self.combo_lang.addItem('Tiếng Nhật (Japanese)', userData='ja')
        layout_ai.addWidget(self.combo_lang)
        self.ocr_settings_container = QWidget(self.group_ai)
        layout_ocr = QVBoxLayout(self.ocr_settings_container)
        layout_ocr.setContentsMargins(0, 0, 0, 0)
        layout_ocr.setSpacing(10)
        layout_ocr.addWidget(BodyLabel('Chọn Lõi Đọc Chữ:', self.ocr_settings_container))
        self.ocr_engine_group = QButtonGroup(self.ocr_settings_container)
        self.radio_ocr_fast = RadioButton('Lõi Tăng Tốc (GPU): Nhanh gấp ~3 lần nếu máy có Card NVIDIA.', self.ocr_settings_container)
        self.radio_ocr_fast.setProperty('engine_val', 'paddle')
        self.radio_ocr_stable = RadioButton('Lõi Ổn Định (CPU): Tương thích mọi máy, không cần Card rời.', self.ocr_settings_container)
        self.radio_ocr_stable.setProperty('engine_val', 'rapid')
        self.ocr_engine_group.addButton(self.radio_ocr_fast)
        self.ocr_engine_group.addButton(self.radio_ocr_stable)
        self.radio_ocr_fast.setChecked(True)
        layout_ocr.addWidget(self.radio_ocr_fast)
        self.lbl_ocr_gpu_note = BodyLabel('Lưu ý: Chỉ hỗ trợ Card NVIDIA. KHÔNG hỗ trợ Card AMD, Intel Onboard.', self.ocr_settings_container)
        self.lbl_ocr_gpu_note.setStyleSheet('color: #d9534f; font-size: 12px; font-style: italic;')
        layout_ocr.addWidget(self.lbl_ocr_gpu_note)
        layout_ocr.addWidget(self.radio_ocr_stable)
        self.ocr_engine_group.buttonClicked.connect((lambda: self._saveConfig(show_msg=False)))
        self.chk_ocr_preprocess = CheckBox('Chế độ Tách Viền Đen (Xóa nền rối)', self.ocr_settings_container)
        layout_ocr.addWidget(self.chk_ocr_preprocess)
        self.chk_ocr_preprocess.stateChanged.connect((lambda: self._saveConfig(show_msg=False)))
        self.lbl_preprocess_desc = BodyLabel('• Bật: Xóa sạch nền rối phía sau. Lưu ý: CHỈ CÓ TÁC DỤNG với phụ đề gốc màu TRẮNG có viền đen. Chữ màu khác (Vàng, Xanh...) sẽ bị mù.\n• Tắt: Đọc trực tiếp mọi loại màu sắc chữ. Tốc độ nhanh (Khuyên dùng mặc định).', self.ocr_settings_container)
        self.lbl_preprocess_desc.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px; margin-left: 28px; margin-bottom: 10px;')
        self.lbl_preprocess_desc.setWordWrap(True)
        layout_ocr.addWidget(self.lbl_preprocess_desc)
        layout_conf = QHBoxLayout()
        layout_conf.addWidget(BodyLabel('Bộ lọc rác (Khử chữ mờ, sai):', self.ocr_settings_container))
        self.slider_ocr_conf = Slider(Qt.Orientation.Horizontal, self.ocr_settings_container)
        self.slider_ocr_conf.setRange(0, 99)
        self.lbl_ocr_conf_val = BodyLabel('0%', self.ocr_settings_container)
        self.lbl_ocr_conf_val.setFixedWidth(40)
        self.slider_ocr_conf.valueChanged.connect((lambda v: self.lbl_ocr_conf_val.setText(f'{v}%')))
        self.slider_ocr_conf.sliderReleased.connect((lambda: self._saveConfig(show_msg=False)))
        layout_conf.addWidget(self.slider_ocr_conf)
        layout_conf.addWidget(self.lbl_ocr_conf_val)
        layout_ocr.addLayout(layout_conf)
        self.lbl_conf_desc = BodyLabel('• 0%: Lấy mọi chữ (Kể cả mờ). Khuyên dùng nếu đã khoanh vùng chuẩn.\n• 30-50%: Lọc bớt chữ rác do cảnh vật phía sau (Dùng khi nền bị rối).\n• > 80%: Chỉ lấy chữ siêu nét (Dễ gây mất chữ).', self.ocr_settings_container)
        self.lbl_conf_desc.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px;')
        self.lbl_conf_desc.setWordWrap(True)
        layout_ocr.addWidget(self.lbl_conf_desc)
        layout_fps = QHBoxLayout()
        layout_fps.addWidget(BodyLabel('Tốc độ quét (FPS):', self.ocr_settings_container))
        self.slider_ocr_fps = Slider(Qt.Orientation.Horizontal, self.ocr_settings_container)
        self.slider_ocr_fps.setRange(3, 10)
        self.lbl_ocr_fps_val = BodyLabel('10 fps', self.ocr_settings_container)
        self.lbl_ocr_fps_val.setFixedWidth(50)
        layout_fps.addWidget(self.slider_ocr_fps)
        layout_fps.addWidget(self.lbl_ocr_fps_val)
        layout_ocr.addLayout(layout_fps)
        self.lbl_fps_desc = BodyLabel('Ước tính thời gian quét OCR cho Video 10 phút:\n• 3 fps (Khuyên dùng): Quét mất ~5 phút. Bắt chuẩn 97% câu thoại. Tổng thời gian tạo ra video cực nhanh (~15 phút).\n• 5-7 fps (Cân bằng): Quét mất ~10 phút. Dành cho video có sub nhịp độ nhanh, chữ lướt qua chớp nhoáng.\n• 10 fps (Tuyệt đối): Quét mất ~17 phút. Độ chi tiết cao nhất, nhưng tổng thời gian làm video sẽ kéo dài hơn (~26 phút).', self.ocr_settings_container)
        self.lbl_fps_desc.setStyleSheet('color: #94A3B8; font-style: italic; font-size: 13px;')
        self.lbl_fps_desc.setWordWrap(True)
        layout_ocr.addWidget(self.lbl_fps_desc)
        self.slider_ocr_fps.valueChanged.connect((lambda v: self.lbl_ocr_fps_val.setText(f'{v} fps')))
        self.slider_ocr_fps.sliderReleased.connect((lambda: self._saveConfig(show_msg=False)))
        layout_ai.addWidget(self.ocr_settings_container)
        layout_general.addWidget(self.group_ai)
        self.group_perf = CardWidget(self.page_general)
        layout_perf = QVBoxLayout(self.group_perf)
        layout_perf.setSpacing(15)
        layout_perf.addWidget(SubtitleLabel('Hiệu suất Hệ thống'))
        self.combo_cpu = ComboBox(self.group_perf)
        self.combo_cpu.addItem('Tối đa (Nhanh - Chiếm ~80-85% CPU)', userData='max')
        self.combo_cpu.addItem('Trung bình (Cân bằng - Chiếm ~50% CPU)', userData='medium')
        self.combo_cpu.addItem('Thấp (Chậm - Chiếm ~25% CPU)', userData='low')
        layout_perf.addWidget(self.combo_cpu)
        layout_general.addWidget(self.group_perf)
        layout_general.addStretch(1)
        self.stackedWidget.addWidget(self.page_general)
        self.page_ai_services = QWidget()
        layout_ai_services = QVBoxLayout(self.page_ai_services)
        layout_ai_services.setContentsMargins(0, 10, 0, 0)
        layout_ai_services.setSpacing(20)
        self.group_trans = CardWidget(self.page_ai_services)
        layout_trans = QVBoxLayout(self.group_trans)
        layout_trans.setSpacing(15)
        layout_trans.addWidget(SubtitleLabel('Gemini API Keys'))
        layout_trans.addWidget(BodyLabel('Gemini API Keys (Mỗi dòng 1 key, sẽ xoay vòng tự động khi bị lỗi quá tải):'))
        self.text_api_keys = TextEdit(self.group_trans)
        self.text_api_keys.setPlaceholderText('Nhập API Key vào đây...')
        self.text_api_keys.setFixedHeight(80)
        layout_trans.addWidget(self.text_api_keys)
        layout_ai_services.addWidget(self.group_trans)
        self.group_chatgpt = CardWidget(self.page_ai_services)
        layout_cg = QVBoxLayout(self.group_chatgpt)
        layout_cg.setSpacing(12)
        layout_cg.addWidget(SubtitleLabel('Dịch thuật bằng ChatGPT Web (chatgpt.com)'))
        layout_cg.addWidget(BodyLabel('Cookie / AccessToken ChatGPT Web (Tự động xoay vòng khi quá tải):'))
        lbl_cg_guide = CaptionLabel('• Cách 1 (Khuyên dùng - Chuẩn 100%): Mở tab mới vào https://chatgpt.com/api/auth/session -> Copy toàn bộ JSON (hoặc giá trị accessToken) dán vào đây.\n• Cách 2: Copy giá trị __Secure-next-auth.session-token từ F12 Application -> Cookies, hoặc copy toàn bộ header Cookie: từ F12 Network tab (hỗ trợ cả session-token, cookie chunk .0/.1, Cookie-Editor).\n• Hỗ trợ nhập nhiều tài khoản (mỗi tài khoản 1 dòng) để tự động xoay vòng khi đầy hạn mức.')
        lbl_cg_guide.setStyleSheet('color: #94A3B8; font-style: italic;')
        layout_cg.addWidget(lbl_cg_guide)
        self.text_chatgpt_cookies = TextEdit(self.group_chatgpt)
        self.text_chatgpt_cookies.setPlaceholderText('Dán AccessToken, nội dung JSON từ chatgpt.com/api/auth/session hoặc Cookie vào đây...')
        self.text_chatgpt_cookies.setFixedHeight(95)
        layout_cg.addWidget(self.text_chatgpt_cookies)
        row_cg_ctrl = QHBoxLayout()
        self.btn_test_chatgpt = PushButton(FIF.PLAY, 'Kiểm tra Cookie / Token', self.group_chatgpt)
        self.btn_test_chatgpt.setFixedWidth(180)
        row_cg_ctrl.addWidget(self.btn_test_chatgpt)
        self.lbl_chatgpt_status = BodyLabel('Trạng thái: Chưa kiểm tra', self.group_chatgpt)
        self.lbl_chatgpt_status.setStyleSheet('color: gray;')
        row_cg_ctrl.addWidget(self.lbl_chatgpt_status)
        row_cg_ctrl.addStretch(1)
        layout_cg.addLayout(row_cg_ctrl)
        layout_ai_services.addWidget(self.group_chatgpt)
        self.group_custom_api = CardWidget(self.page_ai_services)
        layout_ca = QVBoxLayout(self.group_custom_api)
        layout_ca.setSpacing(12)
        layout_ca.addWidget(SubtitleLabel('Custom API (OpenAI / DeepSeek / Groq / OpenRouter / Ollama...)'))
        layout_ca.addWidget(BodyLabel('Base URL (Mặc định để trống để dùng OpenAI):'))
        self.line_custom_api_base_url = LineEdit(self.group_custom_api)
        self.line_custom_api_base_url.setPlaceholderText('Mặc định để trống (dùng https://api.openai.com/v1) hoặc nhập https://api.deepseek.com...')
        self.line_custom_api_base_url.setClearButtonEnabled(True)
        layout_ca.addWidget(self.line_custom_api_base_url)
        layout_ca.addWidget(BodyLabel('API Key (Mỗi dòng 1 key, tự động xoay vòng khi quá tải):'))
        self.text_custom_api_key = TextEdit(self.group_custom_api)
        self.text_custom_api_key.setPlaceholderText('Dán API Key vào đây (ví dụ: sk-..., gsk_...)...')
        self.text_custom_api_key.setFixedHeight(75)
        layout_ca.addWidget(self.text_custom_api_key)
        layout_ca.addWidget(BodyLabel('Mô hình (Model name):'))
        self.line_custom_api_model = LineEdit(self.group_custom_api)
        self.line_custom_api_model.setPlaceholderText('Để trống để tự động nhận diện theo Base URL (hoặc nhập: deepseek-chat, gpt-4o, llama-3.3-70b-versatile...)')
        self.line_custom_api_model.setClearButtonEnabled(True)
        layout_ca.addWidget(self.line_custom_api_model)
        lbl_ca_guide = CaptionLabel('• Tự động nhận diện: DeepSeek -> deepseek-chat | Groq -> llama-3.3-70b-versatile | OpenRouter -> google/gemini-2.0-flash-001 | OpenAI -> gpt-4o-mini | Ollama -> llama3.2.\n• Hoặc bạn có thể nhập thủ công bất kỳ tên model nào của nhà cung cấp vào ô bên trên.')
        lbl_ca_guide.setStyleSheet('color: #94A3B8; font-style: italic;')
        layout_ca.addWidget(lbl_ca_guide)
        row_ca_ctrl = QHBoxLayout()
        self.btn_test_custom_api = PushButton(FIF.PLAY, 'Kiểm tra API', self.group_custom_api)
        self.btn_test_custom_api.setFixedWidth(180)
        row_ca_ctrl.addWidget(self.btn_test_custom_api)
        self.lbl_custom_api_status = BodyLabel('Trạng thái: Chưa kiểm tra', self.group_custom_api)
        self.lbl_custom_api_status.setStyleSheet('color: gray;')
        row_ca_ctrl.addWidget(self.lbl_custom_api_status)
        row_ca_ctrl.addStretch(1)
        layout_ca.addLayout(row_ca_ctrl)
        layout_ai_services.addWidget(self.group_custom_api)
        self.group_voice = CardWidget(self.page_ai_services)
        layout_voice = QVBoxLayout(self.group_voice)
        layout_voice.setSpacing(15)
        layout_voice.addWidget(SubtitleLabel('Cấu hình Giọng đọc AI'))
        layout_voice.addWidget(BodyLabel('TikTok Session ID (Bắt buộc nếu không muốn dùng dọng AI Google):'))
        self.line_tiktok_session = LineEdit(self.group_voice)
        self.line_tiktok_session.setPlaceholderText('Dán Session ID vào đây...')
        self.line_tiktok_session.setEchoMode(LineEdit.EchoMode.Password)
        layout_voice.addWidget(self.line_tiktok_session)
        self.lbl_tiktok_status = BodyLabel('Trạng thái: Chưa kiểm tra', self.group_voice)
        self.lbl_tiktok_status.setStyleSheet('color: gray;')
        layout_voice.addWidget(self.lbl_tiktok_status)
        layout_ai_services.addWidget(self.group_voice)
        layout_ai_services.addStretch(1)
        self.stackedWidget.addWidget(self.page_ai_services)
        self.page_models = QWidget()
        layout_models = QVBoxLayout(self.page_models)
        layout_models.setContentsMargins(0, 10, 0, 0)
        layout_models.setSpacing(20)
        self.group_models = CardWidget(self.page_models)
        layout_mdl = QVBoxLayout(self.group_models)
        layout_mdl.setSpacing(15)
        layout_mdl.addWidget(SubtitleLabel('Quản lý Gói Tính Năng'))
        lbl_mdl_desc = BodyLabel('Lưu ý: Nếu App bị đơ khi xử lý video lần đầu, có thể do chưa tải các Gói Mở Rộng (Nghe, Tách Nhạc, Bóc Chữ). Bạn hãy bấm nút bên dưới để tải và thử lại nhé.')
        lbl_mdl_desc.setWordWrap(True)
        lbl_mdl_desc.setStyleSheet('color: #94A3B8; font-style: italic; margin-bottom: 5px;')
        layout_mdl.addWidget(lbl_mdl_desc)
        def create_model_row(name, desc):
            row = QHBoxLayout()
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            title = StrongBodyLabel(name)
            desc_lbl = BodyLabel(desc)
            desc_lbl.setStyleSheet('color: #94A3B8; font-size: 12px;')
            info_layout.addWidget(title)
            info_layout.addWidget(desc_lbl)
            status_lbl = BodyLabel('Đang kiểm tra...')
            status_lbl.setFixedWidth(80)
            btn = PushButton(FIF.DOWNLOAD, 'Sửa/Tải')
            btn.setFixedWidth(100)
            btn_del = ToolButton(FIF.DELETE)
            btn_del.setToolTip('Xóa Model để giải phóng bộ nhớ')
            row.addLayout(info_layout)
            row.addStretch(1)
            row.addWidget(status_lbl)
            row.addSpacing(10)
            row.addWidget(btn)
            row.addSpacing(5)
            row.addWidget(btn_del)
            return row, status_lbl, btn, btn_del

        row_whisper_1, self.lbl_whisper_1_status, self.btn_dl_whisper_1, self.btn_del_whisper_1 = create_model_row('1. Gói Chế độ 1 (Nghe)', 'Mô hình siêu nhẹ')
        row_whisper_2, self.lbl_whisper_2_status, self.btn_dl_whisper_2, self.btn_del_whisper_2 = create_model_row('2. Gói Chế độ 2 (Nghe)', 'Mô hình rất nhanh')
        row_whisper_3, self.lbl_whisper_3_status, self.btn_dl_whisper_3, self.btn_del_whisper_3 = create_model_row('3. Gói Chế độ 3 (Nghe)', 'Mô hình cân bằng')
        row_whisper_4, self.lbl_whisper_4_status, self.btn_dl_whisper_4, self.btn_del_whisper_4 = create_model_row('4. Gói Chế độ 4 (Nghe)', 'Mô hình rõ nét')
        row_whisper_5, self.lbl_whisper_5_status, self.btn_dl_whisper_5, self.btn_del_whisper_5 = create_model_row('5. Gói Chế độ 5 (Nghe)', 'Mô hình thông minh nhất')
        row_paddle, self.lbl_paddle_status, self.btn_dl_paddle, self.btn_del_paddle = create_model_row('6. Gói Chế độ 6 (Nhìn)', 'Mô hình quét chữ tự động trên video')
        demucs_desc = 'Mô hình phân tách tiếng người và nhạc nền<br><b>Tối thiểu:</b> RAM trống ≥ 2GB.<br><b>Khuyến nghị:</b> Card đồ họa ~VRAM>2GB chạy mượt.'
        row_demucs, self.lbl_demucs_status, self.btn_dl_demucs, self.btn_del_demucs = create_model_row('7. Gói Bổ Trợ (Tách Nhạc)', demucs_desc)
        layout_mdl.addLayout(row_whisper_1)
        layout_mdl.addLayout(row_whisper_2)
        layout_mdl.addLayout(row_whisper_3)
        layout_mdl.addLayout(row_whisper_4)
        layout_mdl.addLayout(row_whisper_5)
        layout_mdl.addLayout(row_paddle)
        layout_mdl.addLayout(row_demucs)
        layout_btn_models = QHBoxLayout()
        self.btn_download_models = PrimaryPushButton(FIF.DOWNLOAD, 'Tải / Sửa lỗi Tất cả Model')
        self.btn_download_models.setFixedHeight(40)
        self.btn_clean_c_drive = PushButton(FIF.DELETE, 'Dọn dẹp bộ nhớ Cache')
        self.btn_clean_c_drive.setToolTip('Phát hiện và xóa các Gói cài đặt cũ nằm trên bộ nhớ đệm (Cache) để giải phóng dung lượng')
        self.btn_clean_c_drive.setFixedHeight(40)
        layout_btn_models.addWidget(self.btn_download_models)
        layout_btn_models.addSpacing(10)
        layout_btn_models.addWidget(self.btn_clean_c_drive)
        layout_mdl.addLayout(layout_btn_models)
        self.text_model_log = TextEdit(self.group_models)
        self.text_model_log.setReadOnly(True)
        self.text_model_log.setPlaceholderText('Tiến trình tải sẽ hiển thị ở đây...')
        self.text_model_log.setFixedHeight(250)
        self.text_model_log.setStyleSheet('background-color: #0F172A; color: #10B981; font-family: Consolas, monospace;')
        layout_mdl.addWidget(self.text_model_log)
        layout_models.addWidget(self.group_models)
        layout_models.addStretch(1)
        self.stackedWidget.addWidget(self.page_models)
        self.pivot.addItem(routeKey='general', text='Nhận diện', onClick=(lambda: self.stackedWidget.setCurrentWidget(self.page_general)))
        self.pivot.addItem(routeKey='ai_services', text='API', onClick=(lambda: self.stackedWidget.setCurrentWidget(self.page_ai_services)))
        self.pivot.addItem(routeKey='models', text='Gói Mở Rộng', onClick=(lambda: self.stackedWidget.setCurrentWidget(self.page_models), self._check_model_status()))
        self.pivot.addItem(routeKey='account', text='Tài khoản', onClick=(lambda: self.stackedWidget.setCurrentWidget(self.page_account)))
        self.pivot.setCurrentItem('general')
        self.stackedWidget.setCurrentWidget(self.page_general)
        self.footerWidget = QWidget(self)
        self.footerWidget.setStyleSheet('background-color: transparent;')
        self.footerLayout = QHBoxLayout(self.footerWidget)
        self.footerLayout.setContentsMargins(40, 10, 40, 20)
        self.btn_save = PrimaryPushButton('Lưu Cài Đặt', self.footerWidget)
        self.btn_save.setFixedHeight(40)
        self.footerLayout.addWidget(self.btn_save)
        self.mainLayout.addWidget(self.footerWidget)

    def _connectSignals(self):
        self.model_btn_group.buttonClicked.connect(self._onModelChanged)
        self.line_tiktok_session.textChanged.connect(self._onTikTokSessionChanged)
        self.btn_download_models.clicked.connect((lambda: self._startDownloadModels('all')))
        self.btn_dl_whisper_1.clicked.connect((lambda: self._startDownloadModels('whisper_tiny')))
        self.btn_dl_whisper_2.clicked.connect((lambda: self._startDownloadModels('whisper_base')))
        self.btn_dl_whisper_3.clicked.connect((lambda: self._startDownloadModels('whisper_small')))
        self.btn_dl_whisper_4.clicked.connect((lambda: self._startDownloadModels('whisper_medium')))
        self.btn_dl_whisper_5.clicked.connect((lambda: self._startDownloadModels('whisper_large-v3')))
        self.btn_dl_paddle.clicked.connect((lambda: self._startDownloadModels('paddleocr')))
        self.btn_dl_demucs.clicked.connect((lambda: self._startDownloadModels('demucs')))
        self.btn_clean_c_drive.clicked.connect(self._clean_c_drive)
        self.btn_del_whisper_1.clicked.connect((lambda: self._delete_model('whisper_tiny')))
        self.btn_del_whisper_2.clicked.connect((lambda: self._delete_model('whisper_base')))
        self.btn_del_whisper_3.clicked.connect((lambda: self._delete_model('whisper_small')))
        self.btn_del_whisper_4.clicked.connect((lambda: self._delete_model('whisper_medium')))
        self.btn_del_whisper_5.clicked.connect((lambda: self._delete_model('whisper_large-v3')))
        self.btn_del_paddle.clicked.connect((lambda: self._delete_model('paddleocr')))
        self.btn_del_demucs.clicked.connect((lambda: self._delete_model('demucs')))
        self.btn_save.clicked.connect((lambda: self._saveConfig(True)))

    def _startDownloadModels(self, target='all'):
        if hasattr(self, 'model_worker') and self.model_worker.isRunning():
            InfoBar.warning('Đang tải', 'Tiến trình tải Model đang diễn ra, vui lòng chờ...', parent=self.window(), position=InfoBarPosition.TOP)
            return
        self.btn_download_models.setEnabled(False)
        self.btn_dl_whisper_1.setEnabled(False)
        self.btn_dl_whisper_2.setEnabled(False)
        self.btn_dl_whisper_3.setEnabled(False)
        self.btn_dl_whisper_4.setEnabled(False)
        self.btn_dl_whisper_5.setEnabled(False)
        self.btn_dl_demucs.setEnabled(False)
        self.btn_dl_paddle.setEnabled(False)
        self.text_model_log.clear()
        self.model_worker = ModelDownloaderWorker(target_model=target, parent=self)
        self.model_worker.progress.connect(self._onModelDownloadProgress)
        self.model_worker.finished_signal.connect(self._onModelDownloadFinished)
        self.model_worker.start()

    def _onModelDownloadProgress(self, text):
        self.text_model_log.append(text)
        scrollbar = self.text_model_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _onModelDownloadFinished(self, success):
        self.btn_download_models.setEnabled(True)
        self.btn_dl_whisper_1.setEnabled(True)
        self.btn_dl_whisper_2.setEnabled(True)
        self.btn_dl_whisper_3.setEnabled(True)
        self.btn_dl_whisper_4.setEnabled(True)
        self.btn_dl_whisper_5.setEnabled(True)
        self.btn_dl_demucs.setEnabled(True)
        self.btn_dl_paddle.setEnabled(True)
        self._check_model_status()
        if success:
            InfoBar.success('Hoàn tất', 'Đã kiểm tra và tải xong Model AI!', parent=self.window(), position=InfoBarPosition.TOP, duration=8000)

    def _delete_model(self, target):
        import shutil
        import os
        from qfluentwidgets import (MessageBox, InfoBar, InfoBarPosition)
        msg = MessageBox('Xác nhận Xóa Gói Tính Năng', 'Bạn có chắc chắn muốn xóa dữ liệu của tính năng này để giải phóng ổ cứng không?\n(Bạn hoàn toàn có thể tải lại sau nếu cần).', self.window())
        if not msg.exec():
            return
        home = os.path.expanduser('~')
        deleted = False
        from app.common.config_manager import get_hf_cache_dir
        InfoBar.warning(title='Không có gì để xóa', content='Bạn chưa tải Gói tính năng này nên không có gì để xóa cả!', parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
        try:
            if target == 'whisper_tiny':
                old_p = os.path.join(home, '.cache', 'huggingface', 'hub', 'models--Systran--faster-whisper-tiny')
                if os.path.exists(old_p):
                    shutil.rmtree(old_p)
                    deleted = True
                new_p = os.path.join(get_hf_cache_dir(), 'hub', 'models--Systran--faster-whisper-tiny')
                if os.path.exists(new_p):
                    shutil.rmtree(new_p)
                    deleted = True
            elif target == 'whisper_base':
                old_p = os.path.join(home, '.cache', 'huggingface', 'hub', 'models--Systran--faster-whisper-base')
                if os.path.exists(old_p):
                    shutil.rmtree(old_p)
                    deleted = True
                new_p = os.path.join(get_hf_cache_dir(), 'hub', 'models--Systran--faster-whisper-base')
                if os.path.exists(new_p):
                    shutil.rmtree(new_p)
                    deleted = True
            elif target == 'whisper_small':
                old_p = os.path.join(home, '.cache', 'huggingface', 'hub', 'models--Systran--faster-whisper-small')
                if os.path.exists(old_p):
                    shutil.rmtree(old_p)
                    deleted = True
                new_p = os.path.join(get_hf_cache_dir(), 'hub', 'models--Systran--faster-whisper-small')
                if os.path.exists(new_p):
                    shutil.rmtree(new_p)
                    deleted = True
            elif target == 'whisper_medium':
                old_p = os.path.join(home, '.cache', 'huggingface', 'hub', 'models--Systran--faster-whisper-medium')
                if os.path.exists(old_p):
                    shutil.rmtree(old_p)
                    deleted = True
                new_p = os.path.join(get_hf_cache_dir(), 'hub', 'models--Systran--faster-whisper-medium')
                if os.path.exists(new_p):
                    shutil.rmtree(new_p)
                    deleted = True
            elif target == 'whisper_large-v3':
                old_p = os.path.join(home, '.cache', 'huggingface', 'hub', 'models--Systran--faster-whisper-large-v3')
                if os.path.exists(old_p):
                    shutil.rmtree(old_p)
                    deleted = True
                new_p = os.path.join(get_hf_cache_dir(), 'hub', 'models--Systran--faster-whisper-large-v3')
                if os.path.exists(new_p):
                    shutil.rmtree(new_p)
                    deleted = True
            elif target == 'paddleocr':
                from app.common.config_manager import get_paddleocr_cache_dir
                p = get_paddleocr_cache_dir()
                if os.path.exists(p):
                    shutil.rmtree(p)
                    deleted = True
            elif target == 'demucs':
                from app.common.config_manager import get_audio_sep_cache_dir
                p = get_audio_sep_cache_dir()
                if os.path.exists(p):
                    shutil.rmtree(p)
                    deleted = True
            if deleted:
                InfoBar.success(title='Đã xóa thành công', content='Đã giải phóng dung lượng thành công!', parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
                self._check_model_status()
            return
        except Exception as e:
            InfoBar.error(title='Lỗi khi xóa', content=f'Không thể xóa thư mục: {str(e)}', parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
            return

    def _clean_c_drive(self):
        import shutil
        import os
        from qfluentwidgets import (MessageBox, InfoBar, InfoBarPosition)
        home = os.path.expanduser('~')
        folders_to_delete = []
        c_cache = os.path.join(home, '.cache', 'huggingface', 'hub')
        if os.path.exists(c_cache):
            for item in os.listdir(c_cache):
                if 'faster-whisper' in item:
                    folders_to_delete.append(os.path.join(c_cache, item))
        paddle_cache = os.path.join(home, '.paddleocr')
        if os.path.exists(paddle_cache):
            folders_to_delete.append(paddle_cache)
        demucs_cache = os.path.join(home, '.cache', 'audio-separator')
        if os.path.exists(demucs_cache):
            folders_to_delete.append(demucs_cache)
        old_demucs = os.path.join(home, '.cache', 'torch', 'hub', 'facebookresearch_demucs_main')
        if os.path.exists(old_demucs):
            folders_to_delete.append(old_demucs)
        old_checkpoints = os.path.join(home, '.cache', 'torch', 'hub', 'checkpoints')
        if os.path.exists(old_checkpoints):
            folders_to_delete.append(old_checkpoints)
        old_paddle = os.path.join(home, '.cache', 'paddle')
        if os.path.exists(old_paddle):
            folders_to_delete.append(old_paddle)
        old_whisper = os.path.join(home, '.cache', 'whisper')
        if os.path.exists(old_whisper):
            folders_to_delete.append(old_whisper)
        old_audioseal = os.path.join(home, '.cache', 'audioseal')
        if os.path.exists(old_audioseal):
            folders_to_delete.append(old_audioseal)
        if not folders_to_delete:
            InfoBar.success('Sạch sẽ', 'Không có rác Cache!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        size_bytes = 0
        for fp in folders_to_delete:
            if os.path.exists(fp):
                for path, dirs, files in os.walk(fp):
                    for f in files:
                        f_full = os.path.join(path, f)
                        if os.path.exists(f_full):
                            size_bytes += os.path.getsize(f_full)
        if size_bytes == 0:
            InfoBar.success('Sạch sẽ', 'Cache đã sạch sẽ!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        size_gb = size_bytes / 1073741824
        msg = MessageBox('Dọn dẹp rác Cache', f'Phát hiện khoảng {size_gb:.2f} GB dữ liệu Cache bản cũ.\nBạn có muốn xóa để lấy lại dung lượng?\n(Model tải mới sẽ không bị ảnh hưởng)', self.window())
        if not msg.exec():
            return
        try:
            for fp in folders_to_delete:
                shutil.rmtree(fp)
            InfoBar.success('Thành công', f'Đã giải phóng {size_gb:.2f} GB!', parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
            self._check_model_status()
        except Exception as e:
            InfoBar.error('Lỗi', f'Không thể xóa: {e}', parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
            return

    def _check_model_status(self):
        import os
        from pathlib import Path
        home = str(Path.home())
        def check_whisper_cache(model_name):
            from app.common.config_manager import get_hf_cache_dir
            new_path = os.path.join(get_hf_cache_dir(), 'hub', f'models--Systran--faster-whisper-{model_name}')
            old_path = os.path.join(home, '.cache', 'huggingface', 'hub', f'models--Systran--faster-whisper-{model_name}')
            return os.path.exists(new_path) or os.path.exists(old_path)

        if check_whisper_cache('tiny'):
            self.lbl_whisper_1_status.setText('Đã tải')
            self.lbl_whisper_1_status.setStyleSheet('color: #10B981; font-weight: bold;')
        else:
            self.lbl_whisper_1_status.setText('Chưa tải')
            self.lbl_whisper_1_status.setStyleSheet('color: #EF4444; font-weight: bold;')
        if check_whisper_cache('base'):
            self.lbl_whisper_2_status.setText('Đã tải')
            self.lbl_whisper_2_status.setStyleSheet('color: #10B981; font-weight: bold;')
        else:
            self.lbl_whisper_2_status.setText('Chưa tải')
            self.lbl_whisper_2_status.setStyleSheet('color: #EF4444; font-weight: bold;')
        if check_whisper_cache('small'):
            self.lbl_whisper_3_status.setText('Đã tải')
            self.lbl_whisper_3_status.setStyleSheet('color: #10B981; font-weight: bold;')
        else:
            self.lbl_whisper_3_status.setText('Chưa tải')
            self.lbl_whisper_3_status.setStyleSheet('color: #EF4444; font-weight: bold;')
        if check_whisper_cache('medium'):
            self.lbl_whisper_4_status.setText('Đã tải')
            self.lbl_whisper_4_status.setStyleSheet('color: #10B981; font-weight: bold;')
        else:
            self.lbl_whisper_4_status.setText('Chưa tải')
            self.lbl_whisper_4_status.setStyleSheet('color: #EF4444; font-weight: bold;')
        if check_whisper_cache('large-v3'):
            self.lbl_whisper_5_status.setText('Đã tải')
            self.lbl_whisper_5_status.setStyleSheet('color: #10B981; font-weight: bold;')
        else:
            self.lbl_whisper_5_status.setText('Chưa tải')
            self.lbl_whisper_5_status.setStyleSheet('color: #EF4444; font-weight: bold;')
        from app.common.config_manager import get_audio_sep_cache_dir
        demucs_cache = get_audio_sep_cache_dir()
        has_demucs = False
        if os.path.exists(demucs_cache):
            for file in os.listdir(demucs_cache):
                if file.endswith('.ckpt') or file.endswith('.onnx'):
                    has_demucs = True
                    break
        if has_demucs:
            self.lbl_demucs_status.setText('Đã tải')
            self.lbl_demucs_status.setStyleSheet('color: #10B981; font-weight: bold;')
        else:
            self.lbl_demucs_status.setText('Chưa tải')
            self.lbl_demucs_status.setStyleSheet('color: #EF4444; font-weight: bold;')
        from app.common.config_manager import get_paddleocr_cache_dir
        paddle_cache = os.path.join(get_paddleocr_cache_dir(), '.paddleocr', 'whl')
        if os.path.exists(paddle_cache) and os.path.exists(os.path.join(paddle_cache, 'det')) and os.path.exists(os.path.join(paddle_cache, 'rec')):
            self.lbl_paddle_status.setText('Đã tải')
            self.lbl_paddle_status.setStyleSheet('color: #10B981; font-weight: bold;')
            return
        self.lbl_paddle_status.setText('Chưa tải')
        self.lbl_paddle_status.setStyleSheet('color: #EF4444; font-weight: bold;')

    def get_gemini_keys(self):
        '''Trả về danh sách API Keys hợp lệ từ TextEdit'''

        keys_text = self.text_api_keys.toPlainText()
        keys = [k.strip() for k in keys_text.split('\n') if k.strip()]
        return keys

    def get_chatgpt_cookies(self):
        '''Trả về danh sách Cookie ChatGPT hợp lệ từ TextEdit'''
        if not hasattr(self, 'text_chatgpt_cookies'):
            return []
        keys_text = self.text_chatgpt_cookies.toPlainText()
        try:
            from chatgpt_web import extract_cookie_entries
            return extract_cookie_entries(keys_text)
        except Exception:
            return [k.strip() for k in keys_text.split('\n') if k.strip()]

    def get_chatgpt_model(self):
        return 'auto'

    def get_custom_api_base_url(self):
        if hasattr(self, 'line_custom_api_base_url'):
            return self.line_custom_api_base_url.text().strip()
        return ''

    def get_custom_api_key(self):
        if hasattr(self, 'text_custom_api_key'):
            return self.text_custom_api_key.toPlainText().strip()
        return ''

    def get_custom_api_model(self):
        if hasattr(self, 'line_custom_api_model'):
            return self.line_custom_api_model.text().strip()
        return ''

    def _onModelChanged(self):
        btn = self.model_btn_group.checkedButton()
        if not btn:
            return
        model_val = btn.property('model_val')
        if model_val == 'image_ocr':
            self.ocr_settings_container.show()
        else:
            self.ocr_settings_container.hide()
        self._saveConfig(show_msg=False)

    def _onTikTokSessionChanged(self):
        self.check_timer.start()

    def _autoCheckTikTokSession(self):
        if self._is_loading:
            return
        session_id = self.line_tiktok_session.text().strip()
        if len(session_id) < 15:
            self.lbl_tiktok_status.setText('Trạng thái: Chưa nhập mã hợp lệ')
            self.lbl_tiktok_status.setStyleSheet('color: gray;')
            self.last_checked_session = ''
            return
        if session_id == self.last_checked_session:
            return
        self.last_checked_session = session_id
        self.lbl_tiktok_status.setText('Trạng thái: Đang kiểm tra...')
        self.lbl_tiktok_status.setStyleSheet('color: #E6A23C;')
        self.check_worker = TikTokSessionCheckWorker(session_id, parent=self)
        self.check_worker.result.connect(self._onCheckSessionResult)
        self.check_worker.start()

    def _onCheckSessionResult(self, success, message):
        if success:
            self.lbl_tiktok_status.setText('Trạng thái: Đang hoạt động')
            self.lbl_tiktok_status.setStyleSheet('color: #67C23A;')
            if not self._suppress_popup:
                InfoBar.success(title='TikTok Session OK', content=message, parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
            self._saveConfig(show_msg=False)
            return
        self.lbl_tiktok_status.setText('Trạng thái: Đã hết hạn hoặc không hợp lệ')
        self.lbl_tiktok_status.setStyleSheet('color: #F56C6C;')
        if not self._suppress_popup:
            InfoBar.error(title='TikTok Session Lỗi', content=message, parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
        self._saveConfig(show_msg=False)

    def _loadConfigToUI(self):
        if 'whisper_model' not in self.config:
            try:
                import subprocess
                out = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], creationflags=subprocess.CREATE_NO_WINDOW, text=True)
                vram = float(out.split()[0]) / 1024.0
                if vram >= 6.0:
                    model_val = 'large-v3'
                elif vram >= 2.0:
                    model_val = 'small'
                else:
                    model_val = 'tiny'
            except Exception:
                model_val = 'tiny'
            self.config['whisper_model'] = model_val
            save_config(self.config)
        else:
            model_val = self.config.get('whisper_model', 'small')
            if model_val == 'large':
                model_val = 'large-v3'
        for btn in self.model_btn_group.buttons():
            if btn.property('model_val') == model_val:
                btn.setChecked(True)
                break
        if model_val == 'image_ocr':
            self.ocr_settings_container.show()
        else:
            self.ocr_settings_container.hide()
        lang_val = self.config.get('source_lang', 'auto')
        for i in range(self.combo_lang.count()):
            if self.combo_lang.itemData(i) == lang_val:
                self.combo_lang.setCurrentIndex(i)
        ocr_engine = self.config.get('ocr_engine', 'paddle')
        for btn in self.ocr_engine_group.buttons():
            if btn.property('engine_val') == ocr_engine:
                btn.setChecked(True)
                break
        self.chk_ocr_preprocess.setChecked(self.config.get('ocr_preprocess', False))
        try:
            ocr_conf = int(float(self.config.get('ocr_conf_thresh', 0)))
        except:
            ocr_conf = 0
        self.slider_ocr_conf.setValue(ocr_conf)
        self.lbl_ocr_conf_val.setText(f'{ocr_conf}%')
        try:
            ocr_fps = int(float(self.config.get('ocr_fps', 10)))
        except:
            ocr_fps = 10
        self.slider_ocr_fps.setValue(ocr_fps)
        self.lbl_ocr_fps_val.setText(f'{ocr_fps} fps')
        cpu_val = self.config.get('cpu_performance', 'max')
        for i in range(self.combo_cpu.count()):
            if self.combo_cpu.itemData(i) == cpu_val:
                self.combo_cpu.setCurrentIndex(i)
        keys = self.config.get('gemini_keys', [])
        self.text_api_keys.setPlainText('\n'.join(keys))
        if hasattr(self, 'text_chatgpt_cookies'):
            cg_cookies = self.config.get('chatgpt_cookies', [])
            self.text_chatgpt_cookies.setPlainText('\n'.join(cg_cookies))
        if hasattr(self, 'line_custom_api_base_url'):
            self.line_custom_api_base_url.setText(self.config.get('custom_api_base_url', ''))
        if hasattr(self, 'text_custom_api_key'):
            ca_key = self.config.get('custom_api_key', '')
            if isinstance(ca_key, list):
                self.text_custom_api_key.setPlainText('\n'.join(ca_key))
            else:
                self.text_custom_api_key.setPlainText(str(ca_key or ''))
        if hasattr(self, 'line_custom_api_model'):
            self.line_custom_api_model.setText(self.config.get('custom_api_model', ''))
        self.line_tiktok_session.setText(self.config.get('tiktok_session', ''))
        self._check_model_status()

    def _saveConfig(self, show_msg=True):
        if hasattr(self, '_is_loading') and self._is_loading:
            return
        self.config = load_config()
        checked_btn = self.model_btn_group.checkedButton()
        if checked_btn:
            self.config['whisper_model'] = checked_btn.property('model_val')
        self.config['source_lang'] = self.combo_lang.itemData(self.combo_lang.currentIndex())
        self.config['ocr_preprocess'] = self.chk_ocr_preprocess.isChecked()
        self.config['ocr_conf_thresh'] = self.slider_ocr_conf.value()
        self.config['ocr_fps'] = self.slider_ocr_fps.value()
        checked_engine = self.ocr_engine_group.checkedButton()
        if checked_engine:
            self.config['ocr_engine'] = checked_engine.property('engine_val')
        self.config['cpu_performance'] = self.combo_cpu.itemData(self.combo_cpu.currentIndex())
        keys_text = self.text_api_keys.toPlainText().strip()
        self.config['gemini_keys'] = [k.strip() for k in keys_text.split('\n') if k.strip()]
        if hasattr(self, 'text_chatgpt_cookies'):
            cg_text = self.text_chatgpt_cookies.toPlainText().strip()
            try:
                from chatgpt_web import extract_cookie_entries
                self.config['chatgpt_cookies'] = extract_cookie_entries(cg_text)
            except Exception:
                self.config['chatgpt_cookies'] = [k.strip() for k in cg_text.split('\n') if k.strip()]
        self.config['chatgpt_model'] = 'auto'
        if hasattr(self, 'line_custom_api_base_url'):
            self.config['custom_api_base_url'] = self.line_custom_api_base_url.text().strip()
        if hasattr(self, 'text_custom_api_key'):
            self.config['custom_api_key'] = self.text_custom_api_key.toPlainText().strip()
        if hasattr(self, 'line_custom_api_model'):
            self.config['custom_api_model'] = self.line_custom_api_model.text().strip()
        self.config['tiktok_session'] = self.line_tiktok_session.text().strip()
        success = save_config(self.config)
        if show_msg:
            if success:
                InfoBar.success(title='Thành công', content='Đã lưu cài đặt!\n(Lưu ý: Nếu bạn vừa đổi Hiệu suất Hệ thống, hãy Khởi động lại để áp dụng).', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return
            InfoBar.error(title='Lỗi', content='Không thể lưu cài đặt!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)

    def setLicenseInfo(self, status, msg):
        self.lbl_license_status.setText(f'Bản quyền: {msg}')
        if status == 'premium':
            self.lbl_license_status.setStyleSheet('color: #10B981; font-weight: bold; font-size: 14px;')
            return
        if status == 'trial':
            self.lbl_license_status.setStyleSheet('color: #0EA5E9; font-weight: bold; font-size: 14px;')
            return
        if status == 'paid':
            self.lbl_license_status.setStyleSheet('color: #8B5CF6; font-weight: bold; font-size: 14px;')
            return
        self.lbl_license_status.setStyleSheet('color: #E11D48; font-weight: bold; font-size: 14px;')


