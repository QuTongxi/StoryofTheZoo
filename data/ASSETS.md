# 游戏素材

正式美术素材全部位于 `art/`：`backgrounds/` 为 38 张环境背景；`characters/` 为 20 张人物及差分；`illustrations/` 为 15 张事件插画；`endings/` 为 23 张结局 CG；`covers/` 为 3 张封面；`items/` 为 12 张物品图。来源、最终提示词、参考母版及 SHA-256 见 [manifest.json](art/manifest.json)。

普通场景采用背景＋左侧立绘。背景不嵌入主角团或主要员工；事件与结局 CG 用独立插画模式，禁止叠立绘。逐图核对及剧情触发位置见 [画面分层核对](../docs/画面分层核对.md)。

图像通过OpenAI imagegen生成和编辑，以林夏、苏晚晴、游客男主母版约束人物一致性；运行时由pygame缩放与组合。图片中的告示不承载可阅读规则，完整规则由程序显示。旧演示背景和占位立绘已移除。

音乐与音效在`audio/`，署名和授权见[CREDITS.md](../CREDITS.md)。音乐使用Kevin MacLeod的五首CC BY 4.0作品，界面提示使用Kenney CC0音效，其余WAV由`tools/build_audio.py`合成。字体读取本机已安装中文字体。

人物、普通场景和异常场景均为二次元风格。坏结局画面是具体改编演出，不将“它”确定为具有固定实体外形的生物。
