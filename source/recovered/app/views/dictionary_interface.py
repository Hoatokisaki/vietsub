import os
import json
from PyQt6.QtCore import (Qt, pyqtSignal, QSize)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem, QAbstractItemView)
from qfluentwidgets import (ScrollArea, TitleLabel, BodyLabel, LineEdit, PrimaryPushButton, PushButton, TableWidget, InfoBar, InfoBarPosition, FluentIcon as FIF, CardWidget)
from app.common.config_manager import load_pronunciation_dict, save_pronunciation_dict

class DictionaryInterface(ScrollArea):
    ''' Giao diện Quản lý Từ điển Phát âm '''

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('DictionaryInterface')
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(30, 20, 30, 20)
        self.vBoxLayout.setSpacing(20)
        self.initUI()
        self.load_data()

    def initUI(self):
        titleLayout = QVBoxLayout()
        titleLayout.setSpacing(8)
        self.titleLabel = TitleLabel('Từ điển Phát âm Tùy chỉnh (TTS)', self)
        desc_text = 'Thêm các quy tắc đọc cho công cụ chuyển Văn bản thành Giọng nói (TTS).\nVí dụ:\n  - Từ gốc: main    ->  Cách đọc: mên\n  - Từ gốc: pro     ->  Cách đọc: pờ rồ\nDùng phím Ctrl + Click, Shift + Click hoặc Ctrl + A để chọn nhiều file khi xóa.'
        self.descLabel = BodyLabel(desc_text, self)
        self.descLabel.setStyleSheet('color: #94A3B8; line-height: 1.5;')
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addWidget(self.descLabel)
        self.vBoxLayout.addLayout(titleLayout)
        self.card = CardWidget(self)
        cardLayout = QHBoxLayout(self.card)
        cardLayout.setContentsMargins(15, 15, 15, 15)
        cardLayout.setSpacing(15)
        self.originalInput = LineEdit(self.card)
        self.originalInput.setPlaceholderText('Từ gốc (VD: main)')
        self.originalInput.setClearButtonEnabled(True)
        self.pronounceInput = LineEdit(self.card)
        self.pronounceInput.setPlaceholderText('Cách đọc (VD: mên)')
        self.pronounceInput.setClearButtonEnabled(True)
        self.btnAdd = PrimaryPushButton('Thêm', self.card)
        self.btnAdd.setIcon(FIF.ADD)
        self.btnAdd.clicked.connect(self.add_word)
        cardLayout.addWidget(self.originalInput, 1)
        cardLayout.addWidget(self.pronounceInput, 1)
        cardLayout.addWidget(self.btnAdd)
        self.vBoxLayout.addWidget(self.card)
        self.table = TableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(['Từ Gốc', 'Cách Đọc'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.vBoxLayout.addWidget(self.table)
        btnLayout = QHBoxLayout()
        self.btnDelete = PushButton('Xóa từ đã chọn', self)
        self.btnDelete.setIcon(FIF.DELETE)
        self.btnDelete.clicked.connect(self.delete_selected)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.btnDelete)
        self.vBoxLayout.addLayout(btnLayout)

    def load_data(self):
        self.table.setRowCount(0)
        data = load_pronunciation_dict()
        for word, pronounce in data.items():
            self._add_row_to_table(word, pronounce)

    def _add_row_to_table(self, word, pronounce):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(word))
        self.table.setItem(row, 1, QTableWidgetItem(pronounce))

    def add_word(self):
        word = self.originalInput.text().strip()
        pronounce = self.pronounceInput.text().strip()
        if not word or not pronounce:
            InfoBar.warning(title='Lỗi', content='Vui lòng nhập đầy đủ Từ gốc và Cách đọc!', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self)
            return
        data = load_pronunciation_dict()
        data[word] = pronounce
        if save_pronunciation_dict(data):
            self.load_data()
            self.originalInput.clear()
            self.pronounceInput.clear()
            self.originalInput.setFocus()
            InfoBar.success(title='Thành công', content=f'Đã thêm từ \'{word}\' thành công!', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self)

    def delete_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        rows = set()
        for item in selected_items:
            rows.add(item.row())
        data = load_pronunciation_dict()
        deleted_words = []
        for row in sorted(rows, reverse=True):
            word = self.table.item(row, 0).text()
            if word in data:
                del data[word]
                deleted_words.append(word)
        if save_pronunciation_dict(data):
            self.load_data()
            InfoBar.success(title='Thành công', content=f'Đã xóa {len(deleted_words)} từ!', orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self)


