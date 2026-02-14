# SuperEXIF - 图片 EXIF 查看器

将图片拖入窗口即可查看全部 EXIF 信息。界面使用 **PyQt6**（兼容 PyQt5），EXIF 解析使用 **piexif**（支持 JPEG/WebP/TIFF），并辅以 **Pillow** 作为部分格式的补充。

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

## 依赖说明

| 依赖 | 用途 |
|------|------|
| PyQt6 | 图形界面（可改用 PyQt5） |
| piexif | 高性能 EXIF 读取，支持 JPEG/WebP/TIFF |
| Pillow | 补充读取部分格式的 EXIF（如 PNG 等） |
