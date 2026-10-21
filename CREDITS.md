# 署名与素材来源

## 原作与参考资料

- 《动物园怪谈》：十六椰子。规则文本来自用户提供的整理材料，正文保存在 `reference/动物园怪谈正文.md`。标注的隐藏、划去、加重笔迹等信息保留在游戏规则册中。
- 作者问答：用户提供的作者 Q&A，供创作核对；本地保存，不随公开仓库提交。
- 解析参考：bilibili UP 主 **狼蛹**，《动物园怪谈解析重置版》系列。用户说明已取得对解析进行非商业利用的授权；本项目不把该说明当作向公众再授权视频或解析全文。原视频和解析合订稿仅保留在本地。具体视频清单见 `videos/README.md`；未取得的 BV 号不作臆测。
- 游戏新增人物、桥段、危险演出与结局属于本项目改编，不是原作新增规则。尤其换岗和结局中的任命是明确的改编安排，不代表原文确认了通用的安全转换机制。

## 插画

本项目使用 **OpenAI imagegen** 生成并修订的原创二次元插画。人物母版确定后，以母版作图像参考生成服装、表情及事件画面；没有使用动画或商业游戏截图作为素材。

最终图片在 `data/art/`。`data/art/manifest.json` 记录文件、提示词与使用的角色参考。生成时间：2026-10-22。图片不冒称人工手绘。

## 音乐

以下五首曲目均来自作曲者 **Kevin MacLeod / Incompetech** 官网，按 **Creative Commons Attribution 4.0** 使用。保留原始音频内容，仅重命名用于场景配置；循环和音量变化由播放器实时完成。

| 游戏文件 | 曲目及作者页面 |
| --- | --- |
| `data/audio/day.mp3` | [Carefree — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400037) |
| `data/audio/romance.mp3` | [Evening Fall (Harp) — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100236) |
| `data/audio/unease.mp3` | [Lightless Dawn — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100655) |
| `data/audio/night.mp3` | [Long note One — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100418) |
| `data/audio/danger.mp3` | [Unseen Horrors — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400043) |

Music by Kevin MacLeod (incompetech.com).
Licensed under Creative Commons: By Attribution 4.0 License.
[License terms](https://creativecommons.org/licenses/by/4.0/).
[Author's licensing page](https://incompetech.com/music/royalty-free/licenses/).
[Author's track metadata](https://incompetech.com/music/royalty-free/pieces.json).

## 音效

- `ui_click.ogg`、`ui_confirm.ogg`：**Kenney**，[Interface Sounds](https://kenney.nl/assets/interface-sounds)，CC0。未改音频内容，仅重命名。原授权文本见 `data/audio/KENNEY_LICENSE.txt`。
- 其余游戏 WAV：本项目原创的程序合成音效，包括翻纸、敲门、脚步、水声、呼吸、低频环境声和非语言异常声。生成源在 `tools/build_audio.py`。这些并非真人配音或现场动物录音。
- 角色对白没有真人或 AI 配音；低音量的短音作为逐字提示，可在设定中关闭。
- 测试夹具中的 `bell.wav` 仅用于引擎测试，不是正式故事音效。

## 软件与使用范围

运行依赖 pygame-ce；第三方软件遵循自身授权。中文字体优先使用运行系统已安装字体，项目未打包第三方商业字体。

本作定位为非商业同人项目，请勿商用。原作、参考视频、音乐、音效及软件的权利与授权各自独立；本说明不将第三方作品改为项目独占，也不限制 CC BY / CC0 素材原有的合法使用权。
