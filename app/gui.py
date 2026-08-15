from __future__ import annotations

import logging
import shutil
from pathlib import Path

try:
    import qtawesome as qta
except Exception:  # pragma: no cover
    qta = None

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .downloader import DownloadTask, DownloaderWorker
from .formats import FormatsFetcher, VideoItem, _duration_text

log = logging.getLogger(__name__)


def _icon(name: str) -> QIcon:
    if qta is None:
        return QIcon()
    return qta.icon(name, color="#f3f4f6")


class MainWindow(QWidget):
    _on_progress = Signal(float)
    _on_status = Signal(str)
    _on_finished = Signal(bool, object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Videos Downloader")
        self.resize(980, 660)

        self._worker: DownloaderWorker | None = None
        self._fetcher: FormatsFetcher | None = None

        self._setup_ui()
        self._connect_signals()
        self._set_busy(False)

    def _setup_ui(self) -> None:
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("粘贴视频或播放列表链接")
        self.url_edit.setClearButtonEnabled(True)

        self.parse_btn = QPushButton("解析链接")
        self.parse_btn.setIcon(_icon("fa5s.search"))

        self.output_edit = QLineEdit(str(Path.home() / "Downloads"))
        self.output_edit.setPlaceholderText("选择保存目录")

        self.choose_btn = QPushButton()
        self.choose_btn.setIcon(_icon("fa5s.folder-open"))
        self.choose_btn.setToolTip("选择保存目录")

        self.cookies_combo = QComboBox()
        self.cookies_combo.addItem("不使用 cookies", None)
        self.cookies_combo.addItem("从 Chrome 读取", "chrome")
        self.cookies_combo.addItem("从 Edge 读取", "edge")
        self.cookies_combo.addItem("从 Firefox 读取", "firefox")
        self.cookies_combo.setToolTip("用于需要登录态的网站，例如 B 站高清、合集或风控场景")

        self.select_all = QCheckBox("全选")
        self.select_all.setChecked(True)

        self.download_btn = QPushButton("开始下载")
        self.download_btn.setIcon(_icon("fa5s.download"))
        self.download_btn.setEnabled(False)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["选择", "标题", "时长", "清晰度"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.status_label = QLabel("等待解析链接")
        self.status_label.setWordWrap(True)

        form = QGridLayout()
        form.setColumnStretch(1, 1)
        form.addWidget(QLabel("链接"), 0, 0)
        form.addWidget(self.url_edit, 0, 1)
        form.addWidget(self.parse_btn, 0, 2)
        form.addWidget(QLabel("保存到"), 1, 0)
        form.addWidget(self.output_edit, 1, 1)
        form.addWidget(self.choose_btn, 1, 2)
        form.addWidget(QLabel("登录态"), 2, 0)
        form.addWidget(self.cookies_combo, 2, 1)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.select_all)
        toolbar.addStretch()
        toolbar.addWidget(self.download_btn)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addLayout(form)
        root.addLayout(toolbar)
        root.addWidget(self.table, 1)
        root.addWidget(self.progress)
        root.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.parse_btn.clicked.connect(self._fetch_entries)
        self.url_edit.returnPressed.connect(self._fetch_entries)
        self.choose_btn.clicked.connect(self._choose_dir)
        self.download_btn.clicked.connect(self._start_download)
        self.select_all.stateChanged.connect(self._toggle_all_rows)

        self._on_progress.connect(self._set_progress)
        self._on_status.connect(self.status_label.setText)
        self._on_finished.connect(self._on_download_finished)

    def _set_busy(self, busy: bool) -> None:
        self.url_edit.setEnabled(not busy)
        self.parse_btn.setEnabled(not busy)
        self.output_edit.setEnabled(not busy)
        self.choose_btn.setEnabled(not busy)
        self.cookies_combo.setEnabled(not busy)
        self.download_btn.setEnabled(not busy and self.table.rowCount() > 0)
        self.select_all.setEnabled(not busy and self.table.rowCount() > 0)
        self.table.setEnabled(not busy)

    @Slot()
    def _fetch_entries(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "缺少链接", "请先粘贴视频或播放列表链接。")
            return

        if self._fetcher and self._fetcher.isRunning():
            return

        self.table.setRowCount(0)
        self.progress.setValue(0)
        self._on_status.emit("正在解析链接...")
        self._set_busy(True)

        self._fetcher = FormatsFetcher(url, self._selected_cookies_browser())
        self._fetcher.status_sig.connect(self._on_status)
        self._fetcher.result_sig.connect(self._populate_table)
        self._fetcher.error_sig.connect(self._on_fetch_error)
        self._fetcher.finished.connect(lambda: self._set_busy(False))
        self._fetcher.start()

    @Slot(list)
    def _populate_table(self, items: list[VideoItem]) -> None:
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Checked if self.select_all.isChecked() else Qt.Unchecked)
            self.table.setItem(row, 0, checkbox)

            title = QTableWidgetItem(item["title"])
            title.setData(Qt.UserRole, item["url"])
            self.table.setItem(row, 1, title)

            duration = QTableWidgetItem(_duration_text(item["duration"]))
            duration.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, duration)

            formats = QComboBox()
            for fmt in item["formats"]:
                formats.addItem(fmt["label"], fmt["download_expr"])
            formats.setMinimumWidth(230)
            self.table.setCellWidget(row, 3, formats)

        self.download_btn.setEnabled(bool(items))
        self.select_all.setEnabled(bool(items))
        self._on_status.emit(f"已解析 {len(items)} 个条目，可选择清晰度后下载。")

    @Slot(str)
    def _on_fetch_error(self, message: str) -> None:
        self._on_status.emit("解析失败")
        QMessageBox.critical(self, "解析失败", message or "无法解析该链接。")

    @Slot()
    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self.output_edit.text().strip() or str(Path.home()),
            QFileDialog.ShowDirsOnly,
        )
        if path:
            self.output_edit.setText(path)

    @Slot(int)
    def _toggle_all_rows(self, state: int) -> None:
        check_state = Qt.Checked if state == Qt.CheckState.Checked.value else Qt.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(check_state)

    @Slot()
    def _start_download(self) -> None:
        tasks = self._selected_tasks()
        if not tasks:
            QMessageBox.warning(self, "未选择条目", "请至少勾选一个要下载的视频。")
            return

        if self._needs_ffmpeg(tasks) and not shutil.which("ffmpeg"):
            QMessageBox.critical(
                self,
                "缺少 ffmpeg",
                "当前选择可能需要合并音视频或转换为 MP4，但系统未找到 ffmpeg。\n\n"
                "请先安装 ffmpeg，并确保 ffmpeg 命令可以在终端中直接运行。",
            )
            return

        out_dir = Path(self.output_edit.text().strip() or ".").expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        self.progress.setValue(0)
        self._on_status.emit("正在准备下载...")
        self._set_busy(True)

        self._worker = DownloaderWorker(tasks, out_dir, self._selected_cookies_browser())
        self._worker.progress_sig.connect(self._on_progress)
        self._worker.status_sig.connect(self._on_status)
        self._worker.finished_sig.connect(self._on_finished)
        self._worker.start()

    def _selected_cookies_browser(self) -> str | None:
        browser = self.cookies_combo.currentData()
        return str(browser) if browser else None

    def _selected_tasks(self) -> list[DownloadTask]:
        tasks: list[DownloadTask] = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            title_item = self.table.item(row, 1)
            combo = self.table.cellWidget(row, 3)
            if (
                checkbox is None
                or title_item is None
                or checkbox.checkState() != Qt.Checked
                or not isinstance(combo, QComboBox)
            ):
                continue

            tasks.append(
                {
                    "title": title_item.text(),
                    "url": str(title_item.data(Qt.UserRole)),
                    "format_expr": str(combo.currentData() or "bestvideo+bestaudio/best"),
                    "format_label": combo.currentText(),
                }
            )
        return tasks

    def _needs_ffmpeg(self, tasks: list[DownloadTask]) -> bool:
        return any("+" in task["format_expr"] for task in tasks)

    @Slot(float)
    def _set_progress(self, value: float) -> None:
        self.progress.setValue(int(max(0.0, min(value, 1.0)) * 100))

    @Slot(bool, object)
    def _on_download_finished(self, success: bool, err: str | None) -> None:
        self._set_busy(False)
        if success:
            self._on_status.emit("下载完成")
            return

        self._on_status.emit("下载失败")
        QMessageBox.critical(self, "下载失败", err or "未知错误")
