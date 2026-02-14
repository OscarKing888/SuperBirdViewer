#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperEXIF - 图片 EXIF 信息查看器
支持拖拽图片到窗口，使用 piexif 读取并展示全部 EXIF 数据。
"""

import json
import os
import sys
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QDialog,
        QPushButton,
        QDialogButtonBox,
        QTableWidget,
        QTableWidgetItem,
        QSplitter,
        QFrame,
        QFileDialog,
        QMessageBox,
        QHeaderView,
        QAbstractItemView,
        QScrollArea,
        QGroupBox,
        QGridLayout,
    )
    from PyQt6.QtCore import Qt, QMimeData, QSize
    from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor, QAction
except ImportError:
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QDialog,
        QPushButton,
        QDialogButtonBox,
        QTableWidget,
        QTableWidgetItem,
        QSplitter,
        QFrame,
        QFileDialog,
        QMessageBox,
        QHeaderView,
        QAbstractItemView,
        QScrollArea,
        QGroupBox,
        QGridLayout,
    )
    from PyQt5.QtCore import Qt, QMimeData, QSize
    from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor, QAction

# PyQt5/6 枚举兼容
if hasattr(Qt, "AlignmentFlag"):
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _LeftButton = Qt.MouseButton.LeftButton
    _KeepAspectRatio = Qt.AspectRatioMode.KeepAspectRatio
    _SmoothTransformation = Qt.TransformationMode.SmoothTransformation
else:
    _AlignCenter = Qt.AlignCenter
    _LeftButton = Qt.LeftButton
    _KeepAspectRatio = Qt.KeepAspectRatio
    _SmoothTransformation = Qt.SmoothTransformation
if hasattr(QFrame, "Shape"):
    _FrameBox = QFrame.Shape.Box
    _FrameSunken = QFrame.Shadow.Sunken
else:
    _FrameBox = QFrame.Box
    _FrameSunken = QFrame.Sunken
if hasattr(QHeaderView, "ResizeMode"):
    _ResizeStretch = QHeaderView.ResizeMode.Stretch
else:
    _ResizeStretch = QHeaderView.Stretch
if hasattr(QAbstractItemView, "SelectionBehavior"):
    _SelectRows = QAbstractItemView.SelectionBehavior.SelectRows
elif hasattr(QAbstractItemView, "SelectRows"):
    _SelectRows = QAbstractItemView.SelectRows
else:
    _SelectRows = QAbstractItemView.SelectRows
if hasattr(QAbstractItemView, "EditTrigger"):
    _NoEditTriggers = QAbstractItemView.EditTrigger.NoEditTriggers
    _DoubleClicked = QAbstractItemView.EditTrigger.DoubleClicked
else:
    _NoEditTriggers = QAbstractItemView.NoEditTriggers
    _DoubleClicked = QAbstractItemView.DoubleClicked
try:
    _ItemIsEditable = Qt.ItemFlag.ItemIsEditable
except AttributeError:
    _ItemIsEditable = Qt.ItemIsEditable
try:
    _UserRole = Qt.ItemDataRole.UserRole
except AttributeError:
    _UserRole = Qt.UserRole
# QSplitter 水平方向：PyQt6 为 Qt.Orientation.Horizontal，PyQt5/PySide 为 Qt.Horizontal 或整型 1
_orient = getattr(Qt, "Orientation", None)
_Horizontal = getattr(_orient, "Horizontal", None) if _orient else None
if _Horizontal is None:
    _Horizontal = getattr(Qt, "Horizontal", 1)

import piexif
from PIL import Image
from PIL.ExifTags import TAGS as PIL_TAGS


# 与主程序同目录下的配置文件
CONFIG_FILENAME = "EXIF.cfg"


def _get_config_path() -> str:
    """返回 EXIF.cfg 的完整路径，与当前运行的主程序同目录。"""
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if not app_dir:
        app_dir = os.getcwd()
    return os.path.join(app_dir, CONFIG_FILENAME)

# IFD 分组显示名称
IFD_DISPLAY_NAMES = {
    "0th": "图像 (0th IFD)",
    "Exif": "Exif IFD",
    "GPS": "GPS",
    "1st": "缩略图 (1st IFD)",
    "Interop": "Interop IFD",
    "thumbnail": "缩略图数据",
}

# EXIF 中常见编码，按优先级尝试，避免乱码与跨平台显示问题
_EXIF_ENCODINGS = ("utf-8", "utf-16", "utf-16-be", "latin-1", "cp1252", "gbk", "gb2312", "big5")


def _safe_decode_bytes(data: bytes) -> str:
    """
    将 EXIF 字节按多种编码尝试解码，避免乱码。
    Latin-1 作为最后回退（任意字节可解码），保证不抛错且显示稳定。
    """
    if not data:
        return ""
    # 去除尾部常见填充 \x00
    data = data.rstrip(b"\x00")
    if not data:
        return ""
    for enc in _EXIF_ENCODINGS:
        try:
            s = data.decode(enc)
            # 若解码结果含大量替换符，可能误用编码，继续尝试
            if "\ufffd" in s and enc != "latin-1":
                continue
            return _sanitize_display_string(s)
        except (UnicodeDecodeError, LookupError):
            continue
    return _sanitize_display_string(data.decode("latin-1"))


def _sanitize_display_string(s: str) -> str:
    """
    清理用于界面显示的字符串：去掉控制字符与空字节，避免各系统显示异常或截断。
    """
    if not s:
        return s
    # 替换 NUL 及 C0 控制字符，保留 \t \n \r
    result = []
    for c in s:
        code = ord(c)
        if code == 0:
            result.append(" ")
        elif code < 32 and c not in "\t\n\r":
            result.append(" ")
        else:
            result.append(c)
    return "".join(result).strip()


def _looks_binary(data: bytes) -> bool:
    """若字节序列多为不可打印或高位字节，则视为二进制，不按文本解码。"""
    if len(data) > 2048:
        return True
    printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return printable < len(data) * 0.6


def format_exif_value(value):
    """将 piexif 的原始值格式化为可读字符串，保证跨系统无乱码。"""
    if value is None:
        return ""
    if isinstance(value, bytes):
        # 纯二进制或过长时只显示十六进制
        if len(value) > 512 or _looks_binary(value):
            return value.hex() if len(value) <= 64 else value.hex() + "..."
        return _safe_decode_bytes(value)
    if isinstance(value, tuple):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], int):
            if value[1] != 0:
                return f"{value[0]}/{value[1]} ({value[0] / value[1]:.4f})"
            return f"{value[0]}/{value[1]}"
        return ", ".join(str(format_exif_value(v)) for v in value)
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def get_tag_name(ifd_name: str, tag_id: int) -> str:
    """获取 tag 的可读名称。piexif.TAGS[ifd][tag_id] 为 {'name': '...', 'type': ...}。"""
    if ifd_name == "thumbnail":
        return "（二进制数据）"
    t = piexif.TAGS.get(ifd_name, {})
    info = t.get(tag_id)
    if info is None:
        return f"Tag {tag_id}"
    if isinstance(info, dict):
        return info.get("name", f"Tag {tag_id}")
    return str(info)


def load_exif_piexif(path: str) -> dict | None:
    """使用 piexif 加载 EXIF（JPEG/WebP/TIFF）。"""
    try:
        return piexif.load(path)
    except Exception:
        return None


def load_exif_pillow(path: str) -> list[tuple[str, str, str]]:
    """使用 Pillow 加载 EXIF（作为补充，如 PNG 等）。返回 [(ifd, name, value), ...]。"""
    rows = []
    try:
        img = Image.open(path)
        exif = img.getexif()
        if not exif:
            return rows
        for tag_id, value in exif.items():
            name = PIL_TAGS.get(tag_id, f"Tag {tag_id}")
            if isinstance(value, bytes):
                if tag_id == 37510 and len(value) > 8:  # UserComment，去掉前 8 字节编码标识
                    value = value[8:]
                    if not value.strip(b"\x00"):
                        rows.append(("Pillow Exif", str(name), "（无内容）"))
                        continue
                if len(value) > 512 or _looks_binary(value):
                    value = value.hex() if len(value) <= 64 else value.hex() + "..."
                else:
                    value = _safe_decode_bytes(value)
            else:
                value = _sanitize_display_string(str(value))
            rows.append(("Pillow Exif", str(name), value))
        img.close()
    except Exception:
        pass
    return rows


def _parse_value_back(s: str, raw_value) -> tuple | bytes | int:
    """将用户输入的字符串按原始类型转回 EXIF 可写格式。"""
    if raw_value is None:
        return s.encode("utf-8")
    if isinstance(raw_value, bytes):
        return s.encode("utf-8")
    if isinstance(raw_value, int):
        try:
            return int(s.strip())
        except ValueError:
            return raw_value
    if isinstance(raw_value, tuple):
        if len(raw_value) == 2 and isinstance(raw_value[0], int) and isinstance(raw_value[1], int):
            # 有理数：支持 "a/b" 或 "1.5"
            s = s.strip()
            if "/" in s:
                a, _, b = s.partition("/")
                try:
                    return (int(a.strip()), int(b.strip()) if b.strip() else 1)
                except ValueError:
                    pass
            try:
                f = float(s)
                from fractions import Fraction
                fr = Fraction(f).limit_denominator(10000)
                return (fr.numerator, fr.denominator)
            except ValueError:
                pass
            return raw_value
        if all(isinstance(x, int) for x in raw_value):
            try:
                return tuple(int(x) for x in s.replace(",", " ").split())
            except ValueError:
                return raw_value
    return s.encode("utf-8")


def get_all_exif_tag_keys() -> list[tuple]:
    """
    从 piexif.TAGS 收集所有可配置的 (key, 显示文本)。
    key = "ifd_name:tag_id"，显示文本 = "分组 - 标签名"。
    """
    result = []
    for ifd_name in ("0th", "Exif", "GPS", "1st", "Interop"):
        ifd_data = piexif.TAGS.get(ifd_name, {})
        if not ifd_data:
            continue
        group = IFD_DISPLAY_NAMES.get(ifd_name, ifd_name)
        for tag_id, info in ifd_data.items():
            name = info.get("name", f"Tag {tag_id}") if isinstance(info, dict) else str(info)
            key = f"{ifd_name}:{tag_id}"
            result.append((key, f"{group} - {name}"))
    return result


def load_tag_priority_from_settings() -> list:
    """从与主程序同目录的 EXIF.cfg 读取优先显示的 tag key 列表。"""
    path = _get_config_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get("exif_tag_priority", [])
        return list(val) if isinstance(val, list) else []
    except Exception:
        return []


def save_tag_priority_to_settings(priority_keys: list):
    """将优先显示的 tag key 列表写入与主程序同目录的 EXIF.cfg。"""
    path = _get_config_path()
    try:
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        if not isinstance(data, dict):
            data = {}
        data["exif_tag_priority"] = list(priority_keys)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def apply_tag_priority(rows: list[tuple], priority_keys: list[str]) -> list[tuple]:
    """
    按配置的 tag 顺序重排 rows。priority_keys 中出现的 (ifd_name, tag_id) 按顺序排在前面，其余保持原顺序。
    """
    if not priority_keys:
        return rows
    key_to_index = {k: i for i, k in enumerate(priority_keys)}
    n = len(priority_keys)

    def sort_key(row):
        if len(row) < 2:
            return n
        ifd_name, tag_id = row[0], row[1]
        if ifd_name is None or tag_id is None:
            return n
        key = f"{ifd_name}:{tag_id}"
        return key_to_index.get(key, n)

    return sorted(rows, key=sort_key)


def load_all_exif(path: str) -> list[tuple]:
    """
    加载全部 EXIF，返回 [(ifd_name, tag_id, 分组, 标签名, 值字符串, raw_value), ...]。
    ifd_name/tag_id 为 None 表示不可编辑（Pillow/缩略图等）。
    """
    rows = []
    data = load_exif_piexif(path)
    if data:
        for ifd_name in ("0th", "Exif", "GPS", "1st", "Interop"):
            ifd_data = data.get(ifd_name)
            if not ifd_data or not isinstance(ifd_data, dict):
                continue
            group = IFD_DISPLAY_NAMES.get(ifd_name, ifd_name)
            for tag_id, value in ifd_data.items():
                name = get_tag_name(ifd_name, tag_id)
                raw = value
                # UserComment (Exif 37510) 前 8 字节为字符编码标识，需去掉再按文本解码显示（避免被当作二进制显示为 hex）
                if ifd_name == "Exif" and tag_id == 37510 and isinstance(value, bytes) and len(value) > 8:
                    value = value[8:]
                    if not value.strip(b"\x00"):
                        rows.append((ifd_name, tag_id, group, name, "（无内容）", b""))
                        continue
                    raw = value  # 写回时用 ASCII 前缀 + 新内容
                    value_str = _safe_decode_bytes(value)
                    rows.append((ifd_name, tag_id, group, name, value_str, raw))
                    continue
                rows.append((ifd_name, tag_id, group, name, format_exif_value(value), raw))
        if data.get("thumbnail"):
            rows.append((None, None, IFD_DISPLAY_NAMES["thumbnail"], "（存在）", "是", None))
    if not rows:
        for group, name, value in load_exif_pillow(path):
            rows.append((None, None, group, name, value, None))
    return rows


class DropZone(QLabel):
    """支持拖放的图片放置区。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(_AlignCenter)
        self.setMinimumSize(320, 240)
        self.setFrameStyle(_FrameBox | _FrameSunken)
        self.setStyleSheet(
            "DropZone { background-color: #2d2d2d; border: 2px dashed #555; "
            "border-radius: 8px; color: #888; font-size: 14px; }"
        )
        self.setAcceptDrops(True)
        self._current_path = None
        self._pixmap = None
        self.setText("将图片拖入此处\n或点击选择文件")

    def set_image(self, path: str):
        self._current_path = path
        pix = QPixmap(path)
        if not pix.isNull():
            self._pixmap = pix.scaled(
                self.size().width() - 20,
                self.size().height() - 20,
                _KeepAspectRatio,
                _SmoothTransformation,
            )
            self.setPixmap(self._pixmap)
            self.setText("")
        else:
            self._pixmap = None
            self.setText(f"无法预览\n{Path(path).name}")

    def clear_image(self):
        self._current_path = None
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.setText("将图片拖入此处\n或点击选择文件")

    def current_path(self):
        return self._current_path

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap and self._current_path:
            pix = QPixmap(self._current_path)
            if not pix.isNull():
                self._pixmap = pix.scaled(
                self.size().width() - 20,
                self.size().height() - 20,
                _KeepAspectRatio,
                _SmoothTransformation,
                )
                self.setPixmap(self._pixmap)

    def mousePressEvent(self, event):
        if event.button() == _LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择图片",
                os.path.expanduser("~"),
                "图片 (*.jpg *.jpeg *.png *.webp *.tiff *.tif);;全部 (*.*)",
            )
            if path:
                self.set_image(path)
                if self.parent() and hasattr(self.parent(), "on_image_loaded"):
                    self.parent().on_image_loaded(path)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if path and Path(path).suffix.lower() in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".tiff",
                    ".tif",
                ):
                    event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if path and os.path.isfile(path):
                    self.set_image(path)
                    if self.parent() and hasattr(self.parent(), "on_image_loaded"):
                        self.parent().on_image_loaded(path)
        event.acceptProposedAction()


class ExifTable(QTableWidget):
    """EXIF 信息表格，支持按文本过滤与双击编辑值列。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["分组", "标签", "值"])
        self.horizontalHeader().setSectionResizeMode(2, _ResizeStretch)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(_SelectRows)
        self.setEditTriggers(_DoubleClicked)
        self.setStyleSheet(
            "QTableWidget { font-family: 'SF Mono', 'Monaco', 'Consolas', monospace; font-size: 12px; }"
        )
        self._all_rows: list[tuple] = []
        self._filtered_rows: list[tuple] = []
        self._filter_text = ""
        self._updating = False
        self._save_callback = None
        self.itemChanged.connect(self._on_item_changed)

    def set_save_callback(self, cb):
        self._save_callback = cb

    def set_exif(self, rows: list[tuple]):
        self._all_rows = list(rows)
        self._apply_filter(self._filter_text)

    def set_filter_text(self, text):
        self._filter_text = str(text or "").strip()
        self._apply_filter(self._filter_text)

    def _apply_filter(self, text: str):
        self._filter_text = text
        if not text:
            self._filtered_rows = list(self._all_rows)
        else:
            key = text.lower()
            # 6-tuple: (ifd_name, tag_id, group, name, value_str, raw_value)，过滤用 group/name/value_str 即索引 2,3,4
            self._filtered_rows = [
                r for r in self._all_rows
                if key in (r[2] or "").lower() or key in (r[3] or "").lower() or key in (r[4] or "").lower()
            ]
        rows = self._filtered_rows
        self._updating = True
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            ifd_name, tag_id, group, name, value_str, raw_value = row[:6]
            it0 = QTableWidgetItem(group)
            it0.setFlags(it0.flags() & ~_ItemIsEditable)
            self.setItem(i, 0, it0)
            it1 = QTableWidgetItem(name)
            it1.setFlags(it1.flags() & ~_ItemIsEditable)
            self.setItem(i, 1, it1)
            it2 = QTableWidgetItem(value_str)
            if ifd_name is not None and tag_id is not None:
                it2.setFlags(it2.flags() | _ItemIsEditable)
            else:
                it2.setFlags(it2.flags() & ~_ItemIsEditable)
            self.setItem(i, 2, it2)
        self.resizeRowsToContents()
        self._updating = False

    def _on_item_changed(self, item):
        if self._updating or not self._save_callback or item.column() != 2:
            return
        row = item.row()
        if row < 0 or row >= len(self._filtered_rows):
            return
        row_data = self._filtered_rows[row]
        ifd_name, tag_id, group, name, old_val, raw_value = row_data[:6]
        if ifd_name is None or tag_id is None:
            return
        new_val = item.text().strip()
        if new_val == old_val:
            return
        self._save_callback(ifd_name, tag_id, new_val, raw_value)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_act = QAction("复制", self)
        copy_act.triggered.connect(self._copy_selection)
        menu.addAction(copy_act)
        menu.exec(event.globalPos())

    def _copy_selection(self):
        """将选中单元格文本复制到剪贴板。"""
        sel = self.selectedRanges()
        if not sel:
            item = self.currentItem()
            if item is not None:
                QApplication.clipboard().setText(item.text())
            return
        parts = []
        for r in sel:
            for row in range(r.topRow(), r.bottomRow() + 1):
                cells = []
                for col in range(r.leftColumn(), r.rightColumn() + 1):
                    it = self.item(row, col)
                    cells.append(it.text() if it is not None else "")
                parts.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(parts))


class ExifTagOrderDialog(QDialog):
    """配置 EXIF 标签优先显示顺序的对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EXIF 显示顺序")
        self.setMinimumSize(420, 380)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("以下标签将优先显示在 EXIF 列表顶部，按顺序排列："))
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_up = QPushButton("上移")
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down = QPushButton("下移")
        self.btn_down.clicked.connect(self._move_down)
        self.btn_remove = QPushButton("删除")
        self.btn_remove.clicked.connect(self._remove)
        self.btn_add = QPushButton("添加…")
        self.btn_add.clicked.connect(self._add_tag)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            if hasattr(QDialogButtonBox.StandardButton, "Ok")
            else QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)
        self._priority_keys = []
        self._all_tags = get_all_exif_tag_keys()
        self._load_from_settings()

    def _load_from_settings(self):
        self._priority_keys = load_tag_priority_from_settings()
        self._refresh_list()

    def _refresh_list(self):
        key_to_text = {k: t for k, t in self._all_tags}
        self.list_widget.clear()
        for key in self._priority_keys:
            text = key_to_text.get(key, key)
            item = QListWidgetItem(text)
            item.setData(_UserRole, key)
            self.list_widget.addItem(item)

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row <= 0:
            return
        keys = self._priority_keys
        keys[row], keys[row - 1] = keys[row - 1], keys[row]
        self._priority_keys = keys
        self._refresh_list()
        self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._priority_keys) - 1:
            return
        keys = self._priority_keys
        keys[row], keys[row + 1] = keys[row + 1], keys[row]
        self._priority_keys = keys
        self._refresh_list()
        self.list_widget.setCurrentRow(row + 1)

    def _remove(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self._priority_keys.pop(row)
        self._refresh_list()
        if self.list_widget.count():
            self.list_widget.setCurrentRow(min(row, self.list_widget.count() - 1))

    def _add_tag(self):
        d = QDialog(self)
        d.setWindowTitle("选择要优先显示的标签")
        d.setMinimumSize(400, 350)
        layout = QVBoxLayout(d)
        layout.addWidget(QLabel("搜索："))
        search = QLineEdit()
        search.setPlaceholderText("输入分组或标签名过滤…")
        layout.addWidget(search)
        all_list = QListWidget()
        existing = set(self._priority_keys)
        for key, text in self._all_tags:
            if key in existing:
                continue
            item = QListWidgetItem(text)
            item.setData(_UserRole, key)
            all_list.addItem(item)
        layout.addWidget(all_list)

        def _filter_list(text):
            t = str(text or "").strip().lower()
            for i in range(all_list.count()):
                it = all_list.item(i)
                it.setHidden(bool(t) and t not in it.text().lower())

        search.textChanged.connect(_filter_list)
        chosen_key = [None]

        def on_accept():
            cur = all_list.currentItem()
            if cur is not None:
                chosen_key[0] = cur.data(_UserRole)
            d.accept()

        all_list.doubleClicked.connect(on_accept)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            if hasattr(QDialogButtonBox.StandardButton, "Ok")
            else QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        bbox.accepted.connect(on_accept)
        bbox.rejected.connect(d.reject)
        layout.addWidget(bbox)
        if d.exec():
            key = chosen_key[0]
            if key and key not in self._priority_keys:
                self._priority_keys.append(key)
                self._refresh_list()

    def get_priority_keys(self):
        return list(self._priority_keys)

    def accept(self):
        save_tag_priority_to_settings(self._priority_keys)
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SuperEXIF - 图片 EXIF 查看器")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 并排：左侧图片，右侧 EXIF
        splitter = QSplitter(_Horizontal)

        # 左侧：文件名 + 拖放区
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.file_label = QLabel("未选择图片")
        self.file_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.file_label.setWordWrap(True)
        left_layout.addWidget(self.file_label)
        self.drop_zone = DropZone(central)
        left_layout.addWidget(self.drop_zone, stretch=1)
        splitter.addWidget(left_widget)

        # 右侧：过滤框 + EXIF 表格
        group = QGroupBox("EXIF 信息")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")
        group_layout = QVBoxLayout(group)
        top_row = QHBoxLayout()
        self.exif_filter = QLineEdit()
        self.exif_filter.setPlaceholderText("按分组、标签或值过滤…")
        self.exif_filter.setClearButtonEnabled(True)
        self.exif_filter.setStyleSheet("QLineEdit { padding: 6px; font-size: 13px; }")
        self.exif_filter.textChanged.connect(self._on_exif_filter_changed)
        top_row.addWidget(self.exif_filter)
        self.btn_config_order = QPushButton("配置顺序")
        self.btn_config_order.setToolTip("设置优先显示的 EXIF 标签及顺序")
        self.btn_config_order.clicked.connect(self._open_tag_order_config)
        top_row.addWidget(self.btn_config_order)
        group_layout.addLayout(top_row)
        self.exif_table = ExifTable(self)
        self.exif_table.set_save_callback(self._save_exif_value)
        group_layout.addWidget(self.exif_table)
        splitter.addWidget(group)

        splitter.setSizes([400, 500])  # 左侧 400px，右侧 500px
        layout.addWidget(splitter)

        self._current_exif_path = None

        # drop_zone 加入 left_layout 后 parent 为 left_widget，回调需挂在 left_widget 上
        left_widget.on_image_loaded = self.on_image_loaded

    def _on_exif_filter_changed(self, text: str):
        self.exif_table.set_filter_text(text)

    def _open_tag_order_config(self):
        d = ExifTagOrderDialog(self)
        if d.exec():
            if self._current_exif_path and os.path.isfile(self._current_exif_path):
                rows = load_all_exif(self._current_exif_path)
                rows = apply_tag_priority(rows, load_tag_priority_from_settings())
                self.exif_table.set_exif(rows)

    def _save_exif_value(self, ifd_name: str, tag_id: int, new_val: str, raw_value):
        """将编辑后的 EXIF 值写回文件。"""
        path = self._current_exif_path
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "无法保存", "未选择图片或文件不存在。")
            return
        try:
            if tag_id == 37510:
                # UserComment：前 8 字节为 ASCII 编码标识
                new_raw = b"ASCII\x00\x00\x00" + new_val.encode("utf-8")
            else:
                new_raw = _parse_value_back(new_val, raw_value)
            data = piexif.load(path)
            if ifd_name not in data or not isinstance(data[ifd_name], dict):
                data[ifd_name] = {}
            data[ifd_name][tag_id] = new_raw
            exif_bytes = piexif.dump(data)
            piexif.insert(exif_bytes, path)
            rows = load_all_exif(path)
            self.exif_table.set_exif(rows)
            QMessageBox.information(self, "已保存", "EXIF 已写入文件。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def on_image_loaded(self, path: str):
        """图片被拖入或选择后调用。"""
        self._current_exif_path = path
        self.file_label.setText(path)
        self.file_label.setToolTip(path)
        rows = load_all_exif(path)
        if not rows:
            QMessageBox.information(
                self,
                "无 EXIF",
                "该图片未包含 EXIF 信息或格式暂不支持。\n支持格式：JPEG、WebP、TIFF（piexif）；其他格式会尝试用 Pillow 读取。",
            )
        else:
            rows = apply_tag_priority(rows, load_tag_priority_from_settings())
        self.exif_table.set_exif(rows)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    app.setPalette(palette)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
