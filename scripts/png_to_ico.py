#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 image/superexif.png 生成图标文件：
- .ico：Windows 图标（多分辨率）
- .icns：macOS 原生图标（仅在本机为 macOS 且存在 sips/iconutil 时生成）
"""

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT_DIR / "image"
PNG_PATH = IMAGE_DIR / "superexif.png"
ICO_PATH = IMAGE_DIR / "superexif.ico"
ICNS_PATH = IMAGE_DIR / "superexif.icns"

# Windows ICO 常用多分辨率
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# macOS iconset 所需尺寸：(基准, 可选 @2x)
ICNS_SIZES = [(16, 32), (32, 64), (128, 256), (256, 512), (512, 1024)]


def save_ico() -> None:
    img = Image.open(PNG_PATH).convert("RGBA")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    img.save(ICO_PATH, format="ICO", sizes=ICO_SIZES)
    print(f"已生成: {ICO_PATH}")


def save_icns() -> bool:
    """在 macOS 下用 sips + iconutil 从 PNG 生成 .icns。"""
    if sys.platform != "darwin":
        print("[跳过] .icns 仅在 macOS 下生成")
        return False
    if not shutil.which("iconutil") or not shutil.which("sips"):
        print("[跳过] 未找到 iconutil 或 sips，无法生成 .icns")
        return False
    iconset = IMAGE_DIR / "superexif.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True, exist_ok=True)
    try:
        for base, double in ICNS_SIZES:
            for size, suffix in [(base, ""), (double, "@2x")]:
                out = iconset / f"icon_{base}x{base}{suffix}.png"
                subprocess.run(
                    ["sips", "-z", str(size), str(size), str(PNG_PATH), "--out", str(out)],
                    check=True,
                    capture_output=True,
                )
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS_PATH)],
            check=True,
            capture_output=True,
        )
        print(f"已生成: {ICNS_PATH}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[失败] 生成 .icns 时出错: {e}")
        return False
    finally:
        if iconset.exists():
            shutil.rmtree(iconset)


def main() -> int:
    if not PNG_PATH.is_file():
        print(f"错误: 找不到 {PNG_PATH}")
        return 1
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    save_ico()
    save_icns()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
