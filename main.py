#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperEXIF - 图片 EXIF 信息查看器
支持拖拽图片到窗口，使用 piexif 读取并展示全部 EXIF 数据。
"""

import json
import os
import sys
import shutil
import re
import subprocess
import tempfile
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
        QCheckBox,
        QTabWidget,
    )
    from PyQt6.QtCore import Qt, QMimeData, QSize
    from PyQt6.QtGui import QPixmap, QImage, QTransform, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor, QAction, QIcon
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
        QCheckBox,
        QTabWidget,
    )
    from PyQt5.QtCore import Qt, QMimeData, QSize
    from PyQt5.QtGui import QPixmap, QImage, QTransform, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor, QAction, QIcon

from app_common import show_about_dialog, load_about_info, AppInfoBar
from app_common.exif_io import (
    get_exiftool_executable_path,
    run_exiftool_json,
    write_exif_with_exiftool,
    write_exif_with_exiftool_by_key,
    write_meta_with_exiftool,
    write_meta_with_piexif,
    _get_exiftool_tag_target,
)

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
if hasattr(QMessageBox, "Icon"):
    _MsgInfo = QMessageBox.Icon.Information
else:
    _MsgInfo = QMessageBox.Information
if hasattr(QMessageBox, "StandardButton"):
    _MsgOk = QMessageBox.StandardButton.Ok
else:
    _MsgOk = QMessageBox.Ok

import piexif
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS as PIL_TAGS

# 可选：用于 RAW 的 EXIF 回退读取
try:
    import exifread
except ImportError:
    exifread = None

# 可选：用于从 RAW 提取嵌入缩略图
try:
    import rawpy
except ImportError:
    rawpy = None

# 可选：HEIC/HEIF 读取与预览（Pillow 需注册后才能 Image.open(heic)）
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None

# 支持的图片扩展名（含各家相机 RAW 与 HEIC/HEIF）
IMAGE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif",
    ".heic", ".heif", ".hif",
    # Canon
    ".cr2", ".cr3", ".crw",
    # Nikon
    ".nef", ".nrw",
    # Sony
    ".arw", ".srf", ".sr2",
    # Panasonic
    ".rw2", ".raw",
    # Olympus
    ".orf", ".ori",
    # Fujifilm
    ".raf",
    # Adobe / Leica 等
    ".dng",
    # Pentax
    ".pef", ".ptx",
    # Sigma
    ".x3f",
    # Leica
    ".rwl",
    # 其他常见 RAW
    ".3fr", ".dcr", ".kdc", ".mef", ".mrw", ".rwz",
)
# 去重并保持顺序
IMAGE_EXTENSIONS = tuple(dict.fromkeys(e.lower() for e in IMAGE_EXTENSIONS))
RAW_EXTENSIONS = frozenset(
    e for e in IMAGE_EXTENSIONS
    if e not in (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".heic", ".heif", ".hif")
)
HEIF_EXTENSIONS = frozenset({".heic", ".heif", ".hif"})
PIEXIF_WRITABLE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".jpe", ".webp", ".tif", ".tiff"})
EXIFTOOL_IFD_GROUP_MAP = {
    "0th": "IFD0",
    "Exif": "EXIF",
    "GPS": "GPS",
    "1st": "IFD1",
    "Interop": "InteropIFD",
}


# 与主程序同目录下的配置文件
CONFIG_FILENAME = "EXIF.cfg"
META_IFD_NAME = "Meta"
META_TITLE_TAG_ID = "Title"
META_TITLE_PRIORITY_KEY = f"{META_IFD_NAME}:{META_TITLE_TAG_ID}"
META_DESCRIPTION_TAG_ID = "Description"
META_DESCRIPTION_PRIORITY_KEY = f"{META_IFD_NAME}:{META_DESCRIPTION_TAG_ID}"
CALC_IFD_NAME = "Calc"
HYPERFOCAL_TAG_ID = "HyperfocalDistance"
HYPERFOCAL_PRIORITY_KEY = f"{CALC_IFD_NAME}:{HYPERFOCAL_TAG_ID}"
# exiftool 中与“标题/描述”语义重复的 key，已在列表前部用 Meta:Title / Meta:Description 显示，不再在后面重复
EXIFTOOL_KEYS_DUPLICATE_OF_TITLE = frozenset({"XMP-dc:Title", "IFD0:XPTitle", "IFD0:DocumentName"})
EXIFTOOL_KEYS_DUPLICATE_OF_DESCRIPTION = frozenset(
    {
        "XMP-dc:Description",
        "IFD0:XPComment",
        "IFD0:ImageDescription",
        "EXIF:UserComment",
        "ExifIFD:UserComment",
    }
)
APP_ICON_CANDIDATES = (
    os.path.join("image", "superexif.png"),
    os.path.join("image", "superexif.ico"),
    os.path.join("image", "superexif.icns"),
)
def _get_app_dir() -> str:
    """返回当前程序目录（脚本目录或打包后可执行文件目录）。"""
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if not app_dir:
        app_dir = os.getcwd()
    return app_dir


def _get_resource_path(relative_path: str) -> str | None:
    """按运行环境查找资源文件路径。"""
    candidates = [os.path.join(_get_app_dir(), relative_path)]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, relative_path))
        if sys.platform == "darwin":
            # macOS .app 中资源通常位于 Contents/Resources
            candidates.append(
                os.path.abspath(os.path.join(_get_app_dir(), "..", "Resources", relative_path))
            )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _get_app_icon_path() -> str | None:
    """返回应用图标路径。"""
    for rel in APP_ICON_CANDIDATES:
        p = _get_resource_path(rel)
        if p:
            return p
    return None


def _get_config_path() -> str:
    """返回 EXIF.cfg 的完整路径，与当前运行的主程序同目录。"""
    app_dir = _get_app_dir()
    return os.path.join(app_dir, CONFIG_FILENAME)


def _load_settings() -> dict:
    """读取 EXIF.cfg，失败返回空字典。"""
    candidates = [_get_config_path()]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, CONFIG_FILENAME))
        if sys.platform == "darwin":
            candidates.append(os.path.abspath(os.path.join(_get_app_dir(), "..", "Resources", CONFIG_FILENAME)))
    seen = set()
    for path in candidates:
        norm = os.path.normpath(path)
        if norm in seen or not os.path.isfile(path):
            continue
        seen.add(norm)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _save_settings(data: dict):
    """写入 EXIF.cfg（UTF-8）。"""
    path = _get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# IFD 分组显示名称
IFD_DISPLAY_NAMES = {
    META_IFD_NAME: "文件信息",
    "0th": "图像 (0th IFD)",
    "Exif": "Exif IFD",
    "GPS": "GPS",
    "1st": "缩略图 (1st IFD)",
    "Interop": "Interop IFD",
    CALC_IFD_NAME: "计算信息",
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


def _decoded_looks_text(s: str) -> bool:
    """
    解码后的字符串是否像可读文本（用于决定显示为文本还是十六进制）。
    若大量替换符或大量控制字符则视为二进制/乱码，应显示为 hex。
    """
    if not s or len(s) < 2:
        return True
    n = len(s)
    replacement = s.count("\ufffd")
    if replacement > n * 0.15:  # 超过 15% 为替换符，可能解码错误
        return False
    # 可接受字符：可打印、空格、\t\n\r、以及常见 CJK 等
    ok = 0
    for c in s:
        code = ord(c)
        if code == 0 or (code < 32 and c not in "\t\n\r"):
            continue  # 控制字符不计入 ok
        if code < 127 or (code >= 0x4E00 and code <= 0x9FFF) or (code >= 0x3000 and code <= 0x303F):
            ok += 1
        else:
            ok += 1  # 其他 Unicode（如拉丁扩展、符号）也视为可读
    return ok >= n * 0.5  # 至少一半像可读字符


def _tuple_as_bytes(value: tuple) -> bytes | None:
    """若 tuple 全为 0–255 的整数则视为字节序列，返回 bytes；否则返回 None。"""
    if not value:
        return None
    try:
        if all(isinstance(x, int) and 0 <= x <= 255 for x in value):
            return bytes(value)
    except (TypeError, ValueError):
        pass
    return None


def _format_hex_bytes(data: bytes) -> str:
    """将二进制数据格式化为十六进制字符串（过长时截断）。"""
    if len(data) <= 64:
        return data.hex()
    return data[:64].hex() + "..."


def get_tag_type(ifd_name: str, tag_id: int) -> int | None:
    """读取 piexif 标签定义类型（piexif.TYPES.*），失败返回 None。"""
    info = piexif.TAGS.get(ifd_name, {}).get(tag_id)
    if isinstance(info, dict):
        t = info.get("type")
        if isinstance(t, int):
            return t
    return None


def format_exif_value(value, expected_type: int | None = None):
    """
    将 piexif 原始值格式化为可读字符串。
    规则：
    1) 仅当标签定义类型为 ASCII 时，按文本解码显示；
    2) 对于非文本定义的二进制值（bytes / byte tuple），统一显示 hex；
    3) 数值型（Rational/整数等）保持数值可读显示。
    """
    text_type = getattr(piexif.TYPES, "Ascii", 2)
    rational_types = {getattr(piexif.TYPES, "Rational", 5), getattr(piexif.TYPES, "SRational", 10)}

    if value is None:
        return ""
    if isinstance(value, bytes):
        if expected_type == text_type:
            s = _safe_decode_bytes(value)
            if len(s) > 2048:
                return s[:2048] + "\n... (已截断)"
            return s
        return _format_hex_bytes(value)
    if isinstance(value, tuple):
        if (
            expected_type in rational_types
            and len(value) == 2
            and isinstance(value[0], int)
            and isinstance(value[1], int)
        ):
            if value[1] != 0:
                return f"{value[0]}/{value[1]} ({value[0] / value[1]:.4f})"
            return f"{value[0]}/{value[1]}"
        data = _tuple_as_bytes(value)
        if data is not None:
            if expected_type == text_type:
                s = _safe_decode_bytes(data)
                if len(s) > 2048:
                    return s[:2048] + "\n... (已截断)"
                return s
            return _format_hex_bytes(data)
        # 非字节数组的 tuple（如 SHORT/LONG/RATIONAL 数组）保持数值可读
        return ", ".join(str(format_exif_value(v)) for v in value)
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _to_float_exif_number(v) -> float | None:
    """将 EXIF 数值（含有理数）转为浮点，失败返回 None。"""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], int) and isinstance(v[1], int):
        if v[1] == 0:
            return None
        return float(v[0]) / float(v[1])
    return None


def _to_float_text_number(v) -> float | None:
    """Parse exiftool values like '1/800', '400 mm', 5.6 into float."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list):
        for x in v:
            f = _to_float_text_number(x)
            if f is not None:
                return f
        return None
    s = _sanitize_display_string(str(v or "")).strip()
    if not s:
        return None
    if "/" in s:
        a, _, b = s.partition("/")
        try:
            num = float(a.strip())
            den = float(b.strip().split()[0]) if b.strip() else 0.0
            if den != 0:
                return num / den
        except (TypeError, ValueError):
            pass
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _calc_hyperfocal_distance_from_exiftool_obj(obj: dict, default_coc_mm: float = 0.03) -> float | None:
    """Calculate hyperfocal distance from exiftool json object."""
    if not isinstance(obj, dict):
        return None

    def _pick(*keys):
        for k in keys:
            if k in obj:
                f = _to_float_text_number(obj.get(k))
                if f is not None:
                    return f
        return None

    f_mm = _pick("ExifIFD:FocalLength", "EXIF:FocalLength", "Composite:FocalLength")
    n = _pick("ExifIFD:FNumber", "EXIF:FNumber", "Composite:Aperture")
    if f_mm is None or n is None or f_mm <= 0 or n <= 0:
        return None

    coc_mm = default_coc_mm if default_coc_mm > 0 else 0.03
    focal_35 = _pick("ExifIFD:FocalLengthIn35mmFormat", "EXIF:FocalLengthIn35mmFormat")
    if focal_35 is not None and focal_35 > 0:
        crop = focal_35 / f_mm
        if crop > 0:
            coc_mm = 0.03 / crop
    if coc_mm <= 0:
        coc_mm = 0.03

    h_mm = (f_mm * f_mm) / (n * coc_mm) + f_mm
    if h_mm <= 0:
        return None
    return h_mm / 1000.0


def _calc_hyperfocal_distance_m(exif_data: dict, default_coc_mm: float = 0.03) -> float | None:
    """
    计算超焦距（米）。
    公式：H = f^2 / (N * c) + f
    其中 f=焦距(mm), N=光圈值, c=弥散圆(mm)。
    """
    exif_ifd = exif_data.get("Exif") if isinstance(exif_data, dict) else None
    if not isinstance(exif_ifd, dict):
        return None
    f_mm = _to_float_exif_number(exif_ifd.get(37386))   # FocalLength
    n = _to_float_exif_number(exif_ifd.get(33437))      # FNumber
    if f_mm is None or n is None or f_mm <= 0 or n <= 0:
        return None

    coc_mm = default_coc_mm if default_coc_mm > 0 else 0.03
    focal_35 = _to_float_exif_number(exif_ifd.get(41989))  # FocalLengthIn35mmFilm
    if focal_35 is not None and focal_35 > 0:
        crop = focal_35 / f_mm
        if crop > 0:
            coc_mm = 0.03 / crop
    if coc_mm <= 0:
        coc_mm = 0.03

    h_mm = (f_mm * f_mm) / (n * coc_mm) + f_mm
    if h_mm <= 0:
        return None
    return h_mm / 1000.0


def _format_hyperfocal_distance(value_m: float | None) -> str:
    """格式化超焦距显示文本。"""
    if value_m is None:
        return "无法计算"
    return f"{value_m:.2f} m"


def _extract_exiftool_text_value(value) -> str:
    """Normalize exiftool json value to display text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for k in ("x-default", "zh-CN", "zh-cn", "en-US", "en-us"):
            if k in value:
                s = _extract_exiftool_text_value(value.get(k))
                if s:
                    return s
        for v in value.values():
            s = _extract_exiftool_text_value(v)
            if s:
                return s
        return ""
    if isinstance(value, list):
        parts = [_extract_exiftool_text_value(v) for v in value]
        parts = [p for p in parts if p]
        return " ".join(parts)
    return _sanitize_display_string(str(value))


def _is_likely_mojibake_meta_text(s: str) -> bool:
    """
    Detect common mojibake pattern like '??ͷѻȸ' (GBK bytes decoded as UTF-8).
    Keep heuristic conservative: only flag when placeholder + suspicious script mix appears.
    """
    txt = _sanitize_display_string(str(s or "")).strip()
    if not txt:
        return False
    has_cjk = any(0x4E00 <= ord(ch) <= 0x9FFF for ch in txt)
    if has_cjk:
        return False
    has_placeholder = ("?" in txt) or ("\ufffd" in txt)
    has_suspicious_script = any(
        (0x0370 <= ord(ch) <= 0x052F) or (0x0180 <= ord(ch) <= 0x024F)
        for ch in txt
    )
    return has_placeholder and has_suspicious_script


def _pick_preferred_meta_text(*candidates) -> str:
    """
    Pick first non-empty candidate; if earlier candidate looks mojibake, fallback to next healthy one.
    """
    cleaned = []
    for c in candidates:
        s = _extract_exiftool_text_value(c)
        if s:
            cleaned.append(s)
    if not cleaned:
        return ""
    for s in cleaned:
        if not _is_likely_mojibake_meta_text(s):
            return s
    return cleaned[0]


def _load_macos_mdls_text(path: str, attr_name: str) -> str | None:
    """读取 macOS Spotlight 元数据字段（kMDItem*）。"""
    if sys.platform != "darwin":
        return None
    try:
        cp = subprocess.run(
            ["mdls", "-name", attr_name, "-raw", path],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    s = _sanitize_display_string(cp.stdout.strip())
    if not s or s in ("(null)", "null"):
        return None
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = _sanitize_display_string(s[1:-1])
    return s or None


def _decode_xp_text_value(value) -> str | None:
    """解码 XP* 文本字段（常见为 UTF-16LE）。"""
    data = None
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, tuple):
        data = _tuple_as_bytes(value)
    if not data:
        return None
    # XP* 通常为 UTF-16LE，以 0x0000 结尾。不能直接 rstrip，否则可能丢掉最后一个字符。
    while len(data) >= 2 and data[-2:] == b"\x00\x00":
        data = data[:-2]
    if len(data) % 2 == 1:
        data = data[:-1]
    if not data:
        return None
    try:
        s = data.decode("utf-16-le", errors="ignore")
    except Exception:
        s = _safe_decode_bytes(data)
    s = _sanitize_display_string(s)
    return s or None


def _decode_xp_title_value(value) -> str | None:
    """解码 XPTitle（0th:40091）。"""
    return _decode_xp_text_value(value)


def _decode_xp_comment_value(value) -> str | None:
    """解码 XPComment（0th:40092）。"""
    return _decode_xp_text_value(value)


def _extract_ifd_text_value(ifd_data: dict, tag_id: int) -> str | None:
    """从指定 IFD 标签中提取文本。"""
    if not isinstance(ifd_data, dict):
        return None
    v = ifd_data.get(tag_id)
    if isinstance(v, bytes):
        s = _safe_decode_bytes(v)
    elif isinstance(v, tuple):
        b = _tuple_as_bytes(v)
        s = _safe_decode_bytes(b) if b is not None else None
    else:
        s = _sanitize_display_string(str(v)) if v is not None else None
    return s or None


def _decode_user_comment_value(value) -> str | None:
    """解码 UserComment（Exif:37510）。"""
    data = None
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, tuple):
        data = _tuple_as_bytes(value)
    if not data:
        return None
    if len(data) >= 8:
        prefix = data[:8]
        payload = data[8:]
        if prefix.startswith(b"ASCII"):
            s = _safe_decode_bytes(payload)
            return s or None
        if prefix.startswith(b"UNICODE"):
            for enc in ("utf-16-be", "utf-16-le", "utf-8"):
                try:
                    s = _sanitize_display_string(payload.decode(enc, errors="ignore"))
                    if s:
                        return s
                except Exception:
                    continue
        if prefix.startswith(b"JIS"):
            for enc in ("shift_jis", "cp932", "utf-8"):
                try:
                    s = _sanitize_display_string(payload.decode(enc, errors="ignore"))
                    if s:
                        return s
                except Exception:
                    continue
    s = _safe_decode_bytes(data)
    return s or None


def _extract_title_from_exif_data(exif_data: dict | None) -> str | None:
    """从 EXIF 数据中提取标题候选。"""
    if not isinstance(exif_data, dict):
        return None
    ifd0 = exif_data.get("0th")
    if not isinstance(ifd0, dict):
        return None

    # 1) XPTitle
    xp_title = _decode_xp_title_value(ifd0.get(40091))
    if xp_title:
        return xp_title

    # 2) DocumentName（仅标题字段，避免与描述互相污染）
    s = _extract_ifd_text_value(ifd0, 269)
    if s:
        if len(s) <= 120 and "\n" not in s:
            return s
    return None


def _extract_description_from_exif_data(exif_data: dict | None) -> str | None:
    """从 EXIF 数据中提取描述候选。"""
    if not isinstance(exif_data, dict):
        return None
    ifd0 = exif_data.get("0th")
    if isinstance(ifd0, dict):
        # 1) XPComment
        xp_comment = _decode_xp_comment_value(ifd0.get(40092))
        if xp_comment:
            return xp_comment
        # 2) ImageDescription（仅描述字段，避免与标题互相污染）
        s = _extract_ifd_text_value(ifd0, 270)
        if s:
            return s
    # 3) UserComment
    exif_ifd = exif_data.get("Exif")
    if isinstance(exif_ifd, dict):
        s = _decode_user_comment_value(exif_ifd.get(37510))
        if s:
            return s
    return None


def load_display_title(path: str, exif_data: dict | None = None) -> str:
    """
    读取用于展示的标题：
    1) EXIF 标题字段（XPTitle/DocumentName）
    2) macOS More Info 标题（kMDItemTitle）
    3) 无则返回“（未设置）”
    """
    title = _extract_title_from_exif_data(exif_data)
    if title:
        return title
    title = _load_macos_mdls_text(path, "kMDItemTitle")
    if title:
        return title
    return "（未设置）"


def load_display_description(path: str, exif_data: dict | None = None) -> str:
    """
    读取用于展示的描述：
    1) EXIF 描述字段（XPComment/ImageDescription/UserComment）
    2) macOS More Info 描述（kMDItemDescription）
    3) 无则返回“（未设置）”
    """
    desc = _extract_description_from_exif_data(exif_data)
    if desc:
        return desc
    desc = _load_macos_mdls_text(path, "kMDItemDescription")
    if desc:
        return desc
    return "（未设置）"


def _split_tag_name_tokens(name: str) -> list[str]:
    """将 EXIF 原始标签名切分为可读 token。"""
    if not name:
        return []
    s = str(name).strip()
    # 常见缩写先保护，避免被后续规则拆碎
    protected_tokens = ("YCbCr", "GPS", "Exif", "EXIF", "JPEG", "TIFF", "CFA", "XP", "XMP", "ISO", "DNG", "OECF")
    placeholders = {}
    for idx, token in enumerate(protected_tokens):
        ph = f"zzph{chr(97 + idx)}zz"
        if token in s:
            s = s.replace(token, f" {ph} ")
            placeholders[ph] = token
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    s = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", s)
    s = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return []
    tokens = [x for x in s.split(" ") if x]
    return [placeholders.get(x, x) for x in tokens]


def _format_english_tag_name(name: str) -> str:
    """将原始标签名格式化为更可读的英文。"""
    tokens = _split_tag_name_tokens(name)
    if not tokens:
        return _sanitize_display_string(str(name or ""))
    return " ".join(tokens)


def load_tag_name_token_map_zh_from_settings(data: dict | None = None) -> dict:
    """从 EXIF.cfg 读取标签分词中文映射（exif_tag_name_token_map_zh）。"""
    default_map = {}
    if data is None:
        data = _load_settings()
    val = data.get("exif_tag_name_token_map_zh")
    if not isinstance(val, dict):
        return default_map
    merged = dict(default_map)
    for k, v in val.items():
        if isinstance(k, str) and isinstance(v, str):
            kk = _sanitize_display_string(k)
            vv = _sanitize_display_string(v)
            if kk and vv:
                merged[kk] = vv
    return merged


def _translate_tag_name_to_chinese(name: str, token_map: dict | None = None) -> str:
    """将英文 EXIF 标签名尽量转换为中文可读名称。"""
    if not name:
        return ""
    if token_map is None:
        token_map = load_tag_name_token_map_zh_from_settings()
    # 优先使用官方/常见精确名
    fast = token_map.get(name)
    if fast:
        return fast
    parts = []
    for tok in _split_tag_name_tokens(name):
        zh = token_map.get(tok)
        if zh is None:
            zh = token_map.get(tok.lower())
        parts.append(zh if zh else tok)
    if not parts:
        return _sanitize_display_string(str(name))
    text = " ".join(parts)
    # 连续中文词去空格，ASCII/缩写与中文之间保留空格
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return _sanitize_display_string(text)


def _build_default_exif_tag_names_zh(token_map: dict | None = None) -> dict:
    """基于 piexif 全量标签生成默认中文名映射。"""
    if token_map is None:
        token_map = load_tag_name_token_map_zh_from_settings()
    result = {}
    for ifd_name in ("0th", "Exif", "GPS", "1st", "Interop"):
        ifd_data = piexif.TAGS.get(ifd_name, {})
        for tag_id, info in ifd_data.items():
            key = f"{ifd_name}:{tag_id}"
            if isinstance(info, dict):
                raw_name = str(info.get("name", f"Tag {tag_id}"))
            else:
                raw_name = str(info)
            result[key] = _translate_tag_name_to_chinese(raw_name, token_map=token_map)
    result[META_TITLE_PRIORITY_KEY] = "标题"
    result[META_DESCRIPTION_PRIORITY_KEY] = "描述"
    result[HYPERFOCAL_PRIORITY_KEY] = "超焦距"
    return result


def load_exif_tag_names_zh_from_settings() -> dict:
    """从 EXIF.cfg 读取 EXIF 标签中文名映射（key 为 ifd_name:tag_id），并补全缺失项。"""
    data = _load_settings()
    token_map = load_tag_name_token_map_zh_from_settings(data)
    merged = _build_default_exif_tag_names_zh(token_map=token_map)
    val = data.get("exif_tag_names_zh")
    if not isinstance(val, dict):
        return merged
    for k, v in val.items():
        if isinstance(k, str) and isinstance(v, str):
            vv = _sanitize_display_string(v)
            if vv:
                merged[k] = vv
    return merged


def get_tag_name(ifd_name: str, tag_id: int, use_chinese: bool = False, names_zh: dict | None = None) -> str:
    """
    获取 tag 的可读名称。
    use_chinese=True 时优先返回中文；若映射缺失则按标签英文名自动生成中文。
    """
    if ifd_name == META_IFD_NAME and str(tag_id) == META_TITLE_TAG_ID:
        if use_chinese:
            if names_zh is None:
                names_zh = load_exif_tag_names_zh_from_settings()
            zh_name = names_zh.get(META_TITLE_PRIORITY_KEY) if isinstance(names_zh, dict) else None
            return _sanitize_display_string(zh_name) if isinstance(zh_name, str) and zh_name.strip() else "标题"
        return "Title"
    if ifd_name == META_IFD_NAME and str(tag_id) == META_DESCRIPTION_TAG_ID:
        if use_chinese:
            if names_zh is None:
                names_zh = load_exif_tag_names_zh_from_settings()
            zh_name = names_zh.get(META_DESCRIPTION_PRIORITY_KEY) if isinstance(names_zh, dict) else None
            return _sanitize_display_string(zh_name) if isinstance(zh_name, str) and zh_name.strip() else "描述"
        return "Description"
    if ifd_name == "thumbnail":
        return "（二进制数据）"
    if ifd_name == CALC_IFD_NAME and str(tag_id) == HYPERFOCAL_TAG_ID:
        if use_chinese:
            if names_zh is None:
                names_zh = load_exif_tag_names_zh_from_settings()
            zh_name = names_zh.get(HYPERFOCAL_PRIORITY_KEY) if isinstance(names_zh, dict) else None
            return _sanitize_display_string(zh_name) if isinstance(zh_name, str) and zh_name.strip() else "超焦距"
        return "Hyperfocal Distance"
    key = f"{ifd_name}:{tag_id}"
    t = piexif.TAGS.get(ifd_name, {})
    info = t.get(tag_id)
    raw_name = ""
    if isinstance(info, dict):
        raw_name = str(info.get("name", f"Tag {tag_id}"))
    elif info is None:
        raw_name = f"Tag {tag_id}"
    else:
        raw_name = str(info)
    raw_name = _sanitize_display_string(raw_name)
    if use_chinese:
        if names_zh is None:
            names_zh = load_exif_tag_names_zh_from_settings()
        zh_name = names_zh.get(key) if isinstance(names_zh, dict) else None
        if isinstance(zh_name, str) and zh_name.strip():
            return _sanitize_display_string(zh_name)
        auto_zh = _translate_tag_name_to_chinese(raw_name)
        return auto_zh if auto_zh else f"标签 {tag_id}"
    if info is None:
        return f"Tag {tag_id}"
    return _format_english_tag_name(raw_name) or f"Tag {tag_id}"


def load_exif_piexif(path: str) -> dict | None:
    """使用 piexif 加载 EXIF（JPEG/WebP/TIFF）。"""
    try:
        return piexif.load(path)
    except Exception:
        return None


def load_exif_heic(path: str) -> dict | None:
    """使用 pillow-heif 加载 HEIC/HEIF/HIF 的 EXIF，返回与 piexif 相同的 dict 结构；无库或失败时返回 None。"""
    if pillow_heif is None:
        return None
    ext = Path(path).suffix.lower()
    if ext not in HEIF_EXTENSIONS:
        return None
    try:
        heif_file = pillow_heif.open_heif(path)
        if not heif_file or len(heif_file) == 0:
            return None
        img = heif_file[0]
        exif_bytes = None
        if hasattr(img, "info") and isinstance(getattr(img, "info", None), dict):
            exif_bytes = img.info.get("exif")
        if not exif_bytes:
            exif_bytes = getattr(img, "exif", None)
        if not exif_bytes or not isinstance(exif_bytes, bytes):
            return None
        return piexif.load(exif_bytes)
    except Exception:
        return None


def get_raw_thumbnail(path: str) -> bytes | None:
    """
    从 RAW 文件中获取嵌入的 JPEG 缩略图字节，用于预览。
    先尝试 piexif（TIFF 系 RAW 如 DNG/CR2/NEF），再尝试 rawpy。
    返回 None 表示无法获取缩略图。
    """
    if Path(path).suffix.lower() not in RAW_EXTENSIONS:
        return None
    # 1) piexif：TIFF 系 RAW 的 thumbnail 为 JPEG 字节
    try:
        data = piexif.load(path)
        thumb = data.get("thumbnail")
        if isinstance(thumb, bytes) and len(thumb) > 100:
            return thumb
    except Exception:
        pass
    # 2) rawpy：多数 RAW 格式的嵌入预览/缩略图
    if rawpy is None:
        return None
    try:
        with rawpy.imread(path) as rp:
            thumb = rp.extract_thumb()
        if thumb is None:
            return None
        if hasattr(rawpy, "ThumbFormat") and thumb.format == rawpy.ThumbFormat.JPEG:
            if isinstance(thumb.data, bytes):
                return thumb.data
    except Exception:
        pass
    return None


# EXIF Orientation 标签号 (TIFF/EXIF 0x0112)
ORIENTATION_TAG = 274


def _get_orientation_from_file(path: str) -> int:
    """
    从文件中读取 EXIF Orientation 值 (1–8)。
    先尝试 piexif（JPEG/TIFF/部分 RAW），再尝试 exifread（RAW）。
    返回 1 表示正常方向或未找到。
    """
    try:
        data = piexif.load(path)
        for ifd in ("0th", "Exif"):
            if data.get(ifd) and ORIENTATION_TAG in data[ifd]:
                v = data[ifd][ORIENTATION_TAG]
                if isinstance(v, int) and 1 <= v <= 8:
                    return v
    except Exception:
        pass
    if exifread:
        try:
            with open(path, "rb") as f:
                tags = exifread.process_file(f, details=False)
            # exifread 中 Orientation 可能在 "Image Orientation" 等
            for key in ("Image Orientation", "EXIF Orientation"):
                if key in tags:
                    try:
                        v = int(tags[key].values[0])
                        if 1 <= v <= 8:
                            return v
                    except (IndexError, ValueError, TypeError):
                        pass
        except Exception:
            pass
    return 1


def _apply_orientation_to_pixmap(pix: QPixmap, orientation: int) -> QPixmap:
    """
    根据 EXIF Orientation (1–8) 对 QPixmap 做旋转/翻转，返回新 QPixmap。
    标准仅此标签 (274) 决定显示方向；竖拍常见为 6(90° CW) / 8(270° CW)，
    部分相机/RAW 写入方向与常见约定相反，故 6/8 在此处互换以修正竖版倒置。
    """
    if orientation == 1 or pix.isNull():
        return pix
    tr = QTransform()
    if orientation == 2:
        tr.scale(-1, 1)
    elif orientation == 3:
        tr.rotate(180)
    elif orientation == 4:
        tr.scale(1, -1)
    elif orientation == 5:
        tr.rotate(-90)
        tr.scale(-1, 1)
    elif orientation == 6:
        tr.rotate(90)   # 竖拍：与 8 互换以兼容部分相机/RAW 的相反约定
    elif orientation == 7:
        tr.rotate(90)
        tr.scale(-1, 1)
    elif orientation == 8:
        tr.rotate(-90)  # 竖拍：与 6 互换以兼容部分相机/RAW 的相反约定
    else:
        return pix
    return pix.transformed(tr, _SmoothTransformation)


def _load_preview_pixmap_with_orientation(path: str) -> QPixmap | None:
    """
    加载图片并应用 EXIF 方向，使竖拍照片以竖版显示。
    仅对 PIL 可解码的格式（JPEG/PNG/WebP/TIFF 等）应用；失败或 RAW 时返回 None，由调用方回退。
    """
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            w, h = img.size
            data = img.tobytes()
        bpl = w * 3
        fmt = QImage.Format.Format_RGB888 if hasattr(QImage.Format, "Format_RGB888") else QImage.Format_RGB888
        qimg = QImage(data, w, h, bpl, fmt)
        if qimg.isNull():
            return None
        return QPixmap.fromImage(qimg)
    except Exception:
        return None


def load_exif_exifread(path: str) -> list[tuple[str, str, str]]:
    """使用 ExifRead 加载 EXIF（用于 RAW 等 piexif 不支持或失败时）。返回 [(group, name, value), ...]。"""
    if exifread is None:
        return []
    rows = []
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=True, extract_thumbnail=False)
        for key, tag in tags.items():
            if key in ("JPEGThumbnail", "TIFFThumbnail", "Filename"):
                continue
            # key 形如 "Image Make"、"EXIF DateTimeOriginal"
            if " " in key:
                group, name = key.split(None, 1)
            else:
                group, name = "ExifRead", key
            try:
                value_str = str(tag.printable) if hasattr(tag, "printable") else str(tag)
            except Exception:
                value_str = str(tag)
            value_str = _sanitize_display_string(value_str)
            rows.append((group, name, value_str))
    except Exception:
        pass
    return rows


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
                s = _safe_decode_bytes(value)
                if _decoded_looks_text(s):
                    value = s[:2048] + ("\n... (已截断)" if len(s) > 2048 else "")
                else:
                    value = value.hex() if len(value) <= 64 else value.hex() + "..."
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
        # XMLPacket / XMP 等：原为整数元组（字节），编辑后按 UTF-8 写回 bytes
        if len(raw_value) > 2 and all(isinstance(x, int) and 0 <= x <= 255 for x in raw_value):
            return s.encode("utf-8")
        if all(isinstance(x, int) for x in raw_value):
            try:
                return tuple(int(x) for x in s.replace(",", " ").split())
            except ValueError:
                return raw_value
    return s.encode("utf-8")


def _format_exception_message(e: Exception) -> str:
    """将异常格式化为可读文本，避免弹窗空白。"""
    msg = str(e).strip()
    if msg:
        return msg
    rep = repr(e).strip()
    if rep and rep != "Exception()":
        return rep
    return f"{type(e).__name__}（无详细错误信息）"


def _build_windows_app_id(app_name: str) -> str:
    """构造稳定的 Windows AppUserModelID。"""
    base = re.sub(r"[^A-Za-z0-9.]+", "", app_name) or "SuperEXIF"
    return f"oskch.{base}"


def _set_macos_process_name_via_objc(name: str) -> bool:
    """
    使用 Objective-C runtime 直接设置 macOS 进程名。
    该路径不依赖 PyObjC，可在仅有标准 Python 环境时生效。
    """
    try:
        import ctypes

        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Foundation.framework/Foundation")
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
    except Exception:
        return False

    try:
        objc_get_class = objc.objc_getClass
        objc_get_class.restype = ctypes.c_void_p
        objc_get_class.argtypes = [ctypes.c_char_p]

        sel_register_name = objc.sel_registerName
        sel_register_name.restype = ctypes.c_void_p
        sel_register_name.argtypes = [ctypes.c_char_p]

        msg_send_noarg = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        msg_send_cstr = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p
        )(("objc_msgSend", objc))
        msg_send_obj = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(("objc_msgSend", objc))

        ns_string_cls = objc_get_class(b"NSString")
        ns_process_info_cls = objc_get_class(b"NSProcessInfo")
        if not ns_string_cls or not ns_process_info_cls:
            return False

        sel_string_with_utf8 = sel_register_name(b"stringWithUTF8String:")
        sel_process_info = sel_register_name(b"processInfo")
        sel_set_process_name = sel_register_name(b"setProcessName:")

        ns_name = msg_send_cstr(ns_string_cls, sel_string_with_utf8, name.encode("utf-8"))
        if not ns_name:
            return False
        proc_info = msg_send_noarg(ns_process_info_cls, sel_process_info)
        if not proc_info:
            return False
        msg_send_obj(proc_info, sel_set_process_name, ns_name)
        return True
    except Exception:
        return False


def _apply_runtime_app_identity(app_name: str):
    """
    尽量把系统层面的应用名设置为 app_name，避免 Dock/任务栏显示为 Python。
    - macOS: 设置 NSProcessInfo 名称与 NSBundle 名称字段
    - Windows: 设置 AppUserModelID
    """
    name = _sanitize_display_string(app_name or "SuperEXIF") or "SuperEXIF"

    if sys.platform == "darwin":
        pyobjc_process_name_ok = False
        try:
            from Foundation import NSProcessInfo

            NSProcessInfo.processInfo().setProcessName_(name)
            pyobjc_process_name_ok = True
        except Exception:
            pass
        if not pyobjc_process_name_ok:
            _set_macos_process_name_via_objc(name)
        try:
            from Foundation import NSBundle

            bundle = NSBundle.mainBundle()
            if bundle is not None:
                info = bundle.localizedInfoDictionary()
                if info is None:
                    info = bundle.infoDictionary()
                if info is not None:
                    info["CFBundleName"] = name
                    info["CFBundleDisplayName"] = name
                    info["CFBundleExecutable"] = name
        except Exception:
            pass

    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_build_windows_app_id(name))
        except Exception:
            pass


def _normalize_meta_edit_text(text: str | None) -> str:
    """统一元数据编辑值，避免“（未设置）”被当成真实内容。"""
    s = _sanitize_display_string(str(text or ""))
    if s in ("（未设置）", "(未设置)", "<未设置>"):
        return ""
    return s


def _build_exiftool_key_to_piexif_key() -> dict:
    """exiftool Group:Tag -> piexif ifd:tag_id，用于排序与隐藏过滤。"""
    out = {}
    for ifd_name in ("0th", "Exif", "GPS", "1st", "Interop"):
        for tag_id in piexif.TAGS.get(ifd_name, {}):
            t = _get_exiftool_tag_target(ifd_name, tag_id)
            if t:
                out[t] = f"{ifd_name}:{tag_id}"
    return out


EXIFTOOL_KEY_TO_PIEXIF_KEY = _build_exiftool_key_to_piexif_key()

# exiftool group alias -> canonical group used by _build_exiftool_key_to_piexif_key
EXIFTOOL_GROUP_ALIASES = {
    "IFD0": "IFD0",
    "IFD1": "IFD1",
    "GPS": "GPS",
    "EXIF": "EXIF",
    "ExifIFD": "EXIF",
    "SubIFD": "EXIF",
    "Interop": "InteropIFD",
    "InteropIFD": "InteropIFD",
}

# exiftool alias keys that should map to configured piexif-style keys.
# This keeps exif_tag_priority (e.g. Exif:40962) effective even when exiftool returns aliases.
EXIFTOOL_ALIAS_KEY_TO_PIEXIF_KEY = {
    "IFD0:ModifyDate": "0th:306",
    "EXIF:ISO": "Exif:34855",
    "ExifIFD:ISO": "Exif:34855",
    "EXIF:ExifImageWidth": "Exif:40962",
    "EXIF:ExifImageHeight": "Exif:40963",
    "ExifIFD:ExifImageWidth": "Exif:40962",
    "ExifIFD:ExifImageHeight": "Exif:40963",
    # Keep compatibility with existing priority key 37378 in config.
    "EXIF:ExposureCompensation": "Exif:37378",
    "ExifIFD:ExposureCompensation": "Exif:37378",
}


def map_exiftool_key_to_piexif_key(exiftool_key: str | None) -> str | None:
    """
    Normalize exiftool Group:Tag key to piexif style key (ifd:tag_id).
    Returns None when no reliable mapping exists.
    """
    if not isinstance(exiftool_key, str):
        return None
    key = exiftool_key.strip()
    if not key or ":" not in key:
        return None

    mapped = EXIFTOOL_KEY_TO_PIEXIF_KEY.get(key)
    if mapped:
        return mapped

    mapped = EXIFTOOL_ALIAS_KEY_TO_PIEXIF_KEY.get(key)
    if mapped:
        return mapped

    group, tag_name = key.split(":", 1)
    group_norm = EXIFTOOL_GROUP_ALIASES.get(group)
    if not group_norm:
        return None

    mapped = EXIFTOOL_KEY_TO_PIEXIF_KEY.get(f"{group_norm}:{tag_name}")
    if mapped:
        return mapped

    mapped = EXIFTOOL_ALIAS_KEY_TO_PIEXIF_KEY.get(f"{group_norm}:{tag_name}")
    if mapped:
        return mapped
    return None


def get_tag_name_for_exiftool_key(
    exiftool_key: str, tag_name: str, use_chinese: bool, names_zh: dict | None = None
) -> str:
    """
    根据 exiftool 的 Group:Tag 键和原始标签名，返回显示用标签名。
    用于 exiftool 加载的行（ifd_name/tag_id 为 None）在中文/英文切换时正确显示。
    """
    if not use_chinese:
        return _format_english_tag_name(tag_name) or _sanitize_display_string(tag_name)
    if names_zh is None:
        names_zh = load_exif_tag_names_zh_from_settings()
    zh = names_zh.get(exiftool_key) if isinstance(names_zh, dict) else None
    if isinstance(zh, str) and zh.strip():
        return _sanitize_display_string(zh)
    piexif_key = map_exiftool_key_to_piexif_key(exiftool_key)
    if piexif_key:
        parts = piexif_key.split(":", 1)
        if len(parts) == 2:
            try:
                ifd_name, tag_id = parts[0], int(parts[1])
                return get_tag_name(ifd_name, tag_id, use_chinese=True, names_zh=names_zh)
            except ValueError:
                pass
    auto_zh = _translate_tag_name_to_chinese(tag_name)
    return auto_zh if auto_zh else _sanitize_display_string(tag_name)


def get_all_exif_tag_keys(use_chinese: bool = False) -> list[tuple]:
    """
    从 piexif.TAGS 收集所有可配置的 (key, 显示文本)。
    key = "ifd_name:tag_id"，显示文本 = "分组 - 标签名"。
    """
    result = []
    names_zh = load_exif_tag_names_zh_from_settings() if use_chinese else None
    title_name = get_tag_name(META_IFD_NAME, META_TITLE_TAG_ID, use_chinese=use_chinese, names_zh=names_zh)
    result.append((META_TITLE_PRIORITY_KEY, f"{IFD_DISPLAY_NAMES.get(META_IFD_NAME, META_IFD_NAME)} - {title_name}"))
    desc_name = get_tag_name(META_IFD_NAME, META_DESCRIPTION_TAG_ID, use_chinese=use_chinese, names_zh=names_zh)
    result.append((META_DESCRIPTION_PRIORITY_KEY, f"{IFD_DISPLAY_NAMES.get(META_IFD_NAME, META_IFD_NAME)} - {desc_name}"))
    calc_name = get_tag_name(CALC_IFD_NAME, HYPERFOCAL_TAG_ID, use_chinese=use_chinese, names_zh=names_zh)
    result.append((HYPERFOCAL_PRIORITY_KEY, f"{IFD_DISPLAY_NAMES.get(CALC_IFD_NAME, CALC_IFD_NAME)} - {calc_name}"))
    for ifd_name in ("0th", "Exif", "GPS", "1st", "Interop"):
        ifd_data = piexif.TAGS.get(ifd_name, {})
        if not ifd_data:
            continue
        group = IFD_DISPLAY_NAMES.get(ifd_name, ifd_name)
        for tag_id, info in ifd_data.items():
            name = get_tag_name(ifd_name, tag_id, use_chinese=use_chinese, names_zh=names_zh)
            key = f"{ifd_name}:{tag_id}"
            result.append((key, f"{group} - {name}"))
    return result


# 内置默认显示顺序：相机、镜头、曝光、ISO、时间等常用项
DEFAULT_EXIF_TAG_PRIORITY = [
    META_TITLE_PRIORITY_KEY,  # 元数据标题（macOS More Info / EXIF 标题）
    META_DESCRIPTION_PRIORITY_KEY,  # 元数据描述（macOS More Info / EXIF 描述）
    HYPERFOCAL_PRIORITY_KEY,  # 计算值：超焦距
    "0th:271",   # Make 制造商
    "0th:272",   # Model 型号
    "0th:306",   # DateTime
    "Exif:33434",  # ExposureTime 曝光时间
    "Exif:33437",  # FNumber 光圈
    "Exif:37386",  # FocalLength 焦距
    "Exif:37382",  # SubjectDistance 对焦距离
    "Exif:41996",  # SubjectDistanceRange 对焦距离范围
    "Exif:34855",  # ISOSpeedRatings
    "Exif:36867",  # DateTimeOriginal 拍摄时间
    "Exif:42036",  # LensModel 镜头型号
    "Exif:41987",  # WhiteBalance 白平衡
    "Exif:37378",  # ExposureBias 曝光补偿
    "Exif:40962",  # ExifImageWidth
    "Exif:40963",  # ExifImageLength
]


def load_tag_priority_from_settings() -> list:
    """从 EXIF.cfg 读取优先显示的 tag key 列表，缺省时返回内置默认顺序。"""
    data = _load_settings()
    val = data.get("exif_tag_priority", [])
    lst = list(val) if isinstance(val, list) else []
    base = lst if lst else DEFAULT_EXIF_TAG_PRIORITY.copy()
    normalized = []
    seen = set()
    for key in (META_TITLE_PRIORITY_KEY, META_DESCRIPTION_PRIORITY_KEY, HYPERFOCAL_PRIORITY_KEY, *base):
        if not isinstance(key, str) or not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return normalized


def save_tag_priority_to_settings(priority_keys: list):
    """将优先显示的 tag key 列表写入 EXIF.cfg。"""
    data = _load_settings()
    normalized = []
    seen = set()
    for key in (META_TITLE_PRIORITY_KEY, META_DESCRIPTION_PRIORITY_KEY, HYPERFOCAL_PRIORITY_KEY, *(list(priority_keys) if isinstance(priority_keys, list) else [])):
        if not isinstance(key, str) or not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    data["exif_tag_priority"] = normalized
    _save_settings(data)


def load_exif_tag_hidden_from_settings() -> set:
    """从 EXIF.cfg 读取禁止显示的 tag key 集合（ifd:tag_id），如 0th:279。仅由 cfg 配置，无默认项。"""
    data = _load_settings()
    val = data.get("exif_tag_hidden", [])
    lst = val if isinstance(val, list) else []
    return {str(k).strip() for k in lst if isinstance(k, str) and k.strip()}


def save_exif_tag_hidden_to_settings(hidden_keys: list):
    """将禁止显示的 tag key 列表写入 EXIF.cfg。"""
    data = _load_settings()
    normalized = []
    seen = set()
    for k in (list(hidden_keys) if isinstance(hidden_keys, list) else []):
        s = str(k).strip() if k is not None else ""
        if not s or s in seen:
            continue
        normalized.append(s)
        seen.add(s)
    data["exif_tag_hidden"] = normalized
    _save_settings(data)


def load_tag_label_chinese_from_settings() -> bool:
    """是否使用中文显示 EXIF 标签名。"""
    data = _load_settings()
    return bool(data.get("exif_tag_label_chinese", False))


def save_tag_label_chinese_to_settings(use_chinese: bool):
    """保存 EXIF 标签名显示语言。"""
    data = _load_settings()
    data["exif_tag_label_chinese"] = use_chinese
    _save_settings(data)


def load_hyperfocal_coc_mm_from_settings() -> float:
    """读取超焦距计算的默认弥散圆（mm），缺省 0.03。"""
    data = _load_settings()
    val = data.get("hyperfocal_coc_mm", 0.03)
    try:
        f = float(val)
        if f > 0:
            return f
    except (TypeError, ValueError):
        pass
    return 0.03


def apply_tag_priority(rows: list[tuple], priority_keys: list[str]) -> list[tuple]:
    """
    按配置的 tag 顺序重排：先把全部 EXIF 读入列表，按 exif_tag_priority 顺序
    在「EXIF 信息」列表前部显示设定的 tag，已显示的从列表中移除，再把剩余项追加到列表。
    """

    def row_key(row):
        if len(row) > 6 and row[6]:
            mapped = map_exiftool_key_to_piexif_key(row[6])
            return mapped if mapped else row[6]
        if len(row) < 2:
            return None
        ifd_name, tag_id = row[0], row[1]
        if ifd_name is None or tag_id is None:
            return None
        return f"{ifd_name}:{tag_id}"

    def row_signature(row):
        if len(row) < 5:
            return None
        name = _sanitize_display_string(str(row[3] or "")).strip().lower()
        value = _sanitize_display_string(str(row[4] or "")).strip()
        if not name and not value:
            return None
        return f"{name}\x1f{value}"

    normalized_priority = [k for k in priority_keys if isinstance(k, str) and k]
    if not normalized_priority:
        return list(rows)

    exif_info_list = list(rows)
    display_list = []
    displayed_keys = set()

    for key in normalized_priority:
        # 先在 exif_info_list 找到该 key 的首个条目放入前部，
        # 再从 exif_info_list 移除该 key 的所有条目，避免后面重复显示。
        matched_row = None
        remaining_rows = []
        for row in exif_info_list:
            if row_key(row) == key:
                if matched_row is None:
                    matched_row = row
                continue
            remaining_rows.append(row)
        exif_info_list = remaining_rows
        if matched_row is not None:
            display_list.append(matched_row)
            displayed_keys.add(key)
            # 标题/描述在前部显示后，移除其语义重复的 exiftool 行，避免后面重复显示
            if key == META_TITLE_PRIORITY_KEY:
                exif_info_list = [r for r in exif_info_list if not (len(r) > 6 and r[6] in EXIFTOOL_KEYS_DUPLICATE_OF_TITLE)]
            elif key == META_DESCRIPTION_PRIORITY_KEY:
                exif_info_list = [r for r in exif_info_list if not (len(r) > 6 and r[6] in EXIFTOOL_KEYS_DUPLICATE_OF_DESCRIPTION)]

    # 再次兜底：若剩余项中仍有已在前部显示过的 key，则不再重复显示。
    exif_info_list = [r for r in exif_info_list if row_key(r) not in displayed_keys]

    # 再做一层明显重复项去重：同“标签名+值”只保留首次出现。
    seen_signatures = set()
    for row in display_list:
        sig = row_signature(row)
        if sig:
            seen_signatures.add(sig)
    for row in exif_info_list:
        sig = row_signature(row)
        if sig and sig in seen_signatures:
            continue
        if sig:
            seen_signatures.add(sig)
        display_list.append(row)
    return display_list


def load_all_exif_exiftool(path: str, tag_label_chinese: bool = False) -> list[tuple]:
    """
    用 exiftool -j -G1 加载 EXIF，返回 7 元组列表，第 7 项为 exiftool_key（Group:Tag）。
    无 exiftool 或失败返回 []。
    """
    lst = run_exiftool_json(path)
    if not lst or not isinstance(lst[0], dict):
        return []
    obj = lst[0]
    names_zh = load_exif_tag_names_zh_from_settings() if tag_label_chinese else None
    hidden_keys = load_exif_tag_hidden_from_settings()
    hidden_exiftool = set()
    for k in hidden_keys:
        parts = k.split(":", 1)
        if len(parts) == 2:
            try:
                ifd_name, tag_id = parts[0], int(parts[1])
                t = _get_exiftool_tag_target(ifd_name, tag_id)
                if t:
                    hidden_exiftool.add(t)
            except ValueError:
                pass

    def _fmt(v):
        return _extract_exiftool_text_value(v)

    title_value = _pick_preferred_meta_text(
        obj.get("XMP-dc:Title"),
        obj.get("IFD0:XPTitle"),
        obj.get("IFD0:DocumentName"),
    )
    desc_value = _pick_preferred_meta_text(
        obj.get("XMP-dc:Description"),
        obj.get("IFD0:XPComment"),
        obj.get("IFD0:ImageDescription"),
        obj.get("EXIF:UserComment"),
        obj.get("ExifIFD:UserComment"),
    )
    desc_raw_value = _normalize_meta_edit_text(desc_value)
    rows = []
    rows.append(
        (
            META_IFD_NAME,
            META_TITLE_TAG_ID,
            IFD_DISPLAY_NAMES.get(META_IFD_NAME, META_IFD_NAME),
            get_tag_name(META_IFD_NAME, META_TITLE_TAG_ID, use_chinese=tag_label_chinese, names_zh=names_zh),
            title_value,
            _normalize_meta_edit_text(title_value),
            None,
        )
    )
    rows.append(
        (
            META_IFD_NAME,
            META_DESCRIPTION_TAG_ID,
            IFD_DISPLAY_NAMES.get(META_IFD_NAME, META_IFD_NAME),
            get_tag_name(META_IFD_NAME, META_DESCRIPTION_TAG_ID, use_chinese=tag_label_chinese, names_zh=names_zh),
            desc_value,
            desc_raw_value,
            None,
        )
    )
    rows.append(
        (
            CALC_IFD_NAME,
            HYPERFOCAL_TAG_ID,
            IFD_DISPLAY_NAMES.get(CALC_IFD_NAME, CALC_IFD_NAME),
            get_tag_name(CALC_IFD_NAME, HYPERFOCAL_TAG_ID, use_chinese=tag_label_chinese, names_zh=names_zh),
            _format_hyperfocal_distance(
                _calc_hyperfocal_distance_from_exiftool_obj(
                    obj, default_coc_mm=load_hyperfocal_coc_mm_from_settings()
                )
            ),
            None,
            None,
        )
    )
    skip_keys = {"SourceFile", "File:FileName", "File:Directory", "File:FileSize", "File:FileModifyDate", "File:FileAccessDate", "File:FileCreateDate", "File:FilePermissions", "File:FileType", "File:FileTypeExtension", "File:MIMEType"}
    skip_keys |= EXIFTOOL_KEYS_DUPLICATE_OF_TITLE | EXIFTOOL_KEYS_DUPLICATE_OF_DESCRIPTION
    for key, value in obj.items():
        if not isinstance(key, str) or ":" not in key or key in skip_keys:
            continue
        group, tag_name = key.split(":", 1)
        if group in {"System", "ExifTool", "File"}:
            continue
        mapped_key = map_exiftool_key_to_piexif_key(key)
        if key in hidden_exiftool or (mapped_key in hidden_keys if mapped_key else False):
            continue
        value_str = _fmt(value)
        display_name = get_tag_name_for_exiftool_key(key, tag_name, tag_label_chinese, names_zh)
        rows.append((None, None, group, display_name, value_str, value, key))
    return rows


def load_all_exif(path: str, tag_label_chinese: bool = False) -> list[tuple]:
    """
    加载全部 EXIF，返回 [(ifd_name, tag_id, 分组, 标签名, 值字符串, raw_value, exiftool_key?), ...]。
    有 exiftool 时优先用 exiftool 读取（兼容性更好）；否则用 piexif/heic/exifread/pillow。
    """
    if get_exiftool_executable_path():
        exif_rows = load_all_exif_exiftool(path, tag_label_chinese=tag_label_chinese)
        if len(exif_rows) > 2:
            return exif_rows
    rows = []
    names_zh = load_exif_tag_names_zh_from_settings() if tag_label_chinese else None
    data = load_exif_piexif(path) or (load_exif_heic(path) if Path(path).suffix.lower() in HEIF_EXTENSIONS else None)
    title_value = load_display_title(path, exif_data=data)
    desc_value = load_display_description(path, exif_data=data)
    desc_raw_value = _normalize_meta_edit_text(desc_value)
    has_front_desc = bool(desc_raw_value)

    def _is_image_description_name(tag_name: str | None) -> bool:
        """判断标签名是否为图像描述（用于去重显示）。"""
        if not tag_name:
            return False
        s = _sanitize_display_string(str(tag_name)).strip()
        if not s:
            return False
        if s in ("图像描述", "ImageDescription", "Image Description"):
            return True
        key = re.sub(r"[\s_-]+", "", s).lower()
        return key == "imagedescription"
    exiftool_key_for = _get_exiftool_tag_target
    rows.append(
        (
            META_IFD_NAME,
            META_TITLE_TAG_ID,
            IFD_DISPLAY_NAMES.get(META_IFD_NAME, META_IFD_NAME),
            get_tag_name(META_IFD_NAME, META_TITLE_TAG_ID, use_chinese=tag_label_chinese, names_zh=names_zh),
            title_value,
            _normalize_meta_edit_text(title_value),
            None,
        )
    )
    rows.append(
        (
            META_IFD_NAME,
            META_DESCRIPTION_TAG_ID,
            IFD_DISPLAY_NAMES.get(META_IFD_NAME, META_IFD_NAME),
            get_tag_name(META_IFD_NAME, META_DESCRIPTION_TAG_ID, use_chinese=tag_label_chinese, names_zh=names_zh),
            desc_value,
            desc_raw_value,
            None,
        )
    )
    hidden_keys = load_exif_tag_hidden_from_settings()
    if data:
        hyperfocal_m = _calc_hyperfocal_distance_m(data, default_coc_mm=load_hyperfocal_coc_mm_from_settings())
        rows.append(
            (
                CALC_IFD_NAME,
                HYPERFOCAL_TAG_ID,
                IFD_DISPLAY_NAMES.get(CALC_IFD_NAME, CALC_IFD_NAME),
                get_tag_name(CALC_IFD_NAME, HYPERFOCAL_TAG_ID, use_chinese=tag_label_chinese, names_zh=names_zh),
                _format_hyperfocal_distance(hyperfocal_m),
                None,  # 计算值，不可编辑
                None,
            )
        )
        for ifd_name in ("0th", "Exif", "GPS", "1st", "Interop"):
            ifd_data = data.get(ifd_name)
            if not ifd_data or not isinstance(ifd_data, dict):
                continue
            group = IFD_DISPLAY_NAMES.get(ifd_name, ifd_name)
            for tag_id, value in ifd_data.items():
                if f"{ifd_name}:{tag_id}" in hidden_keys:
                    continue
                # 前置“描述”已有值时，隐藏后续重复的 ImageDescription(0th:270)
                if has_front_desc and ifd_name == "0th" and tag_id == 270:
                    continue
                name = get_tag_name(ifd_name, tag_id, use_chinese=tag_label_chinese, names_zh=names_zh)
                raw = value
                tag_type = get_tag_type(ifd_name, tag_id)
                ek = exiftool_key_for(ifd_name, tag_id)
                rows.append((ifd_name, tag_id, group, name, format_exif_value(value, expected_type=tag_type), raw, ek))
        if data.get("thumbnail"):
            rows.append((None, None, IFD_DISPLAY_NAMES["thumbnail"], "（存在）", "是", None, None))
    if len(rows) <= 2 and Path(path).suffix.lower() in RAW_EXTENSIONS and exifread:
        for group, name, value in load_exif_exifread(path):
            if has_front_desc and _is_image_description_name(name):
                continue
            rows.append((None, None, group, name, value, None, None))
    if len(rows) <= 2:
        for group, name, value in load_exif_pillow(path):
            if has_front_desc and _is_image_description_name(name):
                continue
            rows.append((None, None, group, name, value, None, None))
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
        self._source_pixmap = None  # 原始预览图（未按控件尺寸缩放）
        self._pixmap = None
        self.setText("将图片拖入此处\n或点击选择文件")

    def _render_scaled_preview(self):
        """根据当前控件尺寸，从原始预览图重新高质量缩放显示。"""
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        target_w = max(1, self.size().width() - 20)
        target_h = max(1, self.size().height() - 20)
        self._pixmap = self._source_pixmap.scaled(
            target_w,
            target_h,
            _KeepAspectRatio,
            _SmoothTransformation,
        )
        self.setPixmap(self._pixmap)
        self.setText("")

    def set_image(self, path: str):
        self._current_path = path
        self._source_pixmap = None
        pix = _load_preview_pixmap_with_orientation(path)
        is_raw = Path(path).suffix.lower() in RAW_EXTENSIONS
        if (pix is None or pix.isNull()) and is_raw:
            thumb_data = get_raw_thumbnail(path)
            if thumb_data:
                pix = QPixmap()
                if pix.loadFromData(thumb_data):
                    pix = _apply_orientation_to_pixmap(pix, _get_orientation_from_file(path))
                    self._source_pixmap = pix
                    self._render_scaled_preview()
                    return
        if pix is None or pix.isNull():
            pix = QPixmap(path)
        if pix is not None and not pix.isNull():
            if is_raw:
                pix = _apply_orientation_to_pixmap(pix, _get_orientation_from_file(path))
            self._source_pixmap = pix
            self._render_scaled_preview()
        else:
            self._source_pixmap = None
            self._pixmap = None
            self.setPixmap(QPixmap())
            self.setText(f"无法预览\n{Path(path).name}")

    def clear_image(self):
        self._current_path = None
        self._source_pixmap = None
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.setText("将图片拖入此处\n或点击选择文件")

    def current_path(self):
        return self._current_path

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._source_pixmap is not None and not self._source_pixmap.isNull():
            self._render_scaled_preview()

    def mousePressEvent(self, event):
        if event.button() == _LeftButton:
            std_exts = " ".join(f"*{e}" for e in (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".heic", ".heif", ".hif"))
            raw_exts = " ".join(f"*{e}" for e in RAW_EXTENSIONS)
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择图片",
                os.path.expanduser("~"),
                f"图片 ({std_exts});;RAW ({raw_exts});;全部 (*.*)",
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
                if path and Path(path).suffix.lower() in IMAGE_EXTENSIONS:
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
        self.setColumnWidth(1, 220)  # “标签”列加宽以便显示全
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

    def get_all_rows(self) -> list[tuple]:
        """返回当前全部行数据（用于切换标签语言时重算标签名）。"""
        return list(self._all_rows)

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
            exiftool_key = row[6] if len(row) > 6 else None
            it0 = QTableWidgetItem(group)
            it0.setFlags(it0.flags() & ~_ItemIsEditable)
            self.setItem(i, 0, it0)
            it1 = QTableWidgetItem(name)
            it1.setFlags(it1.flags() & ~_ItemIsEditable)
            self.setItem(i, 1, it1)
            it2 = QTableWidgetItem(value_str)
            editable_exif = (
                isinstance(ifd_name, str)
                and ifd_name in ("0th", "Exif", "GPS", "1st", "Interop")
                and isinstance(tag_id, int)
                and raw_value is not None
            )
            editable_meta = (
                ifd_name == META_IFD_NAME
                and str(tag_id) in (META_TITLE_TAG_ID, META_DESCRIPTION_TAG_ID)
            )
            editable_exiftool_row = exiftool_key is not None and ifd_name is None and tag_id is None
            editable = editable_exif or editable_meta or editable_exiftool_row
            if editable:
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
        exiftool_key = row_data[6] if len(row_data) > 6 else None
        is_editable_exif = (
            isinstance(ifd_name, str)
            and ifd_name in ("0th", "Exif", "GPS", "1st", "Interop")
            and isinstance(tag_id, int)
            and raw_value is not None
        )
        is_editable_meta = (
            ifd_name == META_IFD_NAME
            and str(tag_id) in (META_TITLE_TAG_ID, META_DESCRIPTION_TAG_ID)
        )
        is_editable_exiftool_row = exiftool_key is not None and ifd_name is None and tag_id is None
        if not (is_editable_exif or is_editable_meta or is_editable_exiftool_row):
            return
        new_val = item.text().strip()
        if new_val == old_val:
            return
        self._save_callback(ifd_name, tag_id, new_val, raw_value, exiftool_key)

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
    """配置 EXIF 标签优先显示顺序与禁止显示列表的对话框。"""

    def __init__(self, parent=None, use_chinese: bool = False):
        super().__init__(parent)
        self.setWindowTitle("EXIF 显示顺序")
        self.setMinimumSize(480, 420)
        self._all_tags = get_all_exif_tag_keys(use_chinese=use_chinese)
        self._priority_keys = []
        self._hidden_keys = []  # 列表顺序用于保存到 cfg

        tabs = QTabWidget()
        # Tab1: 显示顺序
        order_w = QWidget()
        order_layout = QVBoxLayout(order_w)
        order_layout.addWidget(QLabel("以下标签将优先显示在 EXIF 列表顶部，按顺序排列："))
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        order_layout.addWidget(self.list_widget)
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
        order_layout.addLayout(btn_layout)
        tabs.addTab(order_w, "显示顺序")

        # Tab2: 禁止显示
        hidden_w = QWidget()
        hidden_layout = QVBoxLayout(hidden_w)
        hidden_layout.addWidget(QLabel("以下标签将不在 EXIF 列表中显示（格式如 0th:279）："))
        self.hidden_list_widget = QListWidget()
        self.hidden_list_widget.setAlternatingRowColors(True)
        hidden_layout.addWidget(self.hidden_list_widget)
        hidden_btn = QHBoxLayout()
        hidden_btn.addStretch()
        self.btn_hidden_add = QPushButton("添加…")
        self.btn_hidden_add.clicked.connect(self._add_hidden_tag)
        self.btn_hidden_remove = QPushButton("删除")
        self.btn_hidden_remove.clicked.connect(self._remove_hidden)
        hidden_btn.addWidget(self.btn_hidden_add)
        hidden_btn.addWidget(self.btn_hidden_remove)
        hidden_btn.addStretch()
        hidden_layout.addLayout(hidden_btn)
        tabs.addTab(hidden_w, "禁止显示")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            if hasattr(QDialogButtonBox.StandardButton, "Ok")
            else QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)
        self._load_from_settings()

    def _load_from_settings(self):
        self._priority_keys = load_tag_priority_from_settings()
        data = _load_settings()
        val = data.get("exif_tag_hidden", [])
        lst = val if isinstance(val, list) else []
        self._hidden_keys = [str(k).strip() for k in lst if isinstance(k, str) and k.strip()]
        self._refresh_list()
        self._refresh_hidden_list()

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

    def _refresh_hidden_list(self):
        self.hidden_list_widget.clear()
        key_to_text = {k: t for k, t in self._all_tags}
        for key in self._hidden_keys:
            text = key_to_text.get(key, key)
            item = QListWidgetItem(text)
            item.setData(_UserRole, key)
            self.hidden_list_widget.addItem(item)

    def _add_hidden_tag(self):
        d = QDialog(self)
        d.setWindowTitle("选择要禁止显示的标签")
        d.setMinimumSize(400, 350)
        layout = QVBoxLayout(d)
        layout.addWidget(QLabel("搜索："))
        search = QLineEdit()
        search.setPlaceholderText("输入分组或标签名过滤…")
        layout.addWidget(search)
        all_list = QListWidget()
        existing = set(self._hidden_keys)
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
            if key and key not in self._hidden_keys:
                self._hidden_keys.append(key)
                self._refresh_hidden_list()

    def _remove_hidden(self):
        row = self.hidden_list_widget.currentRow()
        if row < 0:
            return
        self._hidden_keys.pop(row)
        self._refresh_hidden_list()
        if self.hidden_list_widget.count():
            self.hidden_list_widget.setCurrentRow(min(row, self.hidden_list_widget.count() - 1))

    def get_priority_keys(self):
        return list(self._priority_keys)

    def accept(self):
        save_tag_priority_to_settings(self._priority_keys)
        save_exif_tag_hidden_to_settings(self._hidden_keys)
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        info = load_about_info(_get_config_path())
        version = info.get("version", "").strip()
        title = f"SuperEXIF - 图片 EXIF 查看与编辑器 by osk.ch"
        if version:
            title = f"SuperEXIF {version} - 图片 EXIF 查看与编辑器 by osk.ch"
        self.setWindowTitle(title)
        self.setMinimumSize(600, 800)
        self.resize(1080, 1920)
        self._init_menu_bar()
        icon_path = _get_app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 并排：左侧图片，右侧 EXIF
        splitter = QSplitter(_Horizontal)

        # 左侧：App 信息 + 文件名 + 拖放区（垂直一组）
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # App 信息区：图标 + 主副标题 + “关于...”
        app_info_path = _get_resource_path("image/superexif.png") or _get_app_icon_path()
        app_info_widget = AppInfoBar(
            self,
            title="Super EXIF",
            subtitle="查看与编辑EXIF",
            icon_path=app_info_path,
            on_about_clicked=self._show_about_dialog,
        )
        left_layout.addWidget(app_info_widget)

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
        self.check_tag_chinese = QCheckBox("中文标签")
        self.check_tag_chinese.setChecked(load_tag_label_chinese_from_settings())
        self.check_tag_chinese.setToolTip("勾选显示汉字标签名，否则显示英文")
        self.check_tag_chinese.toggled.connect(self._on_tag_label_lang_toggled)
        top_row.addWidget(self.check_tag_chinese)
        self.btn_config_order = QPushButton("配置显示顺序")
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

    def _init_menu_bar(self):
        help_menu = self.menuBar().addMenu("帮助")
        about_action = QAction("关于...", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _show_about_dialog(self):
        info = load_about_info(_get_config_path())
        logo_path = _get_resource_path("image/superexif.png") or _get_app_icon_path()
        show_about_dialog(self, info, logo_path=logo_path)

    def _on_exif_filter_changed(self, text: str):
        self.exif_table.set_filter_text(text)

    def _on_tag_label_lang_toggled(self, checked: bool):
        save_tag_label_chinese_to_settings(checked)
        rows = self.exif_table.get_all_rows()
        if not rows:
            return
        names_zh = load_exif_tag_names_zh_from_settings() if checked else None
        new_rows = []
        for r in rows:
            if r[0] is not None and r[1] is not None:
                name = get_tag_name(r[0], r[1], use_chinese=checked, names_zh=names_zh)
            else:
                exiftool_key = r[6] if len(r) > 6 else None
                tag_name_raw = (exiftool_key.split(":", 1)[1] if exiftool_key and ":" in exiftool_key else None) or r[3]
                name = (
                    get_tag_name_for_exiftool_key(exiftool_key, tag_name_raw, checked, names_zh)
                    if exiftool_key
                    else r[3]
                )
            exiftool_key = r[6] if len(r) > 6 else None
            new_rows.append((r[0], r[1], r[2], name, r[4], r[5], exiftool_key))
        self.exif_table.set_exif(new_rows)

    def _open_tag_order_config(self):
        use_chinese = load_tag_label_chinese_from_settings()
        d = ExifTagOrderDialog(self, use_chinese=use_chinese)
        if d.exec():
            if self._current_exif_path and os.path.isfile(self._current_exif_path):
                rows = load_all_exif(self._current_exif_path, tag_label_chinese=use_chinese)
                rows = apply_tag_priority(rows, load_tag_priority_from_settings())
                self.exif_table.set_exif(rows)

    def _save_exif_value(self, ifd_name: str, tag_id, new_val: str, raw_value, exiftool_key=None):
        """将编辑后的 EXIF 值写回文件。有 exiftool 时优先用 exiftool 写入（兼容性更好）。"""
        path = self._current_exif_path
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "无法保存", "未选择图片或文件不存在。")
            return
        ext = Path(path).suffix.lower()
        has_exiftool = bool(get_exiftool_executable_path())
        try:
            if ifd_name == META_IFD_NAME and str(tag_id) in (META_TITLE_TAG_ID, META_DESCRIPTION_TAG_ID):
                meta_tag_id = str(tag_id)
                new_text = _normalize_meta_edit_text(new_val)
                old_text = _normalize_meta_edit_text(raw_value if raw_value is not None else "")
                if new_text == old_text:
                    QMessageBox.information(self, "未变更", "输入内容与当前值一致，未执行写入。")
                    return
                if has_exiftool:
                    write_meta_with_exiftool(path, meta_tag_id, new_text)
                elif ext in PIEXIF_WRITABLE_EXTENSIONS:
                    write_meta_with_piexif(path, meta_tag_id, new_text)
                else:
                    raise RuntimeError("未找到 exiftool，无法写入该格式。请配置 exiftools_win/exiftools_mac 或将其加入 PATH。")
            elif has_exiftool:
                if exiftool_key:
                    write_exif_with_exiftool_by_key(path, exiftool_key, new_val)
                elif ifd_name is not None and tag_id is not None:
                    write_exif_with_exiftool(path, ifd_name, tag_id, new_val, raw_value)
                else:
                    raise RuntimeError("无法写入该标签。")
            elif ext in PIEXIF_WRITABLE_EXTENSIONS and ifd_name is not None and tag_id is not None:
                if tag_id == 37510:
                    new_raw = b"ASCII\x00\x00\x00" + new_val.encode("utf-8")
                else:
                    new_raw = _parse_value_back(new_val, raw_value)
                if new_raw == raw_value:
                    QMessageBox.information(self, "未变更", "输入内容解析后与原值一致，未执行写入。")
                    return
                try:
                    data = piexif.load(path)
                    if ifd_name not in data or not isinstance(data[ifd_name], dict):
                        data[ifd_name] = {}
                    data[ifd_name][tag_id] = new_raw
                    exif_bytes = piexif.dump(data)
                    piexif.insert(exif_bytes, path)
                    verify_data = piexif.load(path)
                    verify_ifd = verify_data.get(ifd_name)
                    verify_raw = verify_ifd.get(tag_id) if isinstance(verify_ifd, dict) else None
                    if verify_raw != new_raw:
                        tag_type = get_tag_type(ifd_name, tag_id)
                        old_fmt = format_exif_value(new_raw, expected_type=tag_type)
                        new_fmt = format_exif_value(verify_raw, expected_type=tag_type)
                        if old_fmt != new_fmt:
                            raise RuntimeError("写入后校验失败：文件中的值与目标值不一致。")
                except Exception as e:
                    if type(e).__name__ == "InvalidImageDataError" and get_exiftool_executable_path():
                        write_exif_with_exiftool(path, ifd_name, tag_id, new_val, raw_value)
                    else:
                        raise
            else:
                raise RuntimeError("未找到 exiftool，无法写入该格式。请配置 exiftools_win/exiftools_mac 或将其加入 PATH。")
            rows = load_all_exif(path, tag_label_chinese=load_tag_label_chinese_from_settings())
            rows = apply_tag_priority(rows, load_tag_priority_from_settings())
            self.exif_table.set_exif(rows)
            QMessageBox.information(self, "已保存", "EXIF 已写入文件。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", _format_exception_message(e))

    def on_image_loaded(self, path: str):
        """图片被拖入或选择后调用。"""
        self._current_exif_path = path
        self.file_label.setText(path)
        self.file_label.setToolTip(path)
        rows = load_all_exif(path, tag_label_chinese=load_tag_label_chinese_from_settings())
        if not rows:
            QMessageBox.information(
                self,
                "无 EXIF",
                "该图片未包含 EXIF 信息或格式暂不支持。\n支持格式：JPEG、WebP、TIFF（piexif）；HEIC/HEIF/HIF（可选 pillow-heif）；各家相机 RAW（CR2/NEF/ARW/DNG 等，可选 exifread）；其他格式会尝试用 Pillow 读取。",
            )
        else:
            rows = apply_tag_priority(rows, load_tag_priority_from_settings())
        self.exif_table.set_exif(rows)


def main():
    about_info = load_about_info(_get_config_path())
    app_name = _sanitize_display_string(about_info.get("app_name", "SuperEXIF")) or "SuperEXIF"
    _apply_runtime_app_identity(app_name)
    app = QApplication(sys.argv)
    if hasattr(app, "setApplicationName"):
        app.setApplicationName(app_name)
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(app_name)
    if hasattr(app, "setApplicationVersion"):
        app.setApplicationVersion(about_info.get("version", ""))
    icon_path = _get_app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
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
