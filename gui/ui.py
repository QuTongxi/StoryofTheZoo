"""Fixed logical canvas, Chinese wrapping and reusable buttons."""
from __future__ import annotations

from dataclasses import dataclass
import pygame

WIDTH, HEIGHT = 1280, 800
INK = (231, 230, 218)


def wrap_text(text, font, width):
    """Character wrapping supports CJK and preserves explicit line breaks."""
    if width <= 0:
        raise ValueError("文字区域宽度必须为正数")
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for char in paragraph:
            if line and font.size(line + char)[0] > width:
                lines.append(line)
                line = char
            else:
                line += char
        lines.append(line)
    return lines


def text_pages(text, font, width, lines_per_page=3):
    lines = wrap_text(text, font, width)
    return [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]


def label(surface, font, text, pos, color=INK):
    surface.blit(font.render(text, True, color), pos)


def fitted_label(surface, font, text, rect, color=INK):
    # Long menu/choice labels remain inside their clickable region.
    rendered = font.render(text, True, color)
    if rendered.get_width() > rect.width:
        factor = rect.width / rendered.get_width()
        rendered = pygame.transform.smoothscale(rendered, (rect.width, max(1, int(rendered.get_height() * factor))))
    surface.blit(rendered, (rect.x, rect.centery - rendered.get_height() // 2))


@dataclass
class Button:
    rect: pygame.Rect
    text: str
    action: str
    value: int | str | None = None
