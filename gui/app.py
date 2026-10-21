"""Human GUI: input, drawing, audio, and local save slots."""
from __future__ import annotations
import argparse
import math
import os
from pathlib import Path
import sys
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame
from core import Engine, Story, StoryError
from core.session import Session
from .style import PAPER, INK, GREEN, MUTED as FADED, LINE, RED, ACCENT, icon, ICONS, backdrop
from .media import Media, find_font
from .storage import SaveStore
from .ui import WIDTH, HEIGHT, Button, label, fitted_label, text_pages, wrap_text

ROOT = Path(__file__).resolve().parents[1]


class App:
    def __init__(self, story, save_dir, *, muted=False, font=None, text_speed=36):
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(story.name)
        self.story = story
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        font_path = find_font(story.root, font)
        self.body_font = pygame.font.Font(font_path, 25)
        self.display_font = pygame.font.Font(font_path, 32)
        self.small_font = pygame.font.Font(font_path, 19)
        self.title_font = pygame.font.Font(font_path, 34)
        self.micro_font = pygame.font.Font(font_path, 14)
        self.session = Session(story, Path(save_dir) / "session.json")
        self.engine = self.session.engine
        self.scene = "title"
        self.graph_selected = None
        self.graph_pan = [0., 0.]
        self.graph_zoom = 1.
        self.graph_fit = True
        self.graph_drag = None
        self.panel_page = 0
        self.media = Media(story, muted=muted)
        self.store = SaveStore(save_dir)
        self.text_speed = text_speed
        self.running = True
        self.overlay = None
        self.scroll = 0
        self.history_max_scroll = 0
        self.rule_active_book = None
        self.rule_scroll = 0
        self.rule_max_scroll = 0
        self.rule_tab_offset = 0
        self.inventory_selected = None
        self.inventory_page = 0
        self.inventory_scroll = 0
        self.inventory_max_scroll = 0
        self.notice = ""
        self.notice_time = 0.0
        self.buttons = []
        self.scaled_images = {}
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self.chunks = [[]]
        self.chunk_index = 0
        self.revealed = self.effect_time = 0.0
        self.effect = None
        self.animations = []
        self.popup_index = 0
        self.popup_chunks = []
        self.gallery_selected = None
        if (story.root / 'audio/unease.mp3').exists():
            self.media.sync({'ended': False, 'music': 'audio/unease.mp3'}, {}, transient=False)

    def sync_page(self, *, transient=True, restored=False):
        self.engine = self.session.engine
        self.scene = "chapter" if self.engine.state["chapter_pending"] else "game"
        from .popup_ui import prepare
        prepare(self)
        if self.engine.popup:
            self.overlay = None
        self.chunks = text_pages(self.engine.page.get("text", ""), self.body_font, 1120)
        self.chunk_index = 0
        self.revealed = 0.0
        self.effect = self.engine.page.get("effect") if transient and not self.engine.state["ended"] else None
        self.effect_time = 0.0
        self.animations = self.engine.page.get('animations', []) if transient else []
        if restored:
            # Saves resume at the current page, with readable text and no replayed transient effects.
            self.revealed = float(self.chunk_length)
        self.media.sync(self.engine.state, self.engine.page, transient=transient, restart=restored)
        if transient and self.engine.page.get('rules'):
            names = '、'.join(dict.fromkeys(update['title'] for update in self.engine.page['rules']))
            self.announce(f'守则已更新：{names} · 按 R 查看')

        if transient and self.engine.page.get('new_achievements'):
            self.media.confirm()
            self.announce('成就达成：' + '、'.join(self.engine.page['new_achievements']))

    @property
    def chunk_length(self):
        return sum(len(line) for line in self.chunks[self.chunk_index])

    @property
    def complete(self):
        return self.revealed >= self.chunk_length

    @property
    def all_text_read(self):
        return self.complete and self.chunk_index == len(self.chunks) - 1

    @property
    def blocked(self):
        return bool(self.effect and self.effect.get("blocking", False)
                    and self.effect_time < self.effect.get("duration", 0.6))

    def announce(self, text):
        self.notice, self.notice_time = text, 4.0

    def advance(self):
        if self.scene == 'game' and self.engine.popup:
            from .popup_ui import confirm
            confirm(self)
            return
        if self.scene == "title":
            return
        if self.scene == "chapter":
            self.session.apply("advance")
            self.sync_page()
            return
        if self.blocked:
            return
        if not self.complete:
            self.revealed = float(self.chunk_length)
        elif self.chunk_index < len(self.chunks) - 1:
            self.chunk_index += 1
            self.revealed = 0.0
        elif self.session.apply("advance"):
            self.sync_page()

    def choose(self, index):
        if self.blocked or not self.all_text_read or self.engine.state["ended"]:
            return
        self.session.apply("choose", index)
        self.sync_page()

    def action(self, name, value=None):
        try:
            if name not in ('advance', 'popup_continue'):
                self.media.click()
            if name == 'popup_continue':
                if self.engine and self.engine.popup:
                    self.advance()
            elif name in ('new_game', 'confirm_restart'):
                self.session.start()
                self.overlay = None
                self.sync_page()
            elif name == 'continue_game':
                if self.session.engine:
                    self.overlay = None
                    self.sync_page(transient=False, restored=True)
            elif name == 'to_title':
                self.scene, self.overlay = 'title', None
                self.media.sync({'music': None, 'ended': False}, {}, transient=False)
            elif name == 'quit':
                self.running = False
            elif name == 'chapter_continue':
                self.advance()
            elif name in ('flowchart', 'achievements', 'checkpoints', 'gallery', 'credits'):
                self.overlay, self.panel_page = name, 0
                self.graph_fit = True
                self.graph_drag = None
            elif name == 'gallery_image':
                self.gallery_selected = value
                self.overlay = 'gallery_image'
            elif name == 'archive':
                self.overlay = 'archive'
                self.rule_active_book = None
                self.rule_scroll = self.rule_tab_offset = 0
            elif name == 'typing_sound':
                self.media.typing_enabled = not self.media.typing_enabled
            elif name == 'music_volume':
                self.media.cycle_volume()
            elif name == 'panel_page':
                self.panel_page += value
            elif name == 'graph_fit':
                self.graph_fit = True
            elif name == 'graph_zoom':
                from .tree_ui import zoom
                zoom(self, value)
            elif name == 'select_point':
                self.graph_selected = value
            elif name == 'load_point':
                self.session.load(value)
                self.overlay = None
                self.sync_page(transient=False, restored=True)
            elif name == "advance":
                self.advance()
            elif name == "choose":
                self.choose(value)
            elif name in ("history", "save", "load", 'help'):
                self.overlay = name
                self.scroll = 0
            elif name in ('settings', 'inventory'):
                self.overlay = None if self.overlay == name else name
            elif name == 'inspect_item':
                self.inventory_selected, self.inventory_scroll = value, 0
            elif name == 'inventory_page':
                self.inventory_page += value
            elif name == 'use_item':
                self.session.apply('use_item', value)
                self.overlay = None
                self.sync_page()
            elif name == 'rules':
                self.overlay = None if self.overlay == 'rules' else 'rules'
            elif name == 'rule_book':
                self.rule_active_book, self.rule_scroll = value, 0
            elif name == 'rule_tabs':
                self.rule_tab_offset += value
            elif name == 'bookmark':
                self.session.apply('toggle_bookmark', value)
            elif name == "close":
                self.overlay = None
            elif name == "save_slot":
                self.store.save(self.engine, value)
                self.overlay = None
                self.announce(f"已保存到存档 {value}")
            elif name == "load_slot":
                candidate = Engine(self.story, initialize=False)
                self.store.load(candidate, value)
                self.session.import_snapshot(candidate.export())
                self.overlay = None
                self.sync_page(transient=False, restored=True)
                self.announce(f"已读取存档 {value}")
            elif name == "rollback":
                if self.session.apply('rollback'):
                    self.overlay = None
                    self.sync_page(transient=False, restored=True)
                else:
                    self.announce("已经是故事开头")
            elif name == "voice":
                self.media.replay_voice(self.engine.page)
                self.overlay = None
            elif name == "restart":
                self.overlay = "restart"
        except (StoryError, OSError) as exc:
            self.announce(str(exc))

    def logical_position(self, pos):
        if not self.viewport.collidepoint(pos):
            return (-1, -1)
        return ((pos[0] - self.viewport.x) * WIDTH / self.viewport.width,
                (pos[1] - self.viewport.y) * HEIGHT / self.viewport.height)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif self.scene == 'game' and self.engine and self.engine.popup:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.action('popup_continue')
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                from .popup_ui import PANEL
                if PANEL.collidepoint(self.logical_position(event.pos)):
                    self.action('popup_continue')
            return
        elif event.type == pygame.KEYDOWN:
            if self.scene == 'title':
                if event.key == pygame.K_ESCAPE:
                    self.overlay = None if self.overlay else 'settings'
                return
            if self.scene == 'chapter' and not self.overlay and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.action('chapter_continue')
                return
            if event.key == pygame.K_ESCAPE:
                self.overlay = None if self.overlay else 'settings'
            elif event.key == pygame.K_r:
                self.action('rules')
            elif event.key == pygame.K_b:
                self.action('inventory')
            elif self.overlay:
                if self.overlay == "history":
                    if event.key in (pygame.K_UP, pygame.K_PAGEUP):
                        self.scroll = max(0, self.scroll - 180)
                    elif event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                        self.scroll = min(self.history_max_scroll, self.scroll + 180)
                elif self.overlay in ('rules', 'archive'):
                    if event.key in (pygame.K_UP, pygame.K_PAGEUP):
                        self.rule_scroll = max(0, self.rule_scroll - 180)
                    elif event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                        self.rule_scroll = min(self.rule_max_scroll, self.rule_scroll + 180)
                elif self.overlay == 'inventory':
                    if event.key in (pygame.K_UP, pygame.K_PAGEUP):
                        self.inventory_scroll = max(0, self.inventory_scroll - 120)
                    elif event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                        self.inventory_scroll = min(self.inventory_max_scroll, self.inventory_scroll + 120)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.action("advance")
            elif event.key == pygame.K_F5:
                self.action("save_slot", 1)
            elif event.key == pygame.K_F9:
                self.action("load_slot", 1)
            elif event.key == pygame.K_BACKSPACE:
                self.action("rollback")
            elif event.key in (pygame.K_h, pygame.K_s, pygame.K_l, pygame.K_v):
                self.action({pygame.K_h: "history", pygame.K_s: "save", pygame.K_l: "load", pygame.K_v: "voice"}[event.key])
            elif pygame.K_1 <= event.key <= pygame.K_6:
                index = event.key - pygame.K_1
                if index < len(self.engine.choices):
                    self.action("choose", index)
        elif event.type == pygame.MOUSEWHEEL and self.overlay == 'flowchart':
            from .tree_ui import zoom
            modifiers = pygame.key.get_mods()
            if modifiers & pygame.KMOD_CTRL:
                zoom(self, 1.15 ** event.y)
            elif modifiers & pygame.KMOD_SHIFT:
                self.graph_pan[0] += event.y * 65
            else:
                self.graph_pan[1] += event.y * 65
                self.graph_pan[0] += event.x * 65
        elif event.type == pygame.MOUSEWHEEL and self.overlay == "history":
            self.scroll = max(0, min(self.history_max_scroll, self.scroll - event.y * 65))
        elif event.type == pygame.MOUSEWHEEL and self.overlay in ('rules', 'archive'):
            self.rule_scroll = max(0, min(self.rule_max_scroll, self.rule_scroll - event.y * 65))
        elif event.type == pygame.MOUSEWHEEL and self.overlay == 'inventory':
            self.inventory_scroll = max(0, min(self.inventory_max_scroll, self.inventory_scroll - event.y * 60))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.graph_drag = None
        elif event.type == pygame.MOUSEMOTION and self.overlay == 'flowchart' and self.graph_drag is not None:
            pos = self.logical_position(event.pos)
            self.graph_pan[0] += pos[0] - self.graph_drag[0]
            self.graph_pan[1] += pos[1] - self.graph_drag[1]
            self.graph_drag = pos
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.overlay = None if self.overlay else ("settings" if self.scene == "title" else "history")
            elif event.button == 1:
                pos = self.logical_position(event.pos)
                for button in self.buttons:
                    if button.rect.collidepoint(pos):
                        self.action(button.action, button.value)
                        break
                else:
                    if self.overlay == 'flowchart':
                        from .tree_ui import VIEW
                        if VIEW.collidepoint(pos):
                            self.graph_drag = pos
                    if not self.overlay and pos != (-1, -1):
                        self.action("advance")

    def update(self, seconds):
        if self.scene == "game" and not self.overlay and not self.engine.popup:
            self.effect_time += seconds
            if not self.blocked:
                old_revealed = int(self.revealed)
                self.revealed = min(float(self.chunk_length), self.revealed + seconds * self.text_speed)
                if int(self.revealed) > old_revealed:
                    self.media.tick(self.engine.page.get('speaker'))
        self.notice_time = max(0, self.notice_time - seconds)

    def scaled(self, path, box, *, cover=False):
        key = (path, box, cover)
        if key not in self.scaled_images:
            original = self.media.image(path)
            ratios = box[0] / original.get_width(), box[1] / original.get_height()
            ratio = max(ratios) if cover else min(ratios)
            size = tuple(max(1, round(n * ratio)) for n in original.get_size())
            self.scaled_images[key] = pygame.transform.smoothscale(original, size)
        return self.scaled_images[key]

    def add_button(self, rect, text, action, value=None):
        button = Button(pygame.Rect(rect), text, action, value)
        self.buttons.append(button)
        hover = button.rect.collidepoint(self.logical_position(pygame.mouse.get_pos()))
        choice = action == 'choose'
        pygame.draw.rect(self.canvas, GREEN if hover else PAPER, button.rect)
        pygame.draw.rect(self.canvas, GREEN if not hover else PAPER, button.rect, 1)
        color = PAPER if hover else INK
        if choice:
            number = pygame.Rect(button.rect.x + 12, button.rect.y + 12, 30, button.rect.height - 24)
            pygame.draw.rect(self.canvas, PAPER if hover else GREEN, number)
            label(self.canvas, self.small_font, f'{value + 1:02}', (number.x + 3, number.y - 1), GREEN if hover else PAPER)
            fitted_label(self.canvas, self.small_font, text, button.rect.inflate(-112, -10).move(16, 0), color)
            label(self.canvas, self.small_font, '→', (button.rect.right - 34, button.rect.centery - 14), color)
        else:
            glyph = ICONS.get(action)
            if action == 'inspect_item':
                glyph = 'map' if 'map' in str(value).lower() else 'bag'
            if glyph:
                icon(self.canvas, glyph, (button.rect.x + 12, button.rect.centery - 10, 20, 20), color)
                area = pygame.Rect(button.rect.x + 42, button.rect.y + 4, button.rect.width - 50, button.rect.height - 8)
            else:
                area = button.rect.inflate(-22, -8)
            fitted_label(self.canvas, self.small_font, text, area, color)

    def animated(self, surface, kind, slot=None):
        for animation in self.animations:
            if animation['property'] != kind or (kind == 'character' and animation['slot'] != slot):
                continue
            progress = min(1.0, self.effect_time / animation['duration'])
            if progress >= 1:
                continue
            if animation['type'] == 'fade in':
                surface = surface.copy()
                surface.set_alpha(round(255 * progress))
            else:
                scale = .9 + .1 * progress
                surface = pygame.transform.smoothscale(surface, (round(surface.get_width() * scale), round(surface.get_height() * scale)))
        return surface

    def draw_body(self, top, default_color):
        source = self.engine.page.get('text', '')
        spans = self.engine.page.get('text_spans', [])
        cursor = 0
        remaining = int(self.revealed)
        for chunk_index, lines in enumerate(self.chunks):
            for line_index, line in enumerate(lines):
                start = source.find(line, cursor)
                start = cursor if start < 0 else start
                cursor = start + len(line)
                if source[cursor:cursor + 1] == '\n':
                    cursor += 1
                if chunk_index != self.chunk_index:
                    continue
                visible = line[:max(0, remaining)]
                remaining -= len(line)
                if not spans:
                    label(self.canvas, self.body_font, visible, (76, top + line_index * 38), default_color)
                    continue
                x = 76
                for i, char in enumerate(visible):
                    color = default_color
                    for span in spans:
                        if span['start'] <= start + i < span['end']:
                            color = span['color']
                    label(self.canvas, self.body_font, char, (x, top + line_index * 38), color)
                    x += self.body_font.size(char)[0]

    def draw_scene(self):
        backdrop(self.canvas, self.story.chapters.index(self.engine.chapter))
        background = self.engine.state["background"]
        if background:
            surface = self.scaled(background, (WIDTH, HEIGHT), cover=True)
            surface = self.animated(surface, 'background')
            self.canvas.blit(surface, ((WIDTH - surface.get_width()) // 2, (HEIGHT - surface.get_height()) // 2))
        for slot, path in self.engine.state["characters"].items():
            surface = self.scaled(path, (500, 760))
            surface = self.animated(surface, 'character', slot)
            center = {"left": 270, "center": 640, "right": 1010}[slot]
            self.canvas.blit(surface, (center - surface.get_width() // 2, 840 - surface.get_height()))
        if self.effect:
            progress = min(1.0, self.effect_time / self.effect.get("duration", 0.6))
            if progress < 1:
                kind = self.effect["type"]
                if kind == "shake":
                    copy = self.canvas.copy()
                    self.canvas.fill((12, 20, 18))
                    offset = (round(math.sin(self.effect_time * 80) * 12 * (1 - progress)),
                              round(math.cos(self.effect_time * 63) * 7 * (1 - progress)))
                    self.canvas.blit(copy, offset)
                else:
                    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    rgb = (255, 255, 255) if kind == "flash" else (0, 0, 0)
                    overlay.fill((*rgb, round(255 * (1 - progress))))
                    self.canvas.blit(overlay, (0, 0))

    def draw_dialogue(self):
        dark = any(part in (self.engine.state.get('background') or '') for part in ('night','dark','whale','storage','controlroom','confession','endings/B'))
        ink = (224,232,235) if dark else INK
        accent = (140,203,213) if dark else GREEN
        muted = (153,171,179) if dark else FADED
        line = (59,77,86) if dark else LINE
        # Quiet utility strip; controls remain real clickable elements, not baked art.
        pygame.draw.rect(self.canvas, (14,25,32) if dark else GREEN, (0, 0, WIDTH, 66))
        label(self.canvas, self.small_font, '■■ 市 动 物 园', (30, 11), PAPER)
        label(self.canvas, self.micro_font, 'VISITOR HANDBOOK  /  游客留存联', (31, 39), (170, 187, 169))
        for i, (text, action) in enumerate((('设定', 'settings'), ('背包 B', 'inventory'), ('守则 R', 'rules'))):
            self.add_button((900 + i * 114, 15, 104, 35), text, action)
        # A small paper location tab, leaving most of the environment unobstructed.
        for rect in ((32,91,258,83),(40,554,1200,218)):
            if dark:
                panel=pygame.Surface((rect[2],rect[3]),pygame.SRCALPHA)
                panel.fill((12,21,31,228));self.canvas.blit(panel,rect[:2])
                pygame.draw.rect(self.canvas,line,rect,1)
            else:
                self.paper_panel(rect)
        label(self.canvas, self.micro_font, '游 园 记 录    /    FIELD NOTES', (49, 103), muted)
        fitted_label(self.canvas, self.small_font, self.engine.chapter['title'], pygame.Rect(49, 126, 224, 36), accent)
        pygame.draw.rect(self.canvas, accent, (40, 554, 6, 218))
        label(self.canvas, self.small_font, self.engine.page.get('speaker', '') or '游园记录', (76, 569), accent)
        page_number = self.story.node_indexes[self.engine.state['chapter_id']][self.engine.state['page_id']] + 1
        label(self.canvas, self.micro_font, f'RECORD  {page_number:03}  /  {len(self.engine.chapter["contents"]):03}', (1030, 572), muted)
        pygame.draw.line(self.canvas, line, (76, 602), (1203, 602), 1)
        self.draw_body(611, ink)
        if self.engine.state['ended']:
            hint = '本段记录结束 · 可回顾或回退'
        elif self.blocked:
            hint = '场景切换中…'
        elif self.all_text_read and self.engine.choices:
            hint = '请选择接下来的行动' + (' · 或打开背包使用物品' if self.engine.item_uses else '')
        elif self.all_text_read and self.engine.is_decision:
            hint = '打开背包使用物品' + (' · 或点击继续' if self.engine.can_advance else '')
        else:
            hint = '点击 / 空格继续' if self.complete else '点击显示完整文字'
        if len(self.chunks) > 1:
            hint += f'  ·  {self.chunk_index + 1}/{len(self.chunks)}'
        for x in range(76, 1200, 12):
            pygame.draw.line(self.canvas, line, (x, 731), (x + 5, 731))
        label(self.canvas, self.micro_font, hint, (76, 744), muted)
        label(self.canvas, self.micro_font, '请记住，你是人类。', (1060, 744), RED)
        if self.all_text_read and not self.blocked:
            choices = self.engine.choices
            top = 536 - len(choices) * 64
            for i, choice in enumerate(choices):
                self.add_button((374, top + i * 64, 740, 52), choice['text'], 'choose', i)
        if self.engine.state['ended']:
            self.add_button((460, 444, 360, 62), '记录结束 · 重新开始', 'restart')

    def draw_overlay(self):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((9, 24, 19, 192))
        self.canvas.blit(shade, (0, 0))
        self.paper_panel((130, 90, 1020, 620))
        self.buttons = []
        title = {'history': '游 园 记 录', 'save': '存 档 留 存', 'load': '调 阅 记 录',
                 'restart': '重 新 入 园', 'help': '使 用 说 明', 'rules': '规 则 守 则',
                 'settings': '设 定', 'inventory': '随 身 背 包', 'flowchart': '剧 情 图',
                 'achievements': '游 园 成 就', 'checkpoints': '章 节 存 档',
                 'archive': '资 料 馆', 'gallery': '回 忆 画 廊', 'gallery_image': '回 忆 画 廊', 'credits': '制 作 与 素 材'}[self.overlay]
        label(self.canvas, self.micro_font, '■■ 市动物园    /    游客服务处', (175, 109), FADED)
        label(self.canvas, self.display_font, title, (175, 133), GREEN)
        self.add_button((1015, 116, 90, 40), '关闭', 'close')
        pygame.draw.line(self.canvas, GREEN, (175, 180), (1100, 180), 2)
        if self.overlay in ('settings', 'inventory'):
            from .menu_ui import draw_settings, draw_inventory
            (draw_settings if self.overlay == 'settings' else draw_inventory)(self)
        elif self.overlay in ('flowchart', 'achievements', 'checkpoints', 'gallery', 'gallery_image', 'credits'):
            from .screens import draw_progress
            draw_progress(self)
        elif self.overlay in ('rules', 'archive'):
            from .rules_ui import draw_rules
            draw_rules(self)
        elif self.overlay in ('save', 'load'):
            label(self.canvas, self.small_font, '共三份留存记录 · 点击已有存档将覆盖该槽位' if self.overlay == 'save'
                  else '选择一份记录，回到上次停下的地方', (175, 200), FADED)
            for slot in range(1, 4):
                y = 248 + (slot - 1) * 116
                self.add_button((180, y, 920, 82),
                                f'记录 {slot:02}     /     {self.store.description(slot)}', f'{self.overlay}_slot', slot)
                pygame.draw.line(self.canvas, LINE, (180, y + 95), (1100, y + 95), 1)
            if self.overlay == 'load':
                self.add_button((780, 620, 320, 48), '章节自动存档', 'checkpoints')
            label(self.canvas, self.micro_font, 'F5 / F9 快速存读第一份记录', (180, 656), FADED)
        elif self.overlay == 'history':
            rect = pygame.Rect(175, 204, 925, 438)
            entries = []
            for entry in reversed(self.engine.history):
                entries.append((entry['speaker'] or '游园记录', GREEN))
                entries.extend((line, INK) for line in wrap_text(entry['text'], self.small_font, 890))
                if entry.get('popup'):
                    entries.extend((line, GREEN) for line in wrap_text('提示：' + entry['popup']['text'], self.small_font, 890))
                if entry['choice'] is not None:
                    entries.extend((line, RED) for line in wrap_text('已选择 → ' + entry['choice'], self.small_font, 890))
                entries.append(('', FADED))
            self.history_max_scroll = max(0, len(entries) * 32 - rect.height)
            self.scroll = min(self.scroll, self.history_max_scroll)
            self.canvas.set_clip(rect)
            for i, (text, color) in enumerate(entries):
                y = rect.y + i * 32 - self.scroll
                if rect.y - 32 <= y <= rect.bottom:
                    label(self.canvas, self.small_font, text, (rect.x, y), color)
            self.canvas.set_clip(None)
            label(self.canvas, self.micro_font, '最近的记录在前 · 滚轮 / 上下键翻阅 · 仅记录您亲眼所见的内容', (175, 668), FADED)
        elif self.overlay == 'restart':
            label(self.canvas, self.body_font, '未保存的记录将丢失，已有存档会保留。', (180, 260), INK)
            self.add_button((180, 370, 400, 64), '重新入园', 'confirm_restart')
            self.add_button((620, 370, 400, 64), '返回当前记录', 'close')
        elif self.overlay == 'help':
            for i, text in enumerate(('左键 / 空格 / 回车：显示全文或继续', '数字键 1—6：选择行动',
                                      'H / 右键：游园记录；滚轮：翻阅', 'S / L：存档与读档；F5 / F9：快速存读',
                                      'Backspace：回退；V：重听本页语音', 'B：背包；R：守则；Esc：设定 / 关闭菜单')):
                label(self.canvas, self.body_font, text, (180, 220 + i * 62), INK)

    def render(self):
        self.buttons = []
        if self.scene == 'title':
            from .screens import draw_title
            draw_title(self)
        elif self.scene == 'chapter':
            from .screens import draw_chapter
            draw_chapter(self)
        else:
            self.draw_scene()
            self.draw_dialogue()
        if self.overlay:
            self.draw_overlay()
        if self.notice_time > 0 and not (self.scene == 'game' and self.engine.popup):
            notice_lines = wrap_text(self.notice, self.small_font, 1000)
            height = 24 + 28 * len(notice_lines)
            pygame.draw.rect(self.canvas, (42, 53, 42), (110, 70, 1060, height), border_radius=8)
            for i, line in enumerate(notice_lines):
                label(self.canvas, self.small_font, line, (135, 80 + i * 28), ACCENT)
        if self.scene == 'game' and self.engine.popup:
            from .popup_ui import draw_popup
            draw_popup(self)
        width, height = self.screen.get_size()
        ratio = min(width / WIDTH, height / HEIGHT)
        size = (max(1, round(WIDTH * ratio)), max(1, round(HEIGHT * ratio)))
        self.viewport = pygame.Rect((width - size[0]) // 2, (height - size[1]) // 2, *size)
        self.screen.fill((0, 0, 0))
        self.screen.blit(pygame.transform.smoothscale(self.canvas, size), self.viewport)
        pygame.display.flip()

    def run(self, frames=None, screenshot=None):
        clock = pygame.time.Clock()
        count = 0
        self.render()
        while self.running:
            dt = min(clock.tick(60) / 1000, 0.1)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.render()
            count += 1
            if frames is not None and count >= frames:
                break
        if screenshot:
            pygame.image.save(self.canvas, str(screenshot))

    def paper_panel(self, rect):
        rect = pygame.Rect(rect)
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        shadow.fill((24, 55, 43, 24))
        self.canvas.blit(shadow, rect.move(3, 5))
        pygame.draw.rect(self.canvas, PAPER, rect, border_radius=6)
        pygame.draw.rect(self.canvas, LINE, rect, 1, border_radius=6)


def main(argv=None):
    parser = argparse.ArgumentParser(description='动物园文字游戏')
    parser.add_argument('--story', type=Path, default=ROOT / 'data/story.json')
    parser.add_argument('--save-dir', type=Path, default=ROOT / 'saves/gui')
    parser.add_argument('--font', help='相对剧情目录的字体文件；默认使用系统中文字体')
    parser.add_argument('--text-speed', type=int, default=36, help='每秒显示字符数，1—300')
    parser.add_argument('--mute', action='store_true')
    parser.add_argument('--check', action='store_true', help='校验剧情和素材路径')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--frames', type=int, help='运行指定帧数后退出')
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.text_speed <= 300:
        parser.error('--text-speed 必须在 1—300 之间')
    if args.frames is not None and args.frames <= 0:
        parser.error('--frames 必须为正数')
    if args.headless and args.frames is None and not args.check:
        parser.error('--headless 需要 --frames')
    if args.headless:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    try:
        story = Story.load(args.story)
        if args.check:
            print(f'剧情校验通过：{len(story.chapters)} 章，{sum(len(c["contents"]) for c in story.chapters)} 个节点')
            return 0
        app = App(story, args.save_dir, muted=args.mute, font=args.font, text_speed=args.text_speed)
        app.run(args.frames, args.screenshot)
        return 0
    except (StoryError, pygame.error, OSError) as exc:
        print(f'启动或运行失败：{exc}', file=sys.stderr)
        return 1
    finally:
        pygame.quit()
