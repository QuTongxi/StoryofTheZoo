# 游戏字体

游戏直接读取此目录的字体，无需向操作系统安装。字体文件保持上游原样，未修改或裁剪。

| 文件 | 用途 | 上游 |
| --- | --- | --- |
| `LXGWWenKai-Regular.ttf` | 对白、心理描写及弹窗正文，28 px | [霞鹜文楷](https://github.com/lxgw/LxgwWenKai) |
| `GlowSansSC-Normal-Regular.otf` | 菜单、姓名及界面文字 | [未来荧黑](https://github.com/welai/glow-sans) |
| `SourceHanSerifSC-Medium.otf` | 游戏、章节及结局标题 | [思源宋体](https://github.com/adobe-fonts/source-han-serif) |

三个字体均采用 SIL Open Font License 1.1；分发游戏时请保留对应的许可证文件及版权信息。`manifest.json` 记录版本、原始下载地址与校验值。

如使用 `--font fonts/某字体.ttf`，该参数会覆盖全部字体用途，路径相对故事 JSON 所在目录。未附带本目录的自定义故事仍可使用系统中文字体。
