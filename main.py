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
from html import escape

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
    )
    from PyQt5.QtCore import Qt, QMimeData, QSize
    from PyQt5.QtGui import QPixmap, QImage, QTransform, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor, QAction, QIcon

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

# 支持的图片扩展名（含各家相机 RAW）
IMAGE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif",
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
    if e not in (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif")
)


# 与主程序同目录下的配置文件
CONFIG_FILENAME = "EXIF.cfg"
APP_ICON_CANDIDATES = (
    os.path.join("image", "superexif.png"),
    os.path.join("image", "superexif.ico"),
    os.path.join("image", "superexif.icns"),
)
ABOUT_INFO_DEFAULT = {
    "app_name": "SuperEXIF",
    "version": "1.0.0",
    "tagline": "图片 EXIF 查看与编辑工具",
    "description": "支持拖拽查看、过滤检索和直接编辑常见 EXIF 字段。",
    "author": "SuperEXIF Team",
    "website": "",
    "license": "",
    "copyright": "",
}


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


def format_exif_value(value):
    """
    将 piexif 的原始值格式化为可读字符串。
    凡可能是文本的（bytes、整数元组表示的字节）都先尝试按多种编码解码为可读文本，
    仅当解码结果明显不可读（乱码/二进制）时才显示十六进制。
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        s = _safe_decode_bytes(value)
        if _decoded_looks_text(s):
            if len(s) > 2048:
                return s[:2048] + "\n... (已截断)"
            return s
        return value.hex() if len(value) <= 64 else value.hex() + "..."
    if isinstance(value, tuple):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], int):
            if value[1] != 0:
                return f"{value[0]}/{value[1]} ({value[0] / value[1]:.4f})"
            return f"{value[0]}/{value[1]}"
        # XMLPacket / XMP / 其他 UNDEFINED 等可能被 piexif 解析为整数元组，按字节解码为可读文本
        data = _tuple_as_bytes(value)
        if data is not None:
            s = _safe_decode_bytes(data)
            if _decoded_looks_text(s):
                if len(s) > 2048:
                    return s[:2048] + "\n... (已截断)"
                return s
            return data.hex() if len(data) <= 64 else data.hex() + "..."
        return ", ".join(str(format_exif_value(v)) for v in value)
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


# cfg 中无 exif_tag_names_zh 时的内置默认（可被 EXIF.cfg 覆盖）
DEFAULT_EXIF_TAG_NAMES_ZH = {
    "0th:256": "图像宽度", "0th:257": "图像高度", "0th:258": "每像素位数",
    "0th:271": "制造商", "0th:272": "型号", "0th:274": "方向", "0th:282": "X 分辨率",
    "0th:283": "Y 分辨率", "0th:296": "分辨率单位", "0th:306": "日期时间",
    "0th:315": "作者", "0th:318": "色彩空间",
    "Exif:33434": "曝光时间", "Exif:33437": "光圈", "Exif:34850": "曝光程序",
    "Exif:34855": "ISO", "Exif:36864": "Exif 版本", "Exif:36867": "拍摄时间",
    "Exif:36868": "数字化时间", "Exif:37378": "曝光补偿", "Exif:37379": "测光模式",
    "Exif:37386": "焦距", "Exif:41985": "亮度", "Exif:41986": "曝光模式",
    "Exif:41987": "白平衡", "Exif:41990": "场景类型", "Exif:42036": "镜头型号",
    "Exif:40962": "图像宽度(Exif)", "Exif:40963": "图像高度(Exif)",
    "GPS:1": "GPS 纬度", "GPS:2": "GPS 经度", "GPS:3": "GPS 纬度参考",
    "GPS:4": "GPS 经度参考", "GPS:29": "GPS 日期",
}


def load_exif_tag_names_zh_from_settings() -> dict:
    """从 EXIF.cfg 读取 EXIF 标签中文名映射（key 为 ifd_name:tag_id），缺省用内置默认。"""
    data = _load_settings()
    val = data.get("exif_tag_names_zh")
    if isinstance(val, dict) and val:
        return dict(val)
    return DEFAULT_EXIF_TAG_NAMES_ZH.copy()


def get_tag_name(ifd_name: str, tag_id: int, use_chinese: bool = False) -> str:
    """获取 tag 的可读名称。use_chinese=True 时优先返回 cfg 中的中文（若有映射）。"""
    if ifd_name == "thumbnail":
        return "（二进制数据）"
    key = f"{ifd_name}:{tag_id}"
    if use_chinese:
        names_zh = load_exif_tag_names_zh_from_settings()
        if key in names_zh:
            return names_zh[key]
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


def get_all_exif_tag_keys(use_chinese: bool = False) -> list[tuple]:
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
            name = get_tag_name(ifd_name, tag_id, use_chinese=use_chinese)
            key = f"{ifd_name}:{tag_id}"
            result.append((key, f"{group} - {name}"))
    return result


# 内置默认显示顺序：相机、镜头、曝光、ISO、时间等常用项
DEFAULT_EXIF_TAG_PRIORITY = [
    "0th:271",   # Make 制造商
    "0th:272",   # Model 型号
    "0th:306",   # DateTime
    "Exif:33434",  # ExposureTime 曝光时间
    "Exif:33437",  # FNumber 光圈
    "Exif:34855",  # ISOSpeedRatings
    "Exif:36867",  # DateTimeOriginal 拍摄时间
    "Exif:37386",  # FocalLength 焦距
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
    return lst if lst else DEFAULT_EXIF_TAG_PRIORITY.copy()


def save_tag_priority_to_settings(priority_keys: list):
    """将优先显示的 tag key 列表写入 EXIF.cfg。"""
    data = _load_settings()
    data["exif_tag_priority"] = list(priority_keys)
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


def load_about_info_from_settings() -> dict:
    """从 EXIF.cfg 读取“关于”信息，缺失字段使用默认值。"""
    data = _load_settings()
    about = data.get("about", {})
    result = dict(ABOUT_INFO_DEFAULT)
    if isinstance(about, dict):
        for key in ABOUT_INFO_DEFAULT:
            value = about.get(key)
            if isinstance(value, str) and value.strip():
                result[key] = _sanitize_display_string(value)
    return result


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


def load_all_exif(path: str, tag_label_chinese: bool = False) -> list[tuple]:
    """
    加载全部 EXIF，返回 [(ifd_name, tag_id, 分组, 标签名, 值字符串, raw_value), ...]。
    tag_label_chinese 为 True 时标签名使用中文（若有映射）。
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
                name = get_tag_name(ifd_name, tag_id, use_chinese=tag_label_chinese)
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
    if not rows and Path(path).suffix.lower() in RAW_EXTENSIONS and exifread:
        for group, name, value in load_exif_exifread(path):
            rows.append((None, None, group, name, value, None))
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
        pix = _load_preview_pixmap_with_orientation(path)
        is_raw = Path(path).suffix.lower() in RAW_EXTENSIONS
        if (pix is None or pix.isNull()) and is_raw:
            thumb_data = get_raw_thumbnail(path)
            if thumb_data:
                pix = QPixmap()
                if pix.loadFromData(thumb_data):
                    pix = _apply_orientation_to_pixmap(pix, _get_orientation_from_file(path))
                    self._pixmap = pix.scaled(
                        self.size().width() - 20,
                        self.size().height() - 20,
                        _KeepAspectRatio,
                        _SmoothTransformation,
                    )
                    self.setPixmap(self._pixmap)
                    self.setText("")
                    return
        if pix is None or pix.isNull():
            pix = QPixmap(path)
        if pix is not None and not pix.isNull():
            if is_raw:
                pix = _apply_orientation_to_pixmap(pix, _get_orientation_from_file(path))
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
            self.setPixmap(QPixmap())
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
            path = self._current_path
            pix = _load_preview_pixmap_with_orientation(path)
            if pix is None or pix.isNull():
                pix = QPixmap(path)
            if pix is None or pix.isNull():
                pix = self._pixmap  # RAW 等无法直接解码时，用当前缩略图重新缩放
            if not pix.isNull():
                is_raw = Path(path).suffix.lower() in RAW_EXTENSIONS
                if is_raw and pix is not self._pixmap:
                    pix = _apply_orientation_to_pixmap(pix, _get_orientation_from_file(path))
                self._pixmap = pix.scaled(
                    self.size().width() - 20,
                    self.size().height() - 20,
                    _KeepAspectRatio,
                    _SmoothTransformation,
                )
                self.setPixmap(self._pixmap)

    def mousePressEvent(self, event):
        if event.button() == _LeftButton:
            std_exts = " ".join(f"*{e}" for e in (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"))
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

    def __init__(self, parent=None, use_chinese: bool = False):
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
        self._all_tags = get_all_exif_tag_keys(use_chinese=use_chinese)
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
        info = load_about_info_from_settings()
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
        app_info_widget = QWidget()
        app_info_layout = QHBoxLayout(app_info_widget)
        app_info_layout.setContentsMargins(0, 0, 0, 12)
        if app_info_path:
            icon_label = QLabel()
            pix = QPixmap(app_info_path)
            icon_label.setPixmap(pix.scaled(64, 64, _KeepAspectRatio, _SmoothTransformation))
            icon_label.setFixedSize(64, 64)
            app_info_layout.addWidget(icon_label)
        text_col = QWidget()
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(8, 0, 0, 0)
        text_layout.setSpacing(0)
        _align_top = getattr(Qt.AlignmentFlag, "AlignTop", None) or getattr(Qt, "AlignTop", None)
        if _align_top is not None:
            text_layout.setAlignment(_align_top)
        title_label = QLabel("Super EXIF")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #eee; margin: 0; padding: 0;")
        text_layout.addWidget(title_label)
        subtitle_label = QLabel("查看与编辑EXIF")
        subtitle_label.setStyleSheet("font-size: 12px; color: #999; margin: 0; padding: 0;")
        text_layout.addWidget(subtitle_label)
        about_btn = QPushButton("关于...")
        about_btn.setFlat(True)
        about_btn.setStyleSheet("QPushButton { color: #7eb8ed; text-align: left; padding: 0; margin: 0; min-height: 0; } QPushButton:hover { color: #9dd; }")
        about_btn.setCursor(Qt.CursorShape.PointingHandCursor if hasattr(Qt, "CursorShape") else Qt.PointingHandCursor)
        about_btn.clicked.connect(self._show_about_dialog)
        text_layout.addWidget(about_btn)
        if _align_top is not None:
            app_info_layout.addWidget(text_col, 1, _align_top)
        else:
            app_info_layout.addWidget(text_col, stretch=1)
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
        info = load_about_info_from_settings()
        d = QDialog(self)
        d.setWindowTitle(f"关于 {info['app_name']}")
        d.setMinimumSize(480, 320)
        main_layout = QVBoxLayout(d)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(24, 24, 24, 24)
        content = QHBoxLayout()
        content.setSpacing(24)
        # 左侧：LOGO
        logo_path = _get_resource_path("image/superexif.png") or _get_app_icon_path()
        if logo_path:
            pix = QPixmap(logo_path)
            if not pix.isNull():
                pix = pix.scaled(128, 128, _KeepAspectRatio, _SmoothTransformation)
                logo_label = QLabel()
                logo_label.setPixmap(pix)
                logo_label.setAlignment(_AlignCenter)
                content.addWidget(logo_label)
        # 右侧：App 信息
        title = f"{info['app_name']} {info['version']}".strip()
        lines = [
            f"<b style='font-size:14px'>{escape(title)}</b>",
            escape(info["tagline"]),
            "",
            escape(info["description"]),
        ]
        if info.get("author"):
            lines.append(f"作者：{escape(info['author'])}")
        if info.get("website"):
            lines.append(f"网站：{escape(info['website'])}")
        if info.get("license"):
            lines.append(f"许可：{escape(info['license'])}")
        if info.get("copyright"):
            lines.append(escape(info["copyright"]))
        text = "<br>".join("&nbsp;" if not line else line for line in lines)
        info_label = QLabel(text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 12px; line-height: 1.4;")
        info_label.setTextFormat(Qt.TextFormat.RichText if hasattr(Qt, "TextFormat") else Qt.RichText)
        content.addWidget(info_label, stretch=1)
        main_layout.addLayout(content)
        btn = QPushButton("确定")
        btn.setDefault(True)
        btn.clicked.connect(d.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        main_layout.addLayout(btn_row)
        d.exec()

    def _on_exif_filter_changed(self, text: str):
        self.exif_table.set_filter_text(text)

    def _on_tag_label_lang_toggled(self, checked: bool):
        save_tag_label_chinese_to_settings(checked)
        rows = self.exif_table.get_all_rows()
        if not rows:
            return
        new_rows = [
            (r[0], r[1], r[2],
             get_tag_name(r[0], r[1], use_chinese=checked) if (r[0] is not None and r[1] is not None) else r[3],
             r[4], r[5])
            for r in rows
        ]
        self.exif_table.set_exif(new_rows)

    def _open_tag_order_config(self):
        use_chinese = load_tag_label_chinese_from_settings()
        d = ExifTagOrderDialog(self, use_chinese=use_chinese)
        if d.exec():
            if self._current_exif_path and os.path.isfile(self._current_exif_path):
                rows = load_all_exif(self._current_exif_path, tag_label_chinese=use_chinese)
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
            rows = load_all_exif(path, tag_label_chinese=load_tag_label_chinese_from_settings())
            self.exif_table.set_exif(rows)
            QMessageBox.information(self, "已保存", "EXIF 已写入文件。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

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
                "该图片未包含 EXIF 信息或格式暂不支持。\n支持格式：JPEG、WebP、TIFF（piexif）；各家相机 RAW（CR2/NEF/ARW/DNG 等，可选 exifread）；其他格式会尝试用 Pillow 读取。",
            )
        else:
            rows = apply_tag_priority(rows, load_tag_priority_from_settings())
        self.exif_table.set_exif(rows)


def main():
    app = QApplication(sys.argv)
    about_info = load_about_info_from_settings()
    if hasattr(app, "setApplicationName"):
        app.setApplicationName(about_info.get("app_name", "SuperEXIF"))
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(about_info.get("app_name", "SuperEXIF"))
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
