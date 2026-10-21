"""Blocking message cards; colors share the dialogue markup contract."""
import pygame
from .style import GREEN, INK, LINE, MUTED
from .ui import WIDTH, HEIGHT, label, fitted_label, text_pages

PANEL = pygame.Rect(220, 180, 840, 440)


def prepare(app):
    app.popup_index = 0
    message = app.engine.popup if app.engine else None
    app.popup_chunks = text_pages(message['text'], app.body_font, 752, lines_per_page=6) if message else []


def confirm(app):
    if app.popup_index + 1 < len(app.popup_chunks):
        app.popup_index += 1
        return
    app.session.apply('advance')
    app.sync_page()


def draw_popup(app):
    message = app.engine.popup
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((12, 30, 24, 175))
    app.canvas.blit(shade, (0, 0))
    app.paper_panel(PANEL)
    app.buttons = []  # Background controls cannot receive this click.
    fitted_label(app.canvas, app.title_font, message['title'], pygame.Rect(260, 201, 752, 49), GREEN)
    pygame.draw.line(app.canvas, LINE, (260, 252), (1020, 252))
    source, cursor = message['text'], 0
    for chunk_index, lines in enumerate(app.popup_chunks):
        for line_index, line in enumerate(lines):
            start = source.find(line, cursor)
            start = cursor if start < 0 else start
            cursor = start + len(line)
            if source[cursor:cursor + 1] == '\n':
                cursor += 1
            if chunk_index != app.popup_index:
                continue
            x = 260
            for offset, char in enumerate(line):
                color = INK
                for span in message['text_spans']:
                    if span['start'] <= start + offset < span['end']:
                        color = span['color']
                label(app.canvas, app.body_font, char, (x, 272 + line_index * 38), color)
                x += app.body_font.size(char)[0]
    more = app.popup_index + 1 < len(app.popup_chunks)
    hint = '点击弹窗 / 空格 / 回车继续'
    if len(app.popup_chunks) > 1:
        hint += f'  ·  {app.popup_index + 1}/{len(app.popup_chunks)}'
    label(app.canvas, app.micro_font, hint, (260, 567), MUTED)
    app.add_button((824, 550, 196, 48), '下一页' if more else '知道了', 'popup_continue')
