"""
基于 PySide6 + qtawesome 的主窗口：粘贴 URL→列出条目→逐行选清晰度→批量下载
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import qtawesome as qta
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QComboBox,
)

from .downloader import DownloaderWorker
from .formats import FormatsFetcher, VideoItem

log = logging.getLogger(__name__)

QUALITY_OPTIONS = ["best", "1080p", "720p", "480p", "audio"]


class MainWindow(QWidget):
    # -------- 自定义信号 --------
    _on_progress = Signal(float)           # 下载进度 0.0 – 1.0
    _on_status = Signal(str)               # 状态栏文本
    _on_finished = Signal(bool, object)    # 全部下载完成 (success, err)

    # -------- 初始化 --------
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Videos Downloader (yt-dlp GUI)")
        self.resize(820, 520)              # 稍宽一点，表格不拥挤

        self._setup_ui()
        self._connect_signals()

        self._worker: DownloaderWorker | None = None
        self._fetcher: FormatsFetcher | None = None

    # -------- UI 构建 --------
    def _setup_ui(self) -> None:
        # —— 输入行 —— #
        self.url_edit = QLineEdit(placeholderText="粘贴视频 / 播放列表 URL …")

        self.choose_btn = QPushButton()
        self.choose_btn.setIcon(qta.icon("fa5s.folder-open", color="#dcdcdc"))
        self.choose_btn.setToolTip("选择下载目录")

        self.output_edit = QLineEdit()

        self.download_btn = QPushButton("开始下载")
        self.download_btn.setIcon(qta.icon("fa5s.download", color="#dcdcdc"))

        # —— 状态 & 进度 —— #
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.status_label = QLabel("等待中…")

        # —— 列表 —— #
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["选择", "标题", "时长", "清晰度"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # —— 布局 —— #
        grid = QGridLayout()
        grid.addWidget(QLabel("视频地址："), 0, 0)
        grid.addWidget(self.url_edit, 0, 1, 1, 2)
        grid.addWidget(QLabel("保存到："), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        grid.addWidget(self.choose_btn, 1, 2)

        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self.download_btn)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        vbox.addLayout(grid)
        vbox.addWidget(self.table)
        vbox.addLayout(hbox)
        vbox.addWidget(self.progress)
        vbox.addWidget(self.status_label)

    # -------- 信号 / 槽 --------
    def _connect_signals(self) -> None:
        self.choose_btn.clicked.connect(self._choose_dir)
        self.download_btn.clicked.connect(self._start_download)

        self._on_progress.connect(self.progress.setValue)
        self._on_status.connect(self.status_label.setText)
        self._on_finished.connect(self._on_download_finished)

        # 地址行回车或失焦时自动解析列表
        self.url_edit.editingFinished.connect(self._fetch_entries)

    # -------- 获取条目列表 --------
    def _fetch_entries(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            return

        self._on_status.emit("正在获取视频列表…")
        self.table.setRowCount(0)

        self._fetcher = FormatsFetcher(url)
        self._fetcher.result_sig.connect(self._populate_table)
        self._fetcher.error_sig.connect(lambda e: QMessageBox.critical(self, "获取失败", e))
        self._fetcher.start()

    @Slot(list)
    def _populate_table(self, items: List[VideoItem]) -> None:
        self.table.setRowCount(len(items))

        for row, itm in enumerate(items):
            # 0 选择列：复选框
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.Unchecked if row else Qt.Checked)  # 默认勾选首行
            self.table.setItem(row, 0, chk)

            # 1 标题列：显示 title，UserRole 存真实 URL
            cell_title = QTableWidgetItem(itm["title"])
            cell_title.setData(Qt.UserRole, itm["url"])
            self.table.setItem(row, 1, cell_title)

            # 2 时长列：mm:ss
            dur = itm["duration"]
            dur_str = "-" if dur is None else f"{int(dur)//60}:{int(dur)%60:02}"
            self.table.setItem(row, 2, QTableWidgetItem(dur_str))

            # 3 清晰度列：ComboBox（默认 best）
            cb = QComboBox()
            cb.addItems(QUALITY_OPTIONS)
            self.table.setCellWidget(row, 3, cb)

        self._on_status.emit(f"共 {len(items)} 条目，可逐行选择清晰度后下载")

    # -------- 目录选择 --------
    @Slot()
    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "选择下载目录", str(Path.home()), QFileDialog.ShowDirsOnly
        )
        if path:
            self.output_edit.setText(path)

    # -------- 开始下载 --------
    @Slot()
    def _start_download(self) -> None:
        tasks: List[Tuple[str, str]] = []  # (url, quality)

        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).checkState() == Qt.Checked:
                url = self.table.item(r, 1).data(Qt.UserRole)
                cb: QComboBox = self.table.cellWidget(r, 3)  # type: ignore
                quality = cb.currentText() if cb else "best"
                tasks.append((url, quality))

        if not tasks:
            QMessageBox.warning(self, "提示", "请选择至少一项要下载")
            return

        out_dir = Path(self.output_edit.text().strip() or ".").expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        self.download_btn.setEnabled(False)
        self.progress.setValue(0)
        self._on_status.emit("正在准备下载…")

        self._worker = DownloaderWorker(tasks, out_dir)
        self._worker.progress_sig.connect(self._on_progress_from_worker)
        self._worker.status_sig.connect(self._on_status)
        self._worker.finished_sig.connect(self._on_finished)
        self._worker.start()

    # -------- 子线程回调 --------
    @Slot(float)
    def _on_progress_from_worker(self, percent: float) -> None:
        self._on_progress.emit(int(percent * 100))

    @Slot(bool, object)
    def _on_download_finished(self, success: bool, err: str | None) -> None:
        self.download_btn.setEnabled(True)
        if success:
            self._on_status.emit("下载完成 ✅")
        else:
            self._on_status.emit("下载失败 ❌")
            QMessageBox.critical(self, "下载失败", err or "未知错误")
