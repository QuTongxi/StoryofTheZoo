"""Acquired rules only: book tabs, a bookmarked-only tab, and entry bookmarks."""
import pygame
from .ui import label, wrap_text


def draw_rules(app):
    ink = (34, 48, 41)
    accent = (35, 66, 55)
    muted = (109, 117, 102)
    archive=app.overlay=='archive'
    rule_books = app.session.collection.rulebooks if archive else app.engine.rulebooks
    tabs = [{'id': '__bookmarks__', 'title': '资料馆说明' if archive else '我的书签'}] + rule_books
    ids = [book['id'] for book in tabs]
    if app.rule_active_book not in ids:
        app.rule_active_book = rule_books[0]['id'] if rule_books else '__bookmarks__'
    label(app.canvas, app.small_font, '跨周目收集 · 不影响角色已知信息' if archive else '已收集的守则', (175, 205), accent)
    # Up to six book tabs at once; explicit paging accommodates any number of books.
    app.rule_tab_offset = max(0, min(app.rule_tab_offset, max(0, len(tabs) - 6)))
    for i, book in enumerate(tabs[app.rule_tab_offset:app.rule_tab_offset + 6]):
        title = f"[ {book['title']} ]" if book['id'] == app.rule_active_book else book['title']
        app.add_button((170, 247 + i * 53, 210, 43), title, 'rule_book', book['id'])
    if len(tabs) > 6:
        app.add_button((170, 580, 100, 38), '上一组', 'rule_tabs', -6)
        app.add_button((280, 580, 100, 38), '下一组', 'rule_tabs', 6)
    pygame.draw.line(app.canvas, muted, (402, 208), (402, 639), 1)
    entries = []
    for book in rule_books:
        for entry in book['entries']:
            if book['id'] == app.rule_active_book or (
                app.rule_active_book == '__bookmarks__' and entry['bookmarked']
            ):
                entries.append((book, entry))
    title = next(book['title'] for book in tabs if book['id'] == app.rule_active_book)
    label(app.canvas, app.small_font, title, (426, 204), accent)
    rect = pygame.Rect(423, 245, 675, 391)
    prepared = []
    total = 0
    for book, entry in entries:
        lines = wrap_text(entry['text'], app.small_font, 652)
        height = 45 + len(lines) * 30 + 24
        prepared.append((book, entry, lines, total, height))
        total += height
    app.rule_max_scroll = max(0, total - rect.height)
    app.rule_scroll = max(0, min(app.rule_scroll, app.rule_max_scroll))
    app.canvas.set_clip(rect)
    if not entries:
        text = '尚未添加书签。' if rule_books else '尚未获得守则，请继续探索。'
        label(app.canvas, app.small_font, text, (426, 269), muted)
    for book, entry, lines, offset, height in prepared:
        y = rect.y + offset - app.rule_scroll
        if y + height < rect.top or y > rect.bottom:
            continue
        title = f"{book['title']} · {entry['id']}"
        # Leave room for the bookmark control; long identifiers wrap or crop here only.
        clipped_title = title
        while app.small_font.size(clipped_title)[0] > 470:
            clipped_title = clipped_title[:-2] + '…'
        label(app.canvas, app.small_font, clipped_title, (426, y + 3), accent)
        button_rect = pygame.Rect(982, y, 110, 34)
        if rect.contains(button_rect):
            if not archive:
                app.add_button(button_rect, '取消书签' if entry['bookmarked'] else '加书签',
                           'bookmark', f"{book['id']}:{entry['id']}")
        for i, line in enumerate(lines):
            label(app.canvas, app.small_font, line, (426, y + 45 + i * 30), ink)
        pygame.draw.line(app.canvas, muted, (426, y + height - 12), (1092, y + height - 12), 1)
    app.canvas.set_clip(None)
    if app.rule_max_scroll:
        track = pygame.Rect(1110, rect.y, 4, rect.height)
        pygame.draw.rect(app.canvas, muted, track)
        thumb_height = max(30, int(rect.height * rect.height / total))
        thumb_y = rect.y + int((rect.height - thumb_height) * app.rule_scroll / app.rule_max_scroll)
        pygame.draw.rect(app.canvas, accent, (1110, thumb_y, 4, thumb_height))
    label(app.canvas, app.small_font, '关闭按钮返回 · 滚轮翻阅 · 资料馆不会把知识交给当前角色' if archive else 'R / 关闭按钮收起守则 · 滚轮翻阅 · 已获得内容随剧情存档和回退', (175, 665), muted)
