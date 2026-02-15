# SuperEXIF - 图片 EXIF 查看器/编辑器

将图片拖入窗口即可查看全部 EXIF 信息，并支持直接编辑可写字段。界面使用 **PyQt6**（兼容 PyQt5），EXIF 解析使用 **piexif**（支持 JPEG/WebP/TIFF），并辅以 **Pillow** 作为部分格式的补充。

## 安装

```bash
cd /Volumes/USB_2T/SuperEXIF
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 使用

- **拖拽**：将图片文件拖入窗口左侧区域。
- **点击**：点击左侧区域，通过文件选择对话框选择图片。
- 支持格式：JPEG、PNG、WebP、TIFF 等（EXIF 完整解析以 piexif 支持的 JPEG/WebP/TIFF 为准）。
- 菜单栏新增 **帮助 -> 关于...**，软件信息由 `EXIF.cfg` 的 `about` 字段控制。

## 关于信息配置

编辑 `EXIF.cfg` 中的 `about` 对象即可修改“关于”弹窗：

```json
"about": {
  "app_name": "SuperEXIF",
  "version": "1.0.0",
  "tagline": "图片 EXIF 查看与编辑工具",
  "description": "支持拖拽查看、过滤检索和直接编辑常见 EXIF 字段。",
  "author": "SuperEXIF Team",
  "website": "https://example.com/superexif",
  "license": "MIT",
  "copyright": "Copyright (c) 2026 SuperEXIF"
}
```

## 图标生成

```bash
python scripts/generate_icon.py --icns
```

会生成：

- `image/superexif.png`
- `image/superexif.ico`
- `image/superexif.icns`（仅 macOS 且有 `sips/iconutil` 时）

## PyInstaller 打包

macOS:

```bash
bash scripts/build_mac.sh
```

Windows:

```bat
scripts\\build_win.bat
```

输出目录默认在 `dist/`。

## 依赖说明

| 依赖 | 用途 |
|------|------|
| PyQt6 | 图形界面（可改用 PyQt5） |
| piexif | 高性能 EXIF 读取，支持 JPEG/WebP/TIFF |
| Pillow | 补充读取部分格式的 EXIF（如 PNG 等） |
