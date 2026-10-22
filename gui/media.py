"""Cached images and independent music, voice and effect channels."""
from __future__ import annotations

import logging
from pathlib import Path
import pygame
from core.story import Story, StoryError

log = logging.getLogger(__name__)


class Media:
    def __init__(self, story: Story, *, muted=False):
        self.story = story
        self.images = {}
        self.sounds = {}
        self.music = None
        self.enabled = False
        self.typing_enabled = True
        self.volume = .25
        self.last_tick = 0
        if not muted:
            try:
                pygame.mixer.init()
                pygame.mixer.set_num_channels(8)
                self.enabled = True
            except pygame.error as exc:
                log.warning("音频设备不可用，继续静音运行：%s", exc)

    def image(self, asset):
        if asset not in self.images:
            try:
                self.images[asset] = pygame.image.load(str(self.story.asset(asset))).convert_alpha()
            except (pygame.error, OSError) as exc:
                raise StoryError(f"无法解码图片 {asset}：{exc}") from exc
        return self.images[asset]

    def sound(self, asset):
        if asset not in self.sounds:
            self.sounds[asset] = pygame.mixer.Sound(str(self.story.asset(asset)))
        return self.sounds[asset]

    def sync(self, state, page, *, transient=True, restart=False):
        if not self.enabled:
            return
        try:
            pygame.mixer.Channel(0).stop()
            pygame.mixer.Channel(1).stop()
            desired = None if state["ended"] else state["music"]
            if restart or desired != self.music:
                pygame.mixer.music.stop()
                if desired:
                    pygame.mixer.music.load(str(self.story.asset(desired)))
                    pygame.mixer.music.set_volume(self.volume)
                    pygame.mixer.music.play(-1)
                self.music = desired
            if transient and not state["ended"]:
                if page.get("voice"):
                    pygame.mixer.Channel(0).play(self.sound(page["voice"]))
                if page.get("sound"):
                    pygame.mixer.Channel(1).set_volume(.55)
                    pygame.mixer.Channel(1).play(self.sound(page["sound"]))
        except (pygame.error, OSError) as exc:
            raise StoryError(f"音频素材播放失败：{exc}") from exc

    def tick(self, speaker):
        if not self.enabled or not self.typing_enabled or not speaker:
            return
        now=pygame.time.get_ticks()
        if now-self.last_tick<75 or not (self.story.root/'audio/typing.wav').exists():
            return
        self.last_tick=now
        pygame.mixer.Channel(2).set_volume(.09)
        pygame.mixer.Channel(2).play(self.sound('audio/typing.wav'))

    def click(self):
        if self.enabled and (self.story.root/'audio/ui_click.ogg').exists():
            pygame.mixer.Channel(3).set_volume(.10)
            pygame.mixer.Channel(3).play(self.sound('audio/ui_click.ogg'))

    def confirm(self):
        if self.enabled and (self.story.root/'audio/ui_confirm.ogg').exists():
            pygame.mixer.Channel(4).set_volume(.12)
            pygame.mixer.Channel(4).play(self.sound('audio/ui_confirm.ogg'))

    def cycle_volume(self):
        values=(0,.12,.25,.4)
        self.volume=values[(values.index(self.volume)+1)%len(values)]
        if self.enabled:
            pygame.mixer.music.set_volume(self.volume)

    def replay_voice(self, page):
        if self.enabled and page.get("voice"):
            try:
                pygame.mixer.Channel(0).play(self.sound(page["voice"]))
            except (pygame.error, OSError) as exc:
                raise StoryError(f"语音播放失败：{exc}") from exc


def find_font(root: Path, configured: str | None, role='body'):
    if configured:
        path = (root / configured).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise StoryError(f"字体文件不存在或路径越界：{configured}")
        return str(path)
    bundled = {'body': 'LXGWWenKai-Regular.ttf', 'ui': 'GlowSansSC-Normal-Regular.otf',
               'title': 'SourceHanSerifSC-Medium.otf'}
    if role not in bundled:
        raise StoryError(f'未知字体用途：{role}')
    path = root / 'fonts' / bundled[role]
    if path.is_file():
        return str(path)
    # Custom stories without bundled fonts can still use installed CJK fonts.
    for family in ("notosanscjksc", "notosanscjk", "microsoftyahei", "pingfangsc",
                   "wenquanyizenhei", "droidsansfallback"):
        path = pygame.font.match_font(family)
        if path:
            return path
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                 "C:/Windows/Fonts/msyh.ttc", "/System/Library/Fonts/PingFang.ttc"):
        if Path(path).is_file():
            return path
    raise StoryError("未找到中文字体，请把字体放进 data/fonts 并通过 --font 指定")
