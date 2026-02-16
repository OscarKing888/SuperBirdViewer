# SuperEXIF - 图片 EXIF 查看器/编辑器

* 将图片拖入窗口即可查看全部 EXIF 信息，并支持直接双击可编辑字段值。
* 支持自定义显示顺序，支持自定义标签名称。
* 支持中文和英文标签名称。
* JPEG/WebP/TIFF 写入走 `piexif`；RAW（如 ARW/CR2/NEF/DNG）写入走项目内置 `exiftools_mac` / `exiftools_win`。
* `文件信息-标题` 与 `文件信息-描述` 支持直接双击编辑并写回元数据。
* 额外增加了超焦距计算，公式为 H = f^2 / (N * c) + f，其中 f=焦距(mm), N=光圈值, c=弥散圆(mm)。
* 额外增加了非EXIF的标题和描述信息显示。
* 主界面（中英文）
[![主界面](./image/manual/MainCH.png)](./image/manual/MainCH.png)
[![主界面](./image/manual/MainEng.png)](./image/manual/MainEng.png)
* 自定义显示顺序
[![自定义显示顺序](./image/manual/CustomEdit.png)](./image/manual/CustomEdit.png)
* 自定义隐藏标签
[![自定义隐藏标签](./image/manual/CustomEditHiddenTag.png)](./image/manual/CustomEditHiddenTag.png)

# 关于作者
[![关于作者](./image/manual/osk.jpg)](./image/manual/osk.jpg)

# 友情链接：慧眼选鸟
小红书 @詹姆斯摄影 https://xhslink.com/m/3UWGeUJqUi0
开源库：https://github.com/jamesphotography/SuperPicky
[![友情链接：慧眼选鸟](https://raw.githubusercontent.com/jamesphotography/SuperPicky/master/img/icon.png)](https://github.com/jamesphotography/SuperPicky)