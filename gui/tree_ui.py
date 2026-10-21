"""Chapter tree layout and a pannable, zoomable tree viewport."""
import pygame
from .style import PAPER, GREEN, MUTED, LINE, RED
from .ui import Button, label, fitted_label

CARD_W, CARD_H, GAP_X, GAP_Y = 224, 88, 42, 50
VIEW = pygame.Rect(175, 236, 930, 342)


def layout_tree(tree):
    """Allocate disjoint subtree widths; center each parent above its children."""
    nodes = {node['id']: node for node in tree['nodes']}
    order, pending = [], list(reversed(tree['roots']))
    while pending:
        node_id = pending.pop()
        order.append(node_id)
        pending.extend(reversed(nodes[node_id]['children']))
    widths = {}
    for node_id in reversed(order):
        children = nodes[node_id]['children']
        widths[node_id] = max(CARD_W, sum(widths[c] for c in children) + GAP_X * max(0, len(children) - 1))
    positions = {}
    offset = 0
    pending = []
    for root in tree['roots']:
        pending.append((root, offset, 0))
        offset += widths[root] + GAP_X
    bottom = 0
    while pending:
        node_id, left, depth = pending.pop()
        y = depth * (CARD_H + GAP_Y)
        positions[node_id] = pygame.Rect(left + (widths[node_id] - CARD_W) / 2, y, CARD_W, CARD_H)
        bottom = max(bottom, y + CARD_H)
        child_left = left
        for child in nodes[node_id]['children']:
            pending.append((child, child_left, depth + 1))
            child_left += widths[child] + GAP_X
    # Center on the immediate children's centers, even for unequal subtrees.
    for node_id in reversed(order):
        children = nodes[node_id]['children']
        if children:
            positions[node_id].centerx = round((positions[children[0]].centerx + positions[children[-1]].centerx) / 2)
    return positions, (max(0, offset - GAP_X), bottom)


def zoom(app, factor):
    previous = app.graph_zoom
    app.graph_zoom = max(.2, min(2.5, previous * factor))
    app.graph_pan = [coordinate * app.graph_zoom / previous for coordinate in app.graph_pan]


def ellipsis(text, font, width):
    text = ' '.join(text.splitlines())
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + '…')[0] > width:
        text = text[:-1]
    return text + '…'


def draw_graph(app):
    tree = app.session.flowchart()
    nodes = tree['nodes']
    if not nodes:
        label(app.canvas, app.small_font, '尚无游园记录。进入章节后，这里会长出你的故事树。', (180, 270), MUTED)
        return
    positions, extent = layout_tree(tree)
    if app.graph_fit:
        app.graph_zoom = min(1., (VIEW.width - 36) / extent[0], (VIEW.height - 24) / extent[1])
        app.graph_pan = [0., 0.]
        app.graph_fit = False
    label(app.canvas, app.micro_font, '章节树 · 拖动空白处移动 · 滚轮上下 / Shift 左右', (175, 204), MUTED)
    label(app.canvas, app.micro_font, f'{round(app.graph_zoom * 100)}%', (784, 204), MUTED)
    app.add_button((835, 196, 48, 30), '−', 'graph_zoom', .8)
    app.add_button((891, 196, 48, 30), '+', 'graph_zoom', 1.25)
    app.add_button((947, 196, 158, 30), '适应窗口', 'graph_fit')
    pygame.draw.rect(app.canvas, (239, 244, 237), VIEW, border_radius=4)
    scale = app.graph_zoom
    max_x = max(0, (extent[0] * scale - VIEW.width) / 2 + 50)
    max_y = max(0, (extent[1] * scale - VIEW.height) / 2 + 50)
    app.graph_pan[0] = max(-max_x, min(max_x, app.graph_pan[0]))
    app.graph_pan[1] = max(-max_y, min(max_y, app.graph_pan[1]))
    origin = (VIEW.centerx - extent[0] * scale / 2 + app.graph_pan[0],
              VIEW.centery - extent[1] * scale / 2 + app.graph_pan[1])
    rects = {key: pygame.Rect(round(origin[0] + r.x * scale), round(origin[1] + r.y * scale),
                              max(1, round(CARD_W * scale)), max(1, round(CARD_H * scale)))
             for key, r in positions.items()}
    app.canvas.set_clip(VIEW)
    for node in nodes:
        if node['parent'] is None:
            continue
        parent, child = rects[node['parent']], rects[node['id']]
        mid = (parent.bottom + child.top) // 2
        color = RED if node['ending'] == 'death' else GREEN
        pygame.draw.lines(app.canvas, color, False,
                          [parent.midbottom, (parent.centerx, mid), (child.centerx, mid), child.midtop], max(1, round(scale * 2)))
        arrow = max(3, round(5 * scale))
        pygame.draw.polygon(app.canvas, color, [(child.centerx, child.top), (child.centerx - arrow, child.top - arrow), (child.centerx + arrow, child.top - arrow)])
    for node in nodes:
        rect = rects[node['id']]
        if not VIEW.colliderect(rect):
            continue
        card = pygame.Surface((CARD_W, CARD_H))
        card.fill(PAPER)
        color = RED if node['ending'] == 'death' else GREEN
        selected = node['id'] == app.graph_selected
        pygame.draw.rect(card, color if selected or node['ending'] else LINE, card.get_rect(), 3 if selected else 1)
        pygame.draw.rect(card, color, (0, 0, 4, CARD_H))
        kind = {'normal': '结局', 'death': '死亡结局'}.get(node['ending'], '章节')
        if node['completed']:
            kind += ' · 已抵达'
        label(card, app.micro_font, kind, (14, 6), color)
        if node['current']:
            label(card, app.micro_font, '当前', (180, 6), GREEN)
        fitted_label(card, app.small_font, node['title'], pygame.Rect(14, 28, CARD_W - 28, 28), color)
        label(card, app.micro_font, ellipsis(node['description'], app.micro_font, CARD_W - 28), (14, 61), MUTED)
        app.canvas.blit(pygame.transform.smoothscale(card, rect.size), rect)
        app.buttons.append(Button(rect.clip(VIEW), node['title'], 'select_point', node['id']))
    app.canvas.set_clip(None)
    selected = next((node for node in nodes if node['id'] == app.graph_selected), None)
    if selected:
        label(app.canvas, app.small_font, ellipsis(selected['title'], app.small_font, 580), (180, 591), GREEN)
        label(app.canvas, app.micro_font, ellipsis(selected['description'], app.micro_font, 580), (180, 625), MUTED)
        text = '从章节入口继续' if selected['entry'] else '从记录处继续'
        app.add_button((820, 607, 280, 48), text, 'load_point', selected['load_point'])
    else:
        label(app.canvas, app.small_font, '选择一个章节，查看简介并从该章节继续。', (180, 604), MUTED)
    label(app.canvas, app.micro_font, '仅展示已走过的路线 · 绿色：章节 / 结局 · 红色：死亡结局', (180, 674), MUTED)
