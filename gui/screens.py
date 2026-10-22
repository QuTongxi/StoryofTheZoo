"""Title, chapter cards, visited story graph, and achievement collection."""
import pygame
from .style import backdrop, icon, INK, GREEN, MUTED, PAPER, LINE, RED
from .ui import WIDTH, HEIGHT, Button, label, fitted_label, wrap_text


def background(app, path=None, variant=0):
    backdrop(app.canvas, variant)
    if path:
        surface = app.scaled(path, (WIDTH, HEIGHT), cover=True)
        app.canvas.blit(surface, ((WIDTH - surface.get_width()) // 2, (HEIGHT - surface.get_height()) // 2))


def draw_title(app):
    background(app, app.story.title.get('background'))

    def floating_text(font, text, pos, color, max_width):
        lettering = font.render(text, True, color)
        shadow = font.render(text, True, (15, 27, 31))
        if lettering.get_width() > max_width:
            size = (max_width, round(lettering.get_height() * max_width / lettering.get_width()))
            lettering = pygame.transform.smoothscale(lettering, size)
            shadow = pygame.transform.smoothscale(shadow, size)
        shadow.set_alpha(180)
        x, y = pos
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (2, 3)):
            app.canvas.blit(shadow, (x + dx, y + dy))
        app.canvas.blit(lettering, pos)

    floating_text(app.logo_font, app.library.title if app.library else app.story.name,
                  (96, 164), (255, 249, 235), 450)
    options = [('新游戏', 'new_game'), ('载入存档', 'load'), ('设置', 'settings'), ('退出游戏', 'quit')]
    for i, (title, action) in enumerate(options):
        rect = pygame.Rect(102, 370 + i * 68, 270, 54)
        app.buttons.append(Button(rect, title, action))
        hover = rect.collidepoint(app.logical_position(pygame.mouse.get_pos()))
        color = (255, 222, 156) if hover else (255, 249, 235)
        x = rect.x + (22 if hover else 12)
        floating_text(app.menu_font, title, (x, rect.y + 8), color, 240)
        if hover:
            pygame.draw.line(app.canvas, color, (rect.x, rect.centery), (rect.x + 9, rect.centery), 2)


def draw_stories(app):
    background(app, 'art/covers/opening.png')
    app.paper_panel((64, 55, 1152, 690))
    label(app.canvas, app.title_font, '选择故事', (100, 83), GREEN)
    label(app.canvas, app.small_font, '两份独立的记录。请从今天的约会开始。', (102, 137), MUTED)
    for i, (key, entry) in enumerate(app.library.entries.items()):
        x = 102 + i * 552
        picture = app.scaled(entry['cover'], (514, 290))
        app.canvas.blit(picture, (x + (514-picture.get_width())//2, 204))
        unlocked = app.library.unlocked(key)
        if not unlocked:
            shade = pygame.Surface((514, 290), pygame.SRCALPHA)
            shade.fill((10, 20, 28, 165))
            app.canvas.blit(shade, (x, 204))
            label(app.canvas, app.title_font, '未解锁', (x+200, 320), PAPER)
        label(app.canvas, app.small_font, entry['name'], (x, 510), GREEN)
        for n, line in enumerate(wrap_text(entry['description'] if unlocked else '完成游客线的海洋馆之夜后解锁。', app.small_font, 500)):
            label(app.canvas, app.small_font, line, (x, 548+n*28), MUTED)
        app.add_button((x, 610, 514, 52), '开始故事' if unlocked else '未解锁 · 查看条件', 'select_story', key)
    app.add_button((984, 82, 190, 48), '返回标题', 'to_title')


def draw_chapter(app):
    chapter = app.engine.chapter
    number = app.story.chapters.index(chapter) + 1
    background(app, chapter.get('background'), number - 1)
    panel=pygame.Surface((900,300),pygame.SRCALPHA);panel.fill((12,24,29,224))
    app.canvas.blit(panel,(190,430))
    light,soft=(224,237,235),(153,187,185)
    label(app.canvas, app.micro_font, f'FIELD NOTES    /    {chapter["id"]}', (245, 454), soft)
    pygame.draw.line(app.canvas, soft, (245, 489), (1035, 489), 1)
    fitted_label(app.canvas, app.title_font, chapter['title'], pygame.Rect(245, 503, 790, 65), light)
    for i, line in enumerate(wrap_text(chapter.get('subtitle', ''), app.small_font, 750)[:2]):
        label(app.canvas, app.small_font, line, (248, 577 + i * 30), soft)
    icon(app.canvas, 'save', (248, 670, 22, 22),soft)
    label(app.canvas, app.micro_font, '已自动保存章节入口', (285, 673), soft)
    app.add_button((800, 651, 235, 50), '进入章节', 'chapter_continue')
    for i, (text, action) in enumerate((('设定', 'settings'), ('背包', 'inventory'), ('守则', 'rules'))):
        app.add_button((900 + i * 114, 15, 104, 35), text, action)


def pagination(app, count, per_page):
    total = max(1, (count + per_page - 1) // per_page)
    app.panel_page = max(0, min(app.panel_page, total - 1))
    if app.panel_page:
        app.add_button((180, 648, 150, 40), '上一页', 'panel_page', -1)
    if app.panel_page + 1 < total:
        app.add_button((940, 648, 150, 40), '下一页', 'panel_page', 1)
    label(app.canvas, app.micro_font, f'{app.panel_page + 1} / {total}', (620, 659), MUTED)
    return app.panel_page * per_page


def draw_progress(app):
    if app.overlay == 'achievements':
        achievements = app.session.collection.achievements
        completed = sum(a['completed'] for a in achievements)
        label(app.canvas, app.small_font, f'已达成 {completed} / {len(achievements)} · 本地跨周目保留', (180, 203), MUTED)
        start = pagination(app, len(achievements), 4)
        if not achievements:
            label(app.canvas, app.small_font, '开始游园后，在这里查看已登记的成就。', (180, 290), MUTED)
        for i, a in enumerate(achievements[start:start + 4]):
            y = 252 + i * 94
            color = GREEN if a['completed'] else MUTED
            icon(app.canvas, 'trophy', (184, y + 8, 34, 34), color)
            label(app.canvas, app.small_font, a['title'] if a['completed'] else '尚未发现', (240, y), color)
            fitted_label(app.canvas, app.micro_font, a['description'] if a['completed'] else '继续游玩，留下自己的记录。', pygame.Rect(240, y + 31, 680, 32), MUTED)
            label(app.canvas, app.micro_font, '已达成' if a['completed'] else '未达成', (1010, y + 12), color)
            pygame.draw.line(app.canvas, LINE, (180, y + 76), (1100, y + 76))
    elif app.overlay == 'gallery':
        unlocked=[c for c in app.story.chapters if c['id'] in app.session.collection.data['endings']]
        label(app.canvas,app.small_font,f'已收藏 {len(unlocked)} 幅结局画面 · 点击查看大图',(180,203),MUTED)
        start=pagination(app,len(unlocked),6)
        for i,chapter in enumerate(unlocked[start:start+6]):
            x,y=180+(i%3)*310,250+(i//3)*185
            app.add_button((x,y,285,170),'','gallery_image',chapter['id'])
            art=app.scaled(chapter['background'],(277,132),cover=True)
            clip=pygame.Rect(x+4,y+4,277,132)
            app.canvas.set_clip(clip);app.canvas.blit(art,clip.topleft);app.canvas.set_clip(None)
            fitted_label(app.canvas,app.micro_font,chapter['title'],pygame.Rect(x+8,y+139,267,26),GREEN)
        if not unlocked:
            label(app.canvas,app.small_font,'走完一个结局后，相应画面会保存在这里。',(180,290),MUTED)
    elif app.overlay == 'gallery_image':
        chapter=app.story.chapter(app.gallery_selected)
        art=app.scaled(chapter['background'],(920,490))
        app.canvas.blit(art,((1280-art.get_width())//2,200))
        app.add_button((180,116,160,40),'返回画廊','gallery')
    elif app.overlay == 'credits':
        lines=['原作：十六椰子《动物园怪谈》',
               '机制参考：狼蛹的解析；解读与本作改编并非原作定论。',
               '人物、剧情分支及插画：本项目制作；插画使用 OpenAI 图像生成。',
               '音乐：Kevin MacLeod (incompetech.com)，CC BY 4.0。',
               'Carefree / Evening Fall (Harp) / Lightless Dawn',
               'Long note One / Unseen Horrors',
               '界面音效：Kenney Interface Sounds，CC0。',
               '环境与异常音效：本项目原创合成音效。',
               '完整链接、署名和授权说明见根目录 CREDITS.md。',
               '非商业同人项目。第三方素材遵循各自授权。']
        for i,text in enumerate(lines):
            label(app.canvas,app.small_font,text,(180,215+i*43),INK)
    elif app.overlay == 'checkpoints':
        points = [p for p in reversed(app.session.points()) if p['kind'] == 'chapter']
        label(app.canvas, app.small_font, '每次进入章节自动保存 · 点击回到当时的章节入口', (180, 203), MUTED)
        start = pagination(app, len(points), 5)
        for i, point in enumerate(points[start:start + 5]):
            app.add_button((180, 252 + i * 74, 920, 58), f"{point['label']}  /  {point['id']}", 'load_point', point['id'])
        if not points:
            label(app.canvas, app.small_font, '尚无章节记录。', (180, 290), MUTED)
    else:
        from .tree_ui import draw_graph
        draw_graph(app)
