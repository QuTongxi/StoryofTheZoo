# 动物园 · 留园须知

![开场图](data/art/covers/opening.png)

一个周末，两种视角。一位大学生与林夏约好了出游，一位年轻员工准备开始值班。

基于十六椰子《动物园怪谈》的非官方中文视觉小说。包含日常约会、探索、物品操作与逐渐加深的恐怖氛围。人物均为成年人；含心理恐怖、异化与死亡描写。

## 开始游玩

Linux 下运行 **`./run.sh`**。已有本地环境时可以直接运行：

```bash
.venv/bin/python game.py --gui
```

首次从仓库下载，需要 Python 3.11 或更高版本。项目已内置中文字体，无需另行安装。推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync
uv run python game.py --gui
```

没有 uv 时，启动脚本会在项目内建立 `.venv` 并安装 pygame-ce。Windows 提供 `启动游戏.bat`，也可以使用上述 uv 命令。当前实际运行验证的平台为 Linux。

## 怎样玩

标题界面提供 **新游戏、载入存档、设置、退出游戏**。点击“新游戏”后选择故事：首次只能开始游客线；完成游客线的海洋馆篇章后，员工线才会解锁。未解锁时点击员工线只显示提示。两条故事独立开始，选择可以改变经历，也可以决定什么时候结束这一天。

- 左键、空格或回车：显示完整文字，再次按下继续。
- 数字键：选择对应行动；也可以点击选项。
- **B：背包**。查看物品与说明，必要时主动使用；仅拥有物品不代表已经使用。
- **R：守则**。抵达告示所在位置后整份收录，可以反复阅读、添加书签。
- **H / 右键：回顾**；**Backspace：回退**。
- **Tab：赏图**。隐藏文字框查看完整画面；再次按键或点击恢复，不推进剧情。
- **S / L：存档 / 读档**；**F5 / F9：快速存读**。
- **Esc：设定**。可以调整音乐音量、关闭说话提示音，查看剧情图、成就、资料馆和画廊。

阅读、打开背包和查看守则不消耗游戏中的时间。只有推进剧情或选择明确的行动，才会推动事件。普通告示自动收录；路边的纸张需要自己决定是否走近。

剧情会自动保存当前位置，并在章节入口、选择和重要节点留下可返回的记录。“载入存档”中可切换故事，恢复自动进度或读取各自的三个手动存档槽。员工线解锁后永久保留，不因重玩、回退或读取较早进度而取消。各故事的成就、已读文档与结局画面跨周目保存在本地；资料馆的内容不会自动变成当前角色知道的事情。

## AI / 命令行入口

GUI 与 CLI 使用相同的剧情、物品和判定。普通场景显示背景与左侧立绘，事件插画和结局 CG 不叠加立绘。CLI 输出 JSON，同时导出相同构图的画面。

```bash
uv run python game.py --cli
uv run python game.py --cli --select-story visitor
uv run python game.py --cli --continue
uv run python game.py --cli --choose-index 1
uv run python game.py --cli --inventory
uv run python game.py --cli --rules
uv run python game.py --cli --flowchart
uv run python game.py --cli --collection
```

`--stories` 查看故事及解锁状态，`--new` 返回故事选择，解锁后用 `--select-story employee` 开始员工线。`--choose-index` 从 1 开始；物品操作使用 `--use ITEM_ID`。GUI 默认存档在 `saves/gui/`，CLI 默认在 `saves/cli/`，解锁记录也随此目录保存；可以用各入口的目录参数指定同一目录或创建独立会话。每条故事使用独立子目录，手动存档互不覆盖。批量操作、接口和开发说明见 [剧情编写接口](docs/剧情编写.md)。开发资料包含剧情信息，首次游玩建议暂不打开。

## 内容与开发

- 互相照应的两条路线，23 个结局。
- 111 张美术素材：38 张背景、20 张人物与差分、15 张事件插画、23 张结局 CG、12 张物品图和 3 张封面。
- 完整规则册、主动探索、背包变化、35 项成就与回忆画廊。
- 本地运行，无账号、联网游玩或模型 API 依赖。

```bash
uv sync --dev
uv run python tools/build_story.py
uv run python tools/check_routes.py
uv run python tools/check_cli.py
uv run pytest -q
uv run python game.py --gui --check
```

`data/visitor.json`、`data/employee.json` 是两份独立剧情，共用 `data/logic.py`；`data/stories.json` 记录故事选择与解锁条件。每个 action 独占一行，函数参数及规则正文在该行内保留。`story/` 保存创作稿，`tools/build_story.py` 将正文和分支控制编译到游戏接口。`reference/` 用于资料，不用于记录启动方式。视频保留在本地 `videos/`，不会提交到 Git。

## 署名与使用

原作：**十六椰子**。机制参考：**狼蛹**的解析；解析中的推测及本作改编不等于原作结论。完整音乐、音效、图像来源与使用说明见 [CREDITS.md](CREDITS.md)。

这是非商业同人项目，请勿用于商业用途。原作及第三方素材的权利归各自权利人；仓库公开不代表获得原作或视频素材的通用再授权。独立音乐和音效仍适用各自的 Creative Commons 授权。
