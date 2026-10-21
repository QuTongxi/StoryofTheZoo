"""Static item definitions. Quantities and scene-specific effects live in Engine."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    description: str
    icon: str | None = None


def load_items(records):
    # Local import avoids a module cycle while Story compiles item references.
    from .story import StoryError
    if not isinstance(records, list):
        raise StoryError('items 必须是物品定义列表')
    result = {}
    for record in records:
        if not isinstance(record, dict) or set(record) - {'id', 'name', 'description', 'icon'}:
            raise StoryError('物品定义只支持 id、name、description、icon')
        if not all(isinstance(record.get(k), str) and record[k].strip() for k in ('id', 'name', 'description')):
            raise StoryError('物品需要非空 id、name 和 description')
        if record['id'] in result:
            raise StoryError(f"物品 ID 重复：{record['id']}")
        icon = record.get('icon')
        if icon is not None and (not isinstance(icon, str) or not icon):
            raise StoryError('物品 icon 必须是相对素材路径或 null')
        result[record['id']] = Item(**record)
    return result
