"""Small explicit dialogue markup; offsets refer to visible Unicode characters."""
import re
from .story import StoryError

COLORS = {'red': (191, 60, 48), 'green': (50, 140, 85), 'blue': (65, 120, 195)}
TOKEN = re.compile(r'</?(?:red|green|blue)>')


def parse_rich(source):
    text, spans, stack = '', [], []
    last = 0
    for match in TOKEN.finditer(source):
        text += source[last:match.start()]
        token = match.group()
        name = token.strip('</>')
        if token.startswith('</'):
            if not stack or stack[-1][0] != name:
                raise StoryError('文字颜色标签未正确配对')
            _, start = stack.pop()
            spans.append((start, len(text), COLORS[name]))
        else:
            stack.append((name, len(text)))
        last = match.end()
    text += source[last:]
    if stack:
        raise StoryError('文字颜色标签缺少结束标签')
    # Outer spans first; nested spans override their colors.
    return text, sorted(spans, key=lambda s: (s[0], -s[1]))
