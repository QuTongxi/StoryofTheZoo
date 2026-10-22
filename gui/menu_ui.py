"""Settings and inventory widgets shared by both GUI skins."""
import pygame
from .ui import label, wrap_text, fitted_label


def draw_settings(app):
    ink, accent, muted = (34, 48, 41), (35, 66, 55), (109, 117, 102)
    label(app.canvas, app.small_font, '进度与游玩设置', (180, 202), muted)
    if app.scene in ('title', 'stories'):
        options = [('读取进度', 'load'), ('剧情图', 'flowchart'), ('游园成就', 'achievements'),
                   ('资料馆', 'archive'), ('回忆画廊', 'gallery'),
                   ('制作与素材', 'credits'), ('操作说明', 'help')]
    else:
        options = [('保存进度  S', 'save'), ('读取进度  L', 'load'),
                   ('剧情图', 'flowchart'), ('游园成就', 'achievements'),
                   ('回退一步', 'rollback'), ('剧情回顾  H', 'history'),
                   ('资料馆', 'archive'), ('回忆画廊', 'gallery'),
                   ('制作与素材', 'credits'), ('返回标题', 'to_title')]
    for i, (title, action) in enumerate(options):
        app.add_button((180 + (i % 2) * 470, 238 + (i // 2) * 65, 440, 52), title, action)
    app.add_button((180, 580, 440, 48), '说话提示音：'+('开' if app.media.typing_enabled else '关'), 'typing_sound')
    app.add_button((650, 580, 440, 48), f'背景音乐音量：{round(app.media.volume*100)}%', 'music_volume')
    label(app.canvas, app.small_font, 'F5 / F9 快速存读 · Esc 收起设定', (180, 670), muted)


def draw_inventory(app):
    ink, accent, muted = (34, 48, 41), (35, 66, 55), (109, 117, 102)
    inventory = app.engine.inventory
    page_count = max(1, (len(inventory) + 8) // 9)
    app.inventory_page = max(0, min(app.inventory_page, page_count - 1))
    ids = [item['id'] for item in inventory]
    if app.inventory_selected not in ids:
        app.inventory_selected = ids[0] if ids else None
    label(app.canvas, app.small_font, f'随身物品 · {len(inventory)} 种', (180, 204), accent)
    for i, item in enumerate(inventory[app.inventory_page * 9:app.inventory_page * 9 + 9]):
        rect = pygame.Rect(175 + (i % 3) * 180, 248 + (i // 3) * 110, 166, 94)
        app.add_button(rect, '', 'inspect_item', item['id'])
        if item['icon']:
            image=app.scaled(item['icon'],(64,64))
            app.canvas.blit(image,(rect.x+8,rect.y+5))
        if item['id']==app.inventory_selected:
            pygame.draw.rect(app.canvas,accent,rect,2,border_radius=5)
        label(app.canvas, app.micro_font, f"× {item['count']}", (rect.x + 110, rect.y+24), muted)
        fitted_label(app.canvas,app.micro_font,item['name'],pygame.Rect(rect.x+8,rect.bottom-25,150,22),accent)
    if not inventory:
        label(app.canvas, app.small_font, '背包里暂时没有物品。', (180, 270), muted)
    if page_count > 1:
        app.add_button((175, 592, 150, 40), '上一页', 'inventory_page', -1)
        app.add_button((535, 592, 150, 40), '下一页', 'inventory_page', 1)
        label(app.canvas, app.small_font, f'{app.inventory_page + 1} / {page_count}', (400, 600), muted)
    pygame.draw.line(app.canvas, muted, (730, 208), (730, 635), 1)
    selected = next((item for item in inventory if item['id'] == app.inventory_selected), None)
    if selected:
        fitted_label(app.canvas, app.title_font, selected['name'], pygame.Rect(768, 230, 326, 48), accent)
        label(app.canvas, app.small_font, f"数量：{selected['count']}", (772, 290), muted)
        if selected['icon']:
            image = app.scaled(selected['icon'], (120, 120))
            app.canvas.blit(image, (970, 293))
        description_width = 190 if selected['icon'] else 322
        lines = wrap_text(selected['description'], app.small_font, description_width)
        rect = pygame.Rect(772, 342, description_width, 190)
        app.inventory_max_scroll = max(0, len(lines) * 30 - rect.height)
        app.inventory_scroll = max(0, min(app.inventory_scroll, app.inventory_max_scroll))
        app.canvas.set_clip(rect)
        for i, text in enumerate(lines):
            label(app.canvas, app.small_font, text, (rect.x, rect.y + i * 30 - app.inventory_scroll), ink)
        app.canvas.set_clip(None)
        if app.inventory_max_scroll:
            label(app.canvas, app.small_font, '滚轮查看完整说明', (772, 544), muted)
        if selected['usable']:
            app.add_button((772, 585, 322, 48), '使用物品', 'use_item', selected['id'])
        else:
            reason = '当前物品不可使用'
            label(app.canvas, app.small_font, reason, (772, 595), muted)
    label(app.canvas, app.small_font, 'B / 关闭按钮收起背包 · 使用物品可能推进剧情', (175, 670), muted)
