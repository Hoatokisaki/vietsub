# -*- coding: utf-8 -*-
import sys
import os
import traceback
import subprocess

class DummyStream:
    def write(self, *args, **kwargs):
        pass

    def flush(self, *args, **kwargs):
        pass

    def isatty(self):
        return False


if getattr(sys, 'stdout', None) is None:
    sys.stdout = DummyStream()
if getattr(sys, 'stderr', None) is None:
    sys.stderr = DummyStream()
if getattr(sys, '__stdout__', None) is None:
    sys.__stdout__ = DummyStream()
if getattr(sys, '__stderr__', None) is None:
    sys.__stderr__ = DummyStream()
if os.name == 'nt':
    original_popen = subprocess.Popen
    class PatchedPopen(original_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)


    subprocess.Popen = PatchedPopen
if len(sys.argv) >= 3 and sys.argv[1] == '-m' and sys.argv[2] == 'yt_dlp':
    import yt_dlp
    sys.exit(yt_dlp.main(sys.argv[3:]))
os.environ['QT_MEDIA_BACKEND'] = 'ffmpeg'
_is_subprocess = len(sys.argv) > 1 and sys.argv[1].startswith('--run-')
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
if not _is_subprocess:
    from app.common.config_manager import get_cpu_threads, get_hf_cache_dir
    __threads = str(get_cpu_threads())
    os.environ['OMP_NUM_THREADS'] = __threads
    os.environ['MKL_NUM_THREADS'] = __threads
    os.environ['OPENBLAS_NUM_THREADS'] = __threads
    os.environ['VECLIB_MAXIMUM_THREADS'] = __threads
    os.environ['NUMEXPR_NUM_THREADS'] = __threads
    os.environ['HF_HOME'] = get_hf_cache_dir()
    os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
else:
    from app.common.config_manager import get_cpu_threads, get_hf_cache_dir
    os.environ['HF_HOME'] = get_hf_cache_dir()
    os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
import multiprocessing
import subprocess
from PyQt6.QtCore import (Qt, QSize, QTimer)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame)
APP_VERSION = '2.6'

def get_icon_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'icon.ico')
    base_dir = os.path.dirname(os.path.abspath(sys.executable))
    internal_path = os.path.join(base_dir, '_internal', 'icon.ico')
    if os.path.exists(internal_path):
        return internal_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')

def get_png_icon_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'icon.png')
    base_dir = os.path.dirname(os.path.abspath(sys.executable))
    internal_path = os.path.join(base_dir, '_internal', 'icon.png')
    if os.path.exists(internal_path):
        return internal_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')

def force_native_taskbar_icon(widget, icon_path):
    import ctypes
    if not os.path.exists(icon_path):
        return
    try:
        hwnd = int(widget.winId())
        hicon_small = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 16, 16, 16)
        hicon_big = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 32, 32, 16)
        if hicon_small:
            ctypes.windll.user32.SendMessageW(hwnd, 128, 0, hicon_small)
        if hicon_big:
            ctypes.windll.user32.SendMessageW(hwnd, 128, 1, hicon_big)
        return
    except Exception:
        pass

from app.common import security

def show_splash_and_check_license(app):
    splash_widget = QWidget()
    splash_widget.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    splash_widget.setFixedSize(380, 130)
    splash_widget.setObjectName('splash')
    splash_widget.setStyleSheet('#splash { background-color: #1E1E1E; border: 1px solid #333333; }')
    main_layout = QHBoxLayout(splash_widget)
    main_layout.setContentsMargins(30, 20, 30, 20)
    main_layout.setSpacing(20)
    icon_path = get_icon_path()
    png_icon_path = get_png_icon_path()
    if os.path.exists(png_icon_path):
        splash_widget.setWindowIcon(QIcon(png_icon_path))
        lbl_icon = QLabel()
        lbl_icon.setPixmap(QIcon(png_icon_path).pixmap(72, 72))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(lbl_icon)
    if os.path.exists(icon_path):
        force_native_taskbar_icon(splash_widget, icon_path)
    text_layout = QVBoxLayout()
    text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    text_layout.setSpacing(4)
    lbl_title = QLabel('luaVietsup')
    lbl_title.setStyleSheet('color: #3498db; font-size: 26px; font-weight: bold; font-family: Arial;')
    lbl_version = QLabel(f'Phiên bản {APP_VERSION} — Đang khởi động...')
    lbl_version.setStyleSheet('color: #E2E8F0; font-size: 13px; font-family: Arial;')
    lbl_wait = QLabel('Vui lòng chờ trong giây lát...')
    lbl_wait.setStyleSheet('color: #94A3B8; font-size: 12px; font-style: italic; font-family: Arial;')
    text_layout.addWidget(lbl_title)
    text_layout.addWidget(lbl_version)
    text_layout.addWidget(lbl_wait)
    main_layout.addLayout(text_layout)
    main_layout.addStretch(1)
    screen = QApplication.primaryScreen().availableGeometry()
    splash_widget.move(screen.width() // 2 - 225, screen.height() // 2 - 75)
    splash_widget.show()
    app.processEvents()
    hwid = security.get_hwid()
    status, msg = security.check_license_online(hwid, APP_VERSION)
    return splash_widget, status, msg

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    if len(sys.argv) > 1:
        if sys.argv[1] == '--run-audio-sep':
            if hasattr(sys, '_MEIPASS'):
                ffmpeg_dir = os.path.join(sys._MEIPASS, 'ffmpeg')
                if os.path.exists(ffmpeg_dir):
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
            try:
                import site
                search_paths = []
                if hasattr(sys, '_MEIPASS'):
                    search_paths.append(sys._MEIPASS)
                if hasattr(site, 'getsitepackages'):
                    search_paths.extend(site.getsitepackages())
                for p in search_paths:
                    for sub in ('nvidia/cublas/bin', 'nvidia/cudnn/bin', 'nvidia/cuda_runtime/bin', 'torch/lib'):
                        dll_path = os.path.join(p, sub.replace('/', os.sep))
                        if os.path.exists(dll_path):
                            if hasattr(os, 'add_dll_directory'):
                                os.add_dll_directory(dll_path)
                            os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')
            except Exception:
                pass
            from audio_separator.separator import Separator
            input_file = sys.argv[2]
            out_dir = sys.argv[3]
            model_name = sys.argv[4]
            use_cuda = sys.argv[5].lower() == 'true'
            segment_size = int(sys.argv[6])
            overlap = int(sys.argv[7])
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception:
                pass
            from app.common.config_manager import get_audio_sep_cache_dir
            cache_dir = get_audio_sep_cache_dir()
            if not use_cuda:
                os.environ['CUDA_VISIBLE_DEVICES'] = ''
            is_roformer_model = 'roformer' in model_name.lower()
            mdx_overlap_map = {2: 0.1, 4: 0.25, 8: 0.5}
            mdx_overlap = mdx_overlap_map.get(overlap, 0.25)
            if is_roformer_model:
                roformer_overlap_map = {2: 0.25, 4: 0.5, 8: 1.0}
                mdxc_overlap = roformer_overlap_map.get(overlap, 0.5)
            else:
                mdxc_overlap = overlap
            separator = Separator(output_dir=out_dir, output_format='WAV', model_file_dir=cache_dir, mdxc_params={'segment_size': segment_size, 'override_model_segment_size': False, 'batch_size': 1, 'overlap': mdxc_overlap, 'pitch_shift': 0}, mdx_params={'segment_size': segment_size, 'overlap': mdx_overlap, 'batch_size': 1, 'hop_length': 1024, 'enable_denoise': False})
            try:
                separator.load_model(model_filename=model_name)
                output_files = separator.separate(input_file)
                for file in output_files:
                    old_path = os.path.join(out_dir, file)
                    if 'Instrumental' in file:
                        new_path = os.path.join(out_dir, 'no_vocals.wav')
                    elif 'Vocals' in file:
                        new_path = os.path.join(out_dir, 'vocals.wav')
                    else:
                        continue
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(old_path, new_path)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                sys.exit(1)
            sys.exit(0)
        elif sys.argv[1] == '--run-script' and len(sys.argv) > 2:
            script_path = sys.argv[2]
            sys.argv = [sys.argv[0]] + sys.argv[3:]
            import importlib.util
            spec = importlib.util.spec_from_file_location('__main__', script_path)
            module = importlib.util.module_from_spec(spec)
            import sys
            sys.modules['__main__'] = module
            spec.loader.exec_module(module)
            sys.exit(0)
        elif sys.argv[1] == '--run-module' and len(sys.argv) > 2:
            import runpy
            module_name = sys.argv[2]
            sys.argv = [sys.argv[0]] + sys.argv[3:]
            runpy.run_module(module_name, run_name='__main__', alter_sys=True)
            sys.exit(0)
        elif sys.argv[1] == '-c' and len(sys.argv) > 2:
            code = sys.argv[2]
            sys.argv = [sys.argv[0]] + sys.argv[3:]
            exec(code)
            sys.exit(0)
    if os.name == 'nt':
        import ctypes
        myappid = 'luaVietsup.Pro.App.' + APP_VERSION
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
    from qfluentwidgets import (setTheme, Theme, setThemeColor, qconfig)
    os.environ['QT_STYLE_OVERRIDE'] = 'Fusion'
    import qfluentwidgets
    if hasattr(qfluentwidgets, 'isDarkTheme'):
        qfluentwidgets.isDarkTheme = lambda: True
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    qconfig.set(qconfig.themeMode, Theme.DARK, save=False)
    setTheme(Theme.DARK)
    from PyQt6.QtGui import QColor
    fixed_color = QColor('#3498db')
    qconfig.set(qconfig.themeColor, fixed_color, save=False)
    setThemeColor(fixed_color)
    from PyQt6.QtGui import QPalette
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    setTheme(Theme.DARK)
    try:
        from app.common.font_manager import load_custom_fonts
        load_custom_fonts()
    except Exception as e:
        print('Lỗi nạp font:', e)
    png_icon_path = get_png_icon_path()
    if os.path.exists(png_icon_path):
        app.setWindowIcon(QIcon(png_icon_path))
    splash, license_status, license_msg = show_splash_and_check_license(app)
    import app.core.security as core_sec
    core_sec.CURRENT_LICENSE_STATUS = license_status
    from qfluentwidgets import (FluentWindow, NavigationItemPosition, SplashScreen)
    from qfluentwidgets import FluentIcon as FIF
    from app.views.home_interface import HomeInterface
    from app.views.library_interface import LibraryInterface
    from app.views.highlight_interface import HighlightInterface
    from app.views.setting_interface import SettingInterface
    from app.views.report_interface import ReportInterface
    from app.views.douyin_interface import DouyinInterface
    from app.views.tts_interface import TTSInterface
    from app.views.video_splitter_interface import VideoSplitterInterface
    from app.views.dictionary_interface import DictionaryInterface
    class MainWindow(FluentWindow):
        def __init__(self, lic_status, lic_msg):
            super().__init__()
            self.license_status = lic_status
            self.license_msg = lic_msg
            self.initWindow()
            self.homeInterface = HomeInterface(self)
            self.homeInterface.license_status = lic_status
            self.libraryInterface = LibraryInterface(self)
            self.highlightInterface = HighlightInterface(self)
            self.settingInterface = SettingInterface(self)
            self.settingInterface.setLicenseInfo(lic_status, lic_msg)
            self.reportInterface = ReportInterface(self)
            self.douyinInterface = DouyinInterface(self)
            self.ttsInterface = TTSInterface(self)
            self.splitterInterface = VideoSplitterInterface(self)
            self.dictInterface = DictionaryInterface(self)
            self.initNavigation()
            self.splashScreen.finish()
            QTimer.singleShot(1500, self.show_license_notification)
            QTimer.singleShot(2000, self.check_update)

        def show_license_notification(self):
            from qfluentwidgets import InfoBar, InfoBarPosition
            lic_status = self.license_status
            lic_msg = self.license_msg
            if lic_status == 'premium':
                InfoBar.success(title='PREMIUM', content=lic_msg, parent=self, position=InfoBarPosition.TOP, duration=5000)
                return
            if lic_status == 'paid':
                InfoBar.success(title='VIP', content=lic_msg, parent=self, position=InfoBarPosition.TOP, duration=5000)
                return
            if lic_status == 'trial':
                InfoBar.warning(title='Dùng thử', content=lic_msg, parent=self, position=InfoBarPosition.TOP, duration=7000)
                return
            InfoBar.error(title='Hết hạn', content=lic_msg if lic_msg else 'Video sẽ kèm Logo (Hãy nâng cấp để mở khóa)', parent=self, position=InfoBarPosition.TOP, duration=10000)

        def check_update(self):
            has_update, info = security.check_for_update(APP_VERSION)
            if has_update:
                from qfluentwidgets import (MessageBoxBase, SubtitleLabel, BodyLabel)
                import webbrowser
                class UpdateDialog(MessageBoxBase):
                    def __init__(self, info, parent=None):
                        super().__init__(parent)
                        self.titleLabel = SubtitleLabel('PHÁT HIỆN PHIÊN BẢN MỚI!', self)
                        self.titleLabel.setStyleSheet('color: #00ffcc;')
                        version_text = f'Bản của bạn: v{APP_VERSION}  -  Bản mới nhất: v{info.get("version", "?")}'
                        self.versionLabel = BodyLabel(version_text, self)
                        self.versionLabel.setStyleSheet('color: #ffaa00; font-weight: bold;')
                        self.msgLabel = BodyLabel(info.get('message', 'Có bản cập nhật mới!'), self)
                        self.msgLabel.setWordWrap(True)
                        self.viewLayout.addWidget(self.titleLabel)
                        self.viewLayout.addWidget(self.versionLabel)
                        self.viewLayout.addWidget(self.msgLabel)
                        self.yesButton.setText('Cập Nhật Ngay')
                        self.cancelButton.setText('Bỏ qua')
                        self.widget.setMinimumWidth(350)


                dlg = UpdateDialog(info, self)
                if dlg.exec():
                    if info.get('url'):
                        webbrowser.open(info['url'])

        def initNavigation(self):
            self.addSubInterface(self.homeInterface, FIF.HOME, 'Trang chủ')
            self.addSubInterface(self.libraryInterface, FIF.VIDEO, 'Quản lý Video')
            self.addSubInterface(self.highlightInterface, FIF.FOLDER, 'Cắt Highlight')
            self.addSubInterface(self.splitterInterface, FIF.CUT, 'Chia tập cho Video')
            self.addSubInterface(self.douyinInterface, FIF.DOWNLOAD, 'Tải Douyin/TikTok/Bili')
            self.addSubInterface(self.ttsInterface, FIF.MICROPHONE, 'Text to Speech')
            self.addSubInterface(self.dictInterface, FIF.BOOK_SHELF, 'Từ điển Phát âm')
            self.addSubInterface(self.reportInterface, FIF.FEEDBACK, 'Báo lỗi / Hỗ trợ', NavigationItemPosition.BOTTOM)
            self.addSubInterface(self.settingInterface, FIF.SETTING, 'Cài đặt', NavigationItemPosition.BOTTOM)
            from PyQt6.QtGui import QFontMetrics
            fm = QFontMetrics(self.font())
            menu_items = ['Trang chủ', 'Quản lý Video', 'Cắt Highlight', 'Chia tập cho Video', 'Tải Douyin/TikTok/Bili', 'Text to Speech', 'Từ điển Phát âm', 'Cài đặt', 'Báo lỗi / Hỗ trợ']
            max_text_width = max((fm.horizontalAdvance(text) for text in menu_items))
            optimal_width = max_text_width + 80
            try:
                self.navigationInterface.setExpandWidth(optimal_width)
            except Exception:
                pass
            if hasattr(self.navigationInterface, 'setReturnButtonVisible'):
                self.navigationInterface.setReturnButtonVisible(False)
                return
            if hasattr(self.navigationInterface.panel, 'setReturnButtonVisible'):
                self.navigationInterface.panel.setReturnButtonVisible(False)

        def initWindow(self):
            self.resize(1200, 700)
            icon_path = get_icon_path()
            png_icon_path = get_png_icon_path()
            if os.path.exists(png_icon_path):
                self.setWindowIcon(QIcon(png_icon_path))
            if os.path.exists(icon_path):
                force_native_taskbar_icon(self, icon_path)
            self.setWindowTitle(f'luaVietsup v{APP_VERSION}')
            desktop = QApplication.primaryScreen().availableGeometry()
            w, h = desktop.width(), desktop.height()
            self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
            self.splashScreen = SplashScreen(self.windowIcon(), self)
            self.splashScreen.setIconSize(QSize(102, 102))
            self.splashScreen.raise_()

        def closeEvent(self, event):
            is_running = False
            if hasattr(self, 'homeInterface') and hasattr(self.homeInterface, 'btn_cancel') and self.homeInterface.btn_cancel.isEnabled():
                is_running = True
            from qfluentwidgets import MessageBox
            title = 'Xác nhận thoát'
            if is_running:
                content = 'Hệ thống đang xử lý công việc. Bạn có chắc chắn muốn hủy bỏ toàn bộ và thoát ứng dụng không?'
            else:
                content = 'Bạn có chắc chắn muốn thoát ứng dụng không?'
            w = MessageBox(title, content, self.window())
            w.yesButton.setText('Có')
            w.cancelButton.setText('Hong')
            if not w.exec():
                event.ignore()
                return
            if is_running:
                self.homeInterface._onCancelClicked()
                import time
                time.sleep(0.5)
            if hasattr(self.libraryInterface, 'current_ai_worker') and self.libraryInterface.current_ai_worker:
                self.libraryInterface.current_ai_worker.cancel()
            if hasattr(self.highlightInterface, 'worker') and self.highlightInterface.worker:
                self.highlightInterface.worker.cancel()
            if hasattr(self, 'douyinInterface') and hasattr(self.douyinInterface, 'image_worker') and self.douyinInterface.image_worker:
                self.douyinInterface.image_worker.stop()
                self.douyinInterface.image_worker.quit()
                self.douyinInterface.image_worker.wait(1000)
            if hasattr(self, 'ttsInterface') and hasattr(self.ttsInterface, 'worker') and self.ttsInterface.worker:
                self.ttsInterface.worker.cancel()
                self.ttsInterface.worker.quit()
                self.ttsInterface.worker.wait(1000)
            super().closeEvent(event)


    w = MainWindow(license_status, license_msg)
    w.show()
    splash.close()
    app.exec()
