import os
import re
from PyQt6.QtCore import (Qt, pyqtSignal, QSize)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QLabel)
from qfluentwidgets import (CardWidget, LineEdit, TextEdit, PushButton, ProgressBar, InfoBar, InfoBarPosition, SubtitleLabel, BodyLabel, qconfig, PrimaryPushButton, ComboBox, SwitchButton, TransparentToolButton, FluentIcon, SmoothScrollArea)
from app.core.douyin_core import (DouyinScannerWorker, DouyinDownloadWorker, ImageLoaderWorker)

class DouyinInterface(SmoothScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('DouyinInterface')
        self.setWidgetResizable(True)
        self.setStyleSheet('QScrollArea { background-color: transparent; border: none; }')
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.scanned_video = None
        self.setup_ui()
        self.load_config()
        self.image_worker = ImageLoaderWorker(self)
        self.image_worker.finished_image.connect(self.on_image_loaded)
        self.image_worker.start()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.title_label = SubtitleLabel('Tải Video Douyin / TikTok / Bilibili (BETA)', self)
        self.main_layout.addWidget(self.title_label)
        self.beta_warning_label = BodyLabel('Tính năng đang phát triển. Có thể phát sinh một số lỗi khi tải video.', self)
        self.beta_warning_label.setStyleSheet('color: #ff9900; font-style: italic;')
        self.main_layout.addWidget(self.beta_warning_label)
        self.settings_card = CardWidget(self)
        self.settings_layout = QHBoxLayout(self.settings_card)
        self.settings_layout.setContentsMargins(20, 20, 20, 20)
        self.settings_layout.setSpacing(20)
        self.left_col_layout = QVBoxLayout()
        self.left_col_layout.setSpacing(10)
        self.left_col_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.left_col_layout.addWidget(SubtitleLabel('Thư Mục Lưu Video', self.settings_card))
        self.dir_input = LineEdit(self.settings_card)
        self.dir_input.setPlaceholderText('Chọn thư mục lưu...')
        self.dir_input.setReadOnly(True)
        self.left_col_layout.addWidget(self.dir_input)
        self.dir_btn_layout = QHBoxLayout()
        self.btn_choose_dir = PushButton('Chọn thư mục', self.settings_card)
        self.btn_choose_dir.clicked.connect(self.choose_directory)
        self.btn_open_dir = PushButton('Mở', self.settings_card)
        self.btn_open_dir.clicked.connect(self.open_directory)
        self.dir_btn_layout.addWidget(self.btn_choose_dir)
        self.dir_btn_layout.addWidget(self.btn_open_dir)
        self.dir_btn_layout.addStretch(1)
        self.left_col_layout.addLayout(self.dir_btn_layout)
        self.right_col_layout = QVBoxLayout()
        self.right_col_layout.setSpacing(10)
        self.right_col_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cookie_header_layout = QHBoxLayout()
        self.cookie_header_layout.addWidget(SubtitleLabel('Cookie Các Nền Tảng', self.settings_card))
        self.cookie_header_layout.addStretch(1)
        self.btn_cookie_guide = TransparentToolButton(FluentIcon.HELP, self.settings_card)
        self.btn_cookie_guide.setToolTip('Cách lấy Cookie?')
        self.btn_cookie_guide.clicked.connect(self.show_cookie_guide)
        self.cookie_header_layout.addWidget(self.btn_cookie_guide)
        self.right_col_layout.addLayout(self.cookie_header_layout)
        self.douyin_cookie_layout = QHBoxLayout()
        self.douyin_cookie_input = LineEdit(self.settings_card)
        self.douyin_cookie_input.setPlaceholderText('Cookie Douyin (.txt)')
        self.douyin_cookie_input.setReadOnly(True)
        self.btn_choose_douyin_cookie = PushButton('Chọn', self.settings_card)
        self.btn_choose_douyin_cookie.clicked.connect((lambda: self.choose_cookie_file(self.douyin_cookie_input, 'douyin_cookie_path')))
        self.btn_clear_douyin_cookie = PushButton('Xóa', self.settings_card)
        self.btn_clear_douyin_cookie.clicked.connect((lambda: self.clear_cookie(self.douyin_cookie_input, 'douyin_cookie_path')))
        self.douyin_cookie_layout.addWidget(self.douyin_cookie_input, 1)
        self.douyin_cookie_layout.addWidget(self.btn_choose_douyin_cookie)
        self.douyin_cookie_layout.addWidget(self.btn_clear_douyin_cookie)
        self.right_col_layout.addLayout(self.douyin_cookie_layout)
        self.tiktok_cookie_layout = QHBoxLayout()
        self.tiktok_cookie_input = LineEdit(self.settings_card)
        self.tiktok_cookie_input.setPlaceholderText('Cookie TikTok (.txt)')
        self.tiktok_cookie_input.setReadOnly(True)
        self.btn_choose_tiktok_cookie = PushButton('Chọn', self.settings_card)
        self.btn_choose_tiktok_cookie.clicked.connect((lambda: self.choose_cookie_file(self.tiktok_cookie_input, 'tiktok_cookie_path')))
        self.btn_clear_tiktok_cookie = PushButton('Xóa', self.settings_card)
        self.btn_clear_tiktok_cookie.clicked.connect((lambda: self.clear_cookie(self.tiktok_cookie_input, 'tiktok_cookie_path')))
        self.tiktok_cookie_layout.addWidget(self.tiktok_cookie_input, 1)
        self.tiktok_cookie_layout.addWidget(self.btn_choose_tiktok_cookie)
        self.tiktok_cookie_layout.addWidget(self.btn_clear_tiktok_cookie)
        self.right_col_layout.addLayout(self.tiktok_cookie_layout)
        self.bili_cookie_layout = QHBoxLayout()
        self.bili_cookie_input = LineEdit(self.settings_card)
        self.bili_cookie_input.setPlaceholderText('Cookie Bilibili VIP (.txt)')
        self.bili_cookie_input.setReadOnly(True)
        self.btn_choose_bili_cookie = PushButton('Chọn', self.settings_card)
        self.btn_choose_bili_cookie.clicked.connect((lambda: self.choose_cookie_file(self.bili_cookie_input, 'bilibili_cookie_path')))
        self.btn_clear_bili_cookie = PushButton('Xóa', self.settings_card)
        self.btn_clear_bili_cookie.clicked.connect((lambda: self.clear_cookie(self.bili_cookie_input, 'bilibili_cookie_path')))
        self.bili_cookie_layout.addWidget(self.bili_cookie_input, 1)
        self.bili_cookie_layout.addWidget(self.btn_choose_bili_cookie)
        self.bili_cookie_layout.addWidget(self.btn_clear_bili_cookie)
        self.right_col_layout.addLayout(self.bili_cookie_layout)
        self.settings_layout.addLayout(self.left_col_layout, 1)
        self.settings_layout.addLayout(self.right_col_layout, 1)
        self.main_layout.addWidget(self.settings_card)
        self.scan_card = CardWidget(self)
        self.scan_layout = QHBoxLayout(self.scan_card)
        self.scan_layout.setContentsMargins(20, 20, 20, 20)
        self.scan_layout.setSpacing(10)
        self.link_input = TextEdit(self.scan_card)
        self.link_input.setPlaceholderText('Dán link video (mỗi link một dòng). Hỗ trợ Douyin, TikTok, Bilibili...')
        self.link_input.setFixedHeight(100)
        self.link_input.setAcceptRichText(False)
        self.btn_scan = PrimaryPushButton('Tải', self.scan_card)
        self.btn_scan.clicked.connect(self.start_scan)
        self.scan_layout.addWidget(self.link_input, 1)
        self.scan_layout.addWidget(self.btn_scan)
        self.main_layout.addWidget(self.scan_card)
        self.status_label = BodyLabel('', self)
        self.status_label.setStyleSheet('color: #94A3B8;')
        self.main_layout.addWidget(self.status_label)
        self.result_card = CardWidget(self)
        self.result_layout = QVBoxLayout(self.result_card)
        self.result_layout.setContentsMargins(20, 20, 20, 20)
        self.result_layout.setSpacing(15)
        self.info_layout = QHBoxLayout()
        self.cover_label = QLabel(self.result_card)
        self.cover_label.setFixedSize(120, 160)
        self.cover_label.setStyleSheet('background-color: #2D2D2D; border-radius: 8px;')
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setText('No Image')
        self.title_result_label = BodyLabel('', self.result_card)
        self.title_result_label.setWordWrap(True)
        self.title_result_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        self.info_layout.addWidget(self.cover_label)
        self.info_layout.addWidget(self.title_result_label, 1)
        self.result_layout.addLayout(self.info_layout)
        self.progress_bar = ProgressBar(self.result_card)
        self.progress_bar.hide()
        self.result_layout.addWidget(self.progress_bar)
        self.speed_label = BodyLabel('', self.result_card)
        self.speed_label.setStyleSheet('color: #94A3B8; font-size: 12px;')
        self.speed_label.hide()
        self.result_layout.addWidget(self.speed_label)
        self.download_options_layout = QHBoxLayout()
        self.quality_combo = ComboBox(self.result_card)
        self.quality_combo.setFixedWidth(250)
        self.download_options_layout.addWidget(BodyLabel('Chọn Chất lượng tải xuống:', self.result_card))
        self.download_options_layout.addWidget(self.quality_combo)
        self.download_options_layout.addStretch(1)
        self.result_layout.addLayout(self.download_options_layout)
        self.download_btn_layout = QHBoxLayout()
        self.download_btn_layout.setSpacing(10)
        self.btn_download = PrimaryPushButton('Tải Xuống Ngay', self.result_card)
        self.btn_download.clicked.connect(self.start_download)
        self.btn_cancel = PushButton('Hủy', self.result_card)
        self.btn_cancel.clicked.connect(self.cancel_download)
        self.btn_cancel.hide()
        self.download_btn_layout.addWidget(self.btn_download, 1)
        self.download_btn_layout.addWidget(self.btn_cancel)
        self.result_layout.addLayout(self.download_btn_layout)
        self.result_card.hide()
        self.main_layout.addWidget(self.result_card)
        self.main_layout.addStretch(1)

    def load_config(self):
        from app.common.config_manager import load_config
        self.config = load_config()
        saved_dir = self.config.get('douyin_save_dir', '')
        if saved_dir and os.path.exists(saved_dir):
            self.dir_input.setText(saved_dir)
        douyin_cookie = self.config.get('douyin_cookie_path', '')
        if os.path.exists(douyin_cookie):
            self.douyin_cookie_input.setText(douyin_cookie)
        tiktok_cookie = self.config.get('tiktok_cookie_path', '')
        if os.path.exists(tiktok_cookie):
            self.tiktok_cookie_input.setText(tiktok_cookie)
        bilibili_cookie = self.config.get('bilibili_cookie_path', '')
        if os.path.exists(bilibili_cookie):
            self.bili_cookie_input.setText(bilibili_cookie)

    def choose_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục lưu video')
        if dir_path:
            self.dir_input.setText(dir_path)
            from app.common.config_manager import save_config
            self.config['douyin_save_dir'] = dir_path
            save_config(self.config)

    def choose_cookie_file(self, input_widget, config_key):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Chọn file Netscape Cookie', '', 'Text Files (*.txt);;All Files (*)')
        if file_path:
            input_widget.setText(file_path)
            from app.common.config_manager import save_config
            self.config[config_key] = file_path
            save_config(self.config)

    def clear_cookie(self, input_widget, config_key):
        input_widget.setText('')
        from app.common.config_manager import save_config
        self.config[config_key] = ''
        save_config(self.config)

    def show_cookie_guide(self):
        from qfluentwidgets import MessageBox
        title = 'Hướng Dẫn Lấy File Cookie'
        content = "<b>Lưu ý:</b> Nếu tải video bị lỗi thì bạn nên thêm Cookies, và nên lấy Cookies khi nền tảng đó đã được đăng nhập!<br><br>Cách lấy file Cookie:<br>1. Bấm vào <a href='https://chromewebstore.google.com/detail/cclelndahbckbenkjhflpdbgdldlbecc?utm_source=item-share-cb'><b>Link Này</b></a> để cài tiện ích 'Get cookies.txt LOCALLY' vào Chrome hoặc Edge.<br>2. Mở một thẻ (tab) mới, vào trang web bạn muốn lấy cookie (ví dụ douyin.com) và <b>đăng nhập tài khoản</b> của bạn trên web đó.<br>3. Nhìn lên góc phải trên cùng của trình duyệt (chỗ biểu tượng hình mảnh ghép), bấm vào tiện ích vừa cài và chọn <b>Export</b>. Sẽ có 1 file tên là <i>cookies.txt</i> được tải về máy.<br>4. Quay lại phần mềm này, bấm nút <b>Chọn</b> và tìm đến tên file <i>cookies.txt</i> vừa tải về là xong!"
        msg_box = MessageBox(title, content, self.window())
        msg_box.yesButton.setText('Đã Hiểu')
        msg_box.cancelButton.hide()
        if hasattr(msg_box, 'contentLabel'):
            msg_box.contentLabel.setOpenExternalLinks(True)
        msg_box.exec()

    def open_directory(self):
        save_dir = self.dir_input.text().strip()
        if save_dir and os.path.exists(save_dir):
            try:
                os.startfile(save_dir)
            except:
                pass

    def start_scan(self):
        text = self.link_input.toPlainText().strip()
        if not text:
            InfoBar.warning('Thiếu thông tin', 'Vui lòng nhập link trước khi quét!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        url_pattern = re.compile('https?://[^\\s]+')
        links = url_pattern.findall(text)
        if not links:
            InfoBar.error('Lỗi', 'Không tìm thấy đường link nào hợp lệ trong văn bản!', parent=self.window(), position=InfoBarPosition.TOP)
            return
        seen = set()
        unique_links = []
        for l in links:
            if l not in seen:
                unique_links.append(l)
                seen.add(l)
        links = unique_links
        self.last_scanned_links_count = len(links)
        self.btn_scan.setEnabled(False)
        self.result_card.hide()
        self.status_label.setText(f'Đang phân tích {len(links)} link...')
        cookies = []
        if self.douyin_cookie_input.text().strip():
            cookies.append(self.douyin_cookie_input.text().strip())
        if self.tiktok_cookie_input.text().strip():
            cookies.append(self.tiktok_cookie_input.text().strip())
        if self.bili_cookie_input.text().strip():
            cookies.append(self.bili_cookie_input.text().strip())
        cookie_file = ';'.join(cookies)
        self.scanner = DouyinScannerWorker(links, cookie_file, self)
        self.scanner.log.connect(self.status_label.setText)
        self.scanner.error.connect(self.on_scan_error)
        self.scanner.finished_urls.connect(self.on_scan_success)
        self.scanner.start()

    def on_scan_error(self, err):
        self.btn_scan.setEnabled(True)
        InfoBar.error('Lỗi quét video', err, parent=self.window(), position=InfoBarPosition.TOP)
        self.status_label.setText(f'Lỗi: {err}')

    def on_scan_success(self, vids):
        self.btn_scan.setEnabled(True)
        total_input = getattr(self, 'last_scanned_links_count', len(vids))
        failed = total_input - len(vids)
        if not vids:
            if failed > 0:
                self.on_scan_error(f'Bỏ qua toàn bộ {failed} link (link lỗi)!')
                return
            self.on_scan_error('Không tìm thấy video nào hợp lệ từ danh sách!')
            return
        self.scanned_videos = vids
        if total_input == 1 and len(vids) == 1:
            self.title_result_label.setText(vids[0]['title'])
            self.cover_label.show()
            self.cover_label.setText('Đang tải ảnh...')
            if vids[0].get('cover'):
                self.image_worker.add_task(0, vids[0]['cover'])
            status_text = 'Bạn có thể tải video ngay.'
        else:
            self.cover_label.hide()
            title_text = f'Tìm thấy {len(vids)} video hợp lệ.'
            if faile"""
Template for creating a PyTorch Lightning DataModule.

This template provides a complete boilerplate for building a LightningDataModule
with all essential methods and best practices for data handling.
"""

import lightning as L
from torch.utils.data import Dataset, DataLoader, random_split
import torch


class CustomDataset(Dataset):
    """
    Custom Dataset implementation.

    Replace this with your actual dataset implementation.
    """

    def __init__(self, data_path, transform=None):
        """
        Initialize the dataset.

        Args:
            data_path: Path to data directory
            transform: Optional transforms to apply
        """
        self.data_path = data_path
        self.transform = transform

        # Load your data here
        # self.data = load_data(data_path)
        # self.labels = load_labels(data_path)

        # Placeholder data
        self.data = torch.randn(1000, 3, 224, 224)
        self.labels = torch.randint(0, 10, (1000,))

    def __len__(self):
        """Return the size of the dataset."""
        return len(self.data)

    def __getitem__(self, idx):
        """
        Get a single item from the dataset.

        Args:
            idx: Index of the item

        Returns:
            Tuple of (data, label)
        """
        sample = self.data[idx]
        label = self.labels[idx]

        if self.transform:
            sample = self.transform(sample)

        return sample, label


class TemplateDataModule(L.LightningDataModule):
    """
    Template LightningDataModule for data handling.

    This class encapsulates all data processing steps:
    1. Download/prepare data (prepare_data)
    2. Create datasets (setup)
    3. Create dataloaders (train/val/test/predict_dataloader)

    Args:
        data_dir: Directory containing the data
        batch_size: Batch size for dataloaders
        num_workers: Number of workers for data loading
        train_val_split: Train/validation split ratio
        pin_memory: Whether to pin memory for faster GPU transfer
    """

    def __init__(
        self,
        data_dir: str = "./data",
        batch_size: int = 32,
        num_workers: int = 4,
        train_val_split: float = 0.8,
        pin_memory: bool = True,
    ):
        super().__init__()

        # Save hyperparameters
        self.save_hyperparameters()

        # Initialize as None (will be set in setup)
        self.train_dataset = None
        self.val_dataset = None
        self.test_dataset = None
        self.predict_dataset = None

    def prepare_data(self):
        """
        Download and prepare data.

        This method is called only once and on a single process.
        Do not set state here (e.g., self.x = y) because it's not
        transferred to other processes.

        Use this for:
        - Downloading datasets
        - Tokenizing text
        - Saving processed data to disk
        """
        # Example: Download data if not exists
        # if not os.path.exists(self.hparams.data_dir):
        #     download_dataset(self.hparams.data_dir)

        # Example: Process and save data
        # process_and_save(self.hparams.data_dir)

        pass

    def setup(self, stage: str = None):
        """
        Create datasets for each stage.

        This method is called on every process in distributed training.
        Set state here (e.g., self.train_dataset = ...).

        Args:
            stage: Current stage ('fit', 'validate', 'test', or 'predict')
        """
        # Define transforms
        train_transform = self._get_train_transforms()
        test_transform = self._get_test_transforms()

        # Setup for training and validation
        if stage == "fit" or stage is None:
            # Load full dataset
            full_dataset = CustomDataset(
                self.hparams.data_dir, transform=train_transform
            )

            # Split into train and validation
            train_size = int(self.hparams.train_val_split * len(full_dataset))
            val_size = len(full_dataset) - train_size

            self.train_dataset, self.val_dataset = random_split(
                full_dataset,
                [train_size, val_size],
                generator=torch.Generator().manual_seed(42),
            )

            # Apply test transforms to validation set
            # (Note: random_split doesn't support different transforms,
            # you may need to implement a custom wrapper)

        # Setup for testing
        if stage == "test" or stage is None:
            self.test_dataset = CustomDataset(
                self.hparams.data_dir, transform=test_transform
            )

        # Setup for prediction
        if stage == "predict":
            self.predict_dataset = CustomDataset(
                self.hparams.data_dir, transform=test_transform
            )

    def _get_train_transforms(self):
        """
        Define training transforms/augmentations.

        Returns:
            Training transforms
        """
        # Example with torchvision:
        # from torchvision import transforms
        # return transforms.Compose([
        #     transforms.RandomHorizontalFlip(),
        #     transforms.RandomRotation(10),
        #     transforms.Normalize(mean=[0.485, 0.456, 0.406],
        #                         std=[0.229, 0.224, 0.225])
        # ])

        return None

    def _get_test_transforms(self):
        """
        Define test/validation transforms (no augmentation).

        Returns:
            Test/validation transforms
        """
        # Example with torchvision:
        # from torchvision import transforms
        # return transforms.Compose([
        #     transforms.Normalize(mean=[0.485, 0.456, 0.406],
        #                         std=[0.229, 0.224, 0.225])
        # ])

        return None

    def train_dataloader(self):
        """
        Create training dataloader.

        Returns:
            Training DataLoader
        """
        return DataLoader(
            self.train_dataset,
            batch_size=self.hparams.batch_size,
            shuffle=True,
            num_workers=self.hparams.num_workers,
            pin_memory=self.hparams.pin_memory,
            persistent_workers=True if self.hparams.num_workers > 0 else Fals