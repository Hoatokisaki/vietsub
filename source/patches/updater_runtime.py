# -*- coding: utf-8 -*-
"""Online Update System for luaVietsup.

Provides:
- Check for updates online (via Remote URL, Supabase, or GitHub release).
- Interactive GUI dialog with Changelog and one-click update.
- Real-time progress bar (download speed, percentage, size).
- Seamless auto-updater for both Quick Patches (.zip) and Full Installers (.exe).
- Settings Card integration inside SettingInterface.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QWidget,
    QFrame,
)
from qfluentwidgets import (
    CardWidget,
    SubtitleLabel,
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    PushButton,
    PrimaryPushButton,
    ProgressBar,
    InfoBar,
    InfoBarPosition,
    MessageBox,
)
from qfluentwidgets import FluentIcon as FIF


# Default remote update manifest endpoint
DEFAULT_UPDATE_CONFIG_FILE = "update_config.json"
FALLBACK_UPDATE_URL = "https://raw.githubusercontent.com/luavietsup/releases/main/version.json"


def get_app_dir() -> Path:
    """Return the base root installation directory of luaVietsup."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_update_config_candidates():
    """Look for update_config.json in _internal, app dir, or AppData."""
    app_dir = get_app_dir()
    yield app_dir / "_internal" / DEFAULT_UPDATE_CONFIG_FILE
    yield app_dir / DEFAULT_UPDATE_CONFIG_FILE
    yield Path(__file__).resolve().parent / DEFAULT_UPDATE_CONFIG_FILE
    user_appdata = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    yield user_appdata / "luaVietsup" / DEFAULT_UPDATE_CONFIG_FILE


def load_update_config() -> dict:
    """Load configuration for updates (URLs, options)."""
    for p in get_update_config_candidates():
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


def get_update_url() -> str:
    """Determine the authoritative update URL."""
    cfg = load_update_config()
    url = str(cfg.get("update_url", "")).strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    
    # Check if supabase is configured
    try:
        from license_runtime import load_service_config
        s_cfg = load_service_config()
        if s_cfg.get("url"):
            # Supabase edge function for update
            return s_cfg["url"].rstrip("/") + "/functions/v1/app-update"
    except Exception:
        pass

    return FALLBACK_UPDATE_URL


def parse_version_tuple(v_str: str) -> tuple[int, ...]:
    """Convert version string like '2.6' or '2.6.1' to a comparable tuple of integers."""
    import re
    cleaned = re.sub(r"[^\d.]", "", str(v_str).strip())
    parts = []
    for part in cleaned.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(0)
    return tuple(parts) if parts else (0,)


def is_newer_version(remote_v: str, local_v: str) -> bool:
    """Return True if remote_v is strictly greater than local_v."""
    try:
        return parse_version_tuple(remote_v) > parse_version_tuple(local_v)
    except Exception:
        return False


def fetch_remote_manifest(url: str, timeout: float = 6.0) -> dict | None:
    """Fetch update manifest from URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "luaVietsup-Updater/2.6 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
            },
        )
        # Check if supabase key should be attached
        try:
            from license_runtime import load_service_config
            s_cfg = load_service_config()
            if s_cfg.get("url") and s_cfg["url"] in url and s_cfg.get("publishable_key"):
                req.add_header("apikey", s_cfg["publishable_key"])
                req.add_header("Authorization", "Bearer " + s_cfg["publishable_key"])
        except Exception:
            pass

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def check_for_updates(current_version: str) -> tuple[bool, dict | None, str]:
    """Check online server for available update.
    
    Returns:
        (has_update: bool, update_info: dict | None, status_message: str)
    """
    url = get_update_url()
    manifest = fetch_remote_manifest(url)
    
    if not manifest:
        # If primary failed, try fallback
        if url != FALLBACK_UPDATE_URL:
            manifest = fetch_remote_manifest(FALLBACK_UPDATE_URL, timeout=4.0)

    if not manifest:
        return False, None, "Không thể kết nối đến máy chủ cập nhật. Vui lòng kiểm tra lại kết nối mạng."

    remote_version = str(manifest.get("version", "")).strip()
    if not remote_version:
        return False, None, "Dữ liệu phiên bản trên máy chủ không hợp lệ."

    if is_newer_version(remote_version, current_version):
        return True, manifest, f"Đã có phiên bản mới: v{remote_version}"
    
    return False, manifest, f"Bạn đang sử dụng phiên bản mới nhất (v{current_version})."


class DownloadWorker(QThread):
    """Background download worker with speed and percentage reporting."""
    progress = pyqtSignal(int, float, float, float)  # percent, downloaded_mb, total_mb, speed_mb_s
    finished = pyqtSignal(str)                       # destination file path
    error = pyqtSignal(str)                          # error description

    def __init__(self, download_url: str, target_filename: str = "", parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.target_filename = target_filename
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            temp_dir = Path(tempfile.gettempdir()) / "luaVietsup_update"
            temp_dir.mkdir(parents=True, exist_ok=True)

            fname = self.target_filename
            if not fname:
                fname = os.path.basename(self.download_url.split("?")[0]) or "update_package.bin"
            
            dest_file = temp_dir / fname

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "luaVietsup-Updater (Windows NT 10.0)"},
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                total_bytes = int(resp.headers.get("Content-Length") or 0)
                downloaded_bytes = 0
                chunk_size = 64 * 1024  # 64 KB
                start_time = time.time()
                last_time = start_time

                with open(dest_file, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            dest_file.unlink(missing_ok=True)
                            self.error.emit("Quá trình tải đã bị hủy.")
                            return

                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded_bytes += len(chunk)

                        now = time.time()
                        if now - last_time >= 0.2 or downloaded_bytes == total_bytes:
                            duration = max(0.001, now - start_time)
                            speed_mb = (downloaded_bytes / (1024 * 1024)) / duration
                            pct = int((downloaded_bytes / total_bytes * 100)) if total_bytes > 0 else 0
                            mb_down = downloaded_bytes / (1024 * 1024)
                            mb_tot = total_bytes / (1024 * 1024)
                            self.progress.emit(pct, mb_down, mb_tot, speed_mb)
                            last_time = now

            self.finished.emit(str(dest_file))
        except Exception as exc:
            self.error.emit(f"Lỗi tải dữ liệu: {exc}")


def apply_update_package(file_path: str, update_info: dict, parent_window=None) -> bool:
    """Apply the downloaded update.
    
    If .exe -> run installer and quit current app.
    If .zip -> spawn extraction batch script and restart app.
    """
    path = Path(file_path)
    if not path.is_file():
        return False

    app_dir = get_app_dir()
    is_exe = path.suffix.lower() == ".exe" or update_info.get("type") == "installer"

    if is_exe:
        # Launch setup executable and terminate this instance
        try:
            cmd = [str(path)]
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0)
            if parent_window:
                parent_window.close()
            QApplication.quit()
            return True
        except Exception as exc:
            if parent_window:
                InfoBar.error(
                    title="Lỗi khởi chạy bộ cài đặt",
                    content=str(exc),
                    parent=parent_window,
                    position=InfoBarPosition.TOP,
                    duration=8000,
                )
            return False

    # Handle .zip patch
    try:
        batch_script = Path(tempfile.gettempdir()) / "luaVietsup_update" / "apply_patch.bat"
        main_exe_name = "luaVietsup-ModelFix4.exe"
        main_exe_path = app_dir / main_exe_name

        script_content = f"""@echo off
chcp 65001 >nul
echo Đang đợi ứng dụng luaVietsup đóng hoàn toàn...
timeout /t 2 /nobreak >nul

echo Đang áp dụng bản cập nhật vào {app_dir}...
tar -xf "{path}" -C "{app_dir}" --overwrite

if exist "{main_exe_path}" (
    echo Khởi động lại luaVietsup...
    start "" "{main_exe_path}"
)

del "%~f0"
exit
"""
        batch_script.write_text(script_content, encoding="utf-8")

        subprocess.Popen(["cmd.exe", "/c", str(batch_script)], creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0)
        if parent_window:
            parent_window.close()
        QApplication.quit()
        return True
    except Exception as exc:
        if parent_window:
            InfoBar.error(
                title="Lỗi áp dụng bản vá",
                content=str(exc),
                parent=parent_window,
                position=InfoBarPosition.TOP,
                duration=8000,
            )
        return False


class UpdateDialog(QDialog):
    """Modern modal dialog presenting update details and real-time download."""

    def __init__(self, current_version: str, update_info: dict, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.update_info = update_info
        self.worker: DownloadWorker | None = None
        self.downloaded_path = ""

        self.setWindowTitle("Cập nhật luaVietsup")
        self.setFixedSize(540, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Style matching luaVietsup dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #E2E8F0;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        # Header Title
        title_box = QHBoxLayout()
        lbl_badge = QLabel("NEW UPDATE")
        lbl_badge.setStyleSheet("""
            background-color: #3498db;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        
        new_ver = self.update_info.get("version", "Mới")
        lbl_title = SubtitleLabel(f"Đã có phiên bản mới: v{new_ver}")
        lbl_title.setStyleSheet("font-size: 19px; font-weight: bold; color: #FFFFFF;")
        
        title_box.addWidget(lbl_title)
        title_box.addSpacing(10)
        title_box.addWidget(lbl_badge)
        title_box.addStretch(1)
        layout.addLayout(title_box)

        # Version Compare row
        ver_box = QHBoxLayout()
        lbl_ver_compare = BodyLabel(
            f"Phiên bản của bạn: <b style='color:#94A3B8;'>v{self.current_version}</b>  ➜  "
            f"Phiên bản mới nhất: <b style='color:#38BDF8;'>v{new_ver}</b>"
        )
        ver_box.addWidget(lbl_ver_compare)
        layout.addLayout(ver_box)

        # Changelog Scroll Area
        lbl_change_title = StrongBodyLabel("Nhật ký cập nhật / Tính năng mới:")
        lbl_change_title.setStyleSheet("color: #38BDF8; font-weight: bold;")
        layout.addWidget(lbl_change_title)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #27272A;
                border: 1px solid #3F3F46;
                border-radius: 6px;
            }
        """)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(12, 12, 12, 12)

        raw_changelog = self.update_info.get("changelog", "Bản cập nhật tối ưu hiệu suất và cải thiện trải nghiệm.")
        lbl_changelog = QLabel(raw_changelog)
        lbl_changelog.setWordWrap(True)
        lbl_changelog.setStyleSheet("color: #E2E8F0; font-size: 13px; line-height: 1.4;")
        scroll_layout.addWidget(lbl_changelog)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Size & Release date info
        meta_box = QHBoxLayout()
        size_mb = self.update_info.get("size_mb", 0)
        rel_date = self.update_info.get("release_date", "")
        meta_text = ""
        if size_mb:
            meta_text += f"Dung lượng: ~{size_mb} MB   "
        if rel_date:
            meta_text += f"Ngày phát hành: {rel_date}"
        if meta_text:
            lbl_meta = CaptionLabel(meta_text)
            lbl_meta.setStyleSheet("color: #A1A1AA;")
            meta_box.addWidget(lbl_meta)
        layout.addLayout(meta_box)

        # Progress bar container (hidden initially)
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(6)

        self.lbl_progress_status = BodyLabel("Đang chuẩn bị tải dữ liệu...")
        self.lbl_progress_status.setStyleSheet("color: #38BDF8; font-size: 12px;")
        self.progress_bar = ProgressBar()
        self.progress_bar.setValue(0)

        prog_layout.addWidget(self.lbl_progress_status)
        prog_layout.addWidget(self.progress_bar)
        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        # Buttons
        self.btn_box = QHBoxLayout()
        self.btn_box.setSpacing(12)

        self.btn_browser = PushButton("Mở link tải ngoài", self)
        self.btn_browser.setToolTip("Mở trình duyệt tải thủ công nếu mạng chập chờn")
        self.btn_browser.clicked.connect(self._open_in_browser)

        self.btn_cancel = PushButton("Để sau", self)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_update = PrimaryPushButton("Cập nhật Online ngay", self)
        self.btn_update.setStyleSheet("background-color: #3498db; color: #FFFFFF; font-weight: bold;")
        self.btn_update.clicked.connect(self._start_download)

        self.btn_box.addWidget(self.btn_browser)
        self.btn_box.addStretch(1)
        self.btn_box.addWidget(self.btn_cancel)
        self.btn_box.addWidget(self.btn_update)
        layout.addLayout(self.btn_box)

    def _open_in_browser(self):
        import webbrowser
        url = self.update_info.get("download_url") or self.update_info.get("url", "")
        if url:
            webbrowser.open(url)

    def _start_download(self):
        url = self.update_info.get("download_url") or self.update_info.get("url", "")
        if not url:
            InfoBar.warning(
                title="Thiếu liên kết tải",
                content="Chưa có đường dẫn tải cập nhật cho phiên bản này.",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )
            return

        self.btn_update.setEnabled(False)
        self.btn_browser.setEnabled(False)
        self.btn_cancel.setText("Hủy tải")
        self.progress_container.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText("Đang kết nối tới máy chủ cập nhật...")

        self.worker = DownloadWorker(url, parent=self)
        self.worker.progress.connect(self._on_download_progress)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.error.connect(self._on_download_error)
        self.worker.start()

    def _on_download_progress(self, percent: int, downloaded_mb: float, total_mb: float, speed_mb_s: float):
        self.progress_bar.setValue(percent)
        if total_mb > 0:
            self.lbl_progress_status.setText(
                f"Đang tải: {percent}% ({downloaded_mb:.1f} MB / {total_mb:.1f} MB) — Tốc độ: {speed_mb_s:.2f} MB/s"
            )
        else:
            self.lbl_progress_status.setText(f"Đã tải: {downloaded_mb:.1f} MB — Tốc độ: {speed_mb_s:.2f} MB/s")

    def _on_download_finished(self, file_path: str):
        self.downloaded_path = file_path
        self.progress_bar.setValue(100)
        self.lbl_progress_status.setText("Tải thành công! Đang tiến hành áp dụng cập nhật...")
        self.lbl_progress_status.setStyleSheet("color: #10B981; font-weight: bold;")
        
        QTimer.singleShot(800, self._apply_update)

    def _apply_update(self):
        ok = apply_update_package(self.downloaded_path, self.update_info, parent_window=self.parent())
        if ok:
            self.accept()
        else:
            self.btn_update.setEnabled(True)
            self.btn_cancel.setText("Đóng")

    def _on_download_error(self, err_msg: str):
        self.progress_container.setVisible(False)
        self.btn_update.setEnabled(True)
        self.btn_browser.setEnabled(True)
        self.btn_cancel.setText("Đóng")
        InfoBar.error(
            title="Lỗi tải cập nhật",
            content=err_msg,
            parent=self,
            position=InfoBarPosition.TOP,
            duration=7000,
        )

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        super().reject()


def setup_update_settings_ui(setting_interface, app_version: str):
    """Add a modern 'Software Update' Card Widget inside SettingInterface."""
    try:
        if getattr(setting_interface, "_update_ui_ready", False):
            return

        # Target page: page_account or page_general
        target_page = getattr(setting_interface, "page_account", None) or getattr(setting_interface, "page_general", None)
        if not target_page:
            return

        page_layout = target_page.layout()
        if not page_layout:
            return

        # Create Update Card
        card_update = CardWidget(target_page)
        layout_card = QVBoxLayout(card_update)
        layout_card.setSpacing(12)
        layout_card.setContentsMargins(16, 16, 16, 16)

        # Header
        row_title = QHBoxLayout()
        lbl_card_title = SubtitleLabel("Cập nhật Ứng dụng & Phiên bản", card_update)
        lbl_card_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        row_title.addWidget(lbl_card_title)
        row_title.addStretch(1)
        layout_card.addLayout(row_title)

        # Body details
        row_info = QHBoxLayout()
        lbl_curr_ver = BodyLabel(f"Phiên bản hiện tại: <b style='color:#38BDF8;'>v{app_version}</b>", card_update)
        lbl_curr_ver.setStyleSheet("font-size: 14px;")
        
        btn_check_update = PrimaryPushButton("Kiểm tra cập nhật ngay", card_update)
        btn_check_update.setIcon(FIF.SYNC)
        btn_check_update.setStyleSheet("background-color: #3498db; color: #FFFFFF; font-weight: bold; padding: 6px 14px;")

        row_info.addWidget(lbl_curr_ver)
        row_info.addStretch(1)
        row_info.addWidget(btn_check_update)
        layout_card.addLayout(row_info)

        # Status note
        lbl_desc = CaptionLabel(
            "Ứng dụng tự động kiểm tra bản mới khi khởi động. "
            "Bạn cũng có thể bấm nút trên để kiểm tra thủ công và cập nhật online ngay lập tức.",
            card_update
        )
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        lbl_desc.setWordWrap(True)
        layout_card.addWidget(lbl_desc)

        # Connect button click
        def _on_manual_check_clicked():
            btn_check_update.setEnabled(False)
            btn_check_update.setText("Đang kiểm tra...")
            QApplication.processEvents()

            try:
                has_update, info, msg = check_for_updates(app_version)
                if has_update and info:
                    dlg = UpdateDialog(app_version, info, parent=setting_interface.window())
                    dlg.exec()
                else:
                    InfoBar.success(
                        title="Phiên bản mới nhất",
                        content=msg,
                        parent=setting_interface.window(),
                        position=InfoBarPosition.TOP,
                        duration=5000,
                    )
            except Exception as exc:
                InfoBar.error(
                    title="Lỗi kiểm tra cập nhật",
                    content=str(exc),
                    parent=setting_interface.window(),
                    position=InfoBarPosition.TOP,
                    duration=6000,
                )
            finally:
                btn_check_update.setEnabled(True)
                btn_check_update.setText("Kiểm tra cập nhật ngay")

        btn_check_update.clicked.connect(_on_manual_check_clicked)

        # Insert Card: If page has group_license, place directly under it
        group_license = getattr(setting_interface, "group_license", None)
        inserted = False
        if group_license:
            idx = page_layout.indexOf(group_license)
            if idx >= 0:
                page_layout.insertWidget(idx + 1, card_update)
                inserted = True

        if not inserted:
            page_layout.addWidget(card_update)

        setting_interface._update_ui_ready = True
        setting_interface.card_update = card_update
    except Exception as exc:
        print("setup_update_settings_ui error:", exc)


def handle_app_start_update_check(window, app_version: str):
    """Background update check triggered at app startup."""
    try:
        has_update, info, msg = check_for_updates(app_version)
        if has_update and info:
            dlg = UpdateDialog(app_version, info, parent=window)
            dlg.exec()
    except Exception as exc:
        pass
