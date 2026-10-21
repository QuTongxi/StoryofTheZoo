"""Persistent playthrough and visited-path checkpoints shared by GUI and CLI."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .engine import Engine
from .story import StoryError


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.save-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


class Session:
    VERSION = 1

    def __init__(self, story, path, *, persist=True):
        self.story, self.path = story, Path(path)
        self.persist = persist
        from .collection import Collection
        self.collection = Collection(story, self.path.parent / 'collection.json')
        self.engine = None
        self.data = {'version': self.VERSION, 'story': story.fingerprint,
                     'current': None, 'active': None, 'points': [], 'segment': []}
        if self.path.exists():
            try:
                if self.path.stat().st_size > 64 * 1024 * 1024:
                    raise StoryError('会话文件过大')
                data = json.loads(self.path.read_text(encoding='utf-8'))
                self._validate(data)
                self.data = data
                self.engine = Engine(story, initialize=False)
                self.engine.restore(data['current'])
                self.collection.update(self.engine, persist=self.persist)
            except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
                raise StoryError(f'无法读取游玩记录：{exc}') from exc

    def _validate(self, data):
        if not isinstance(data, dict) or set(data) != set(self.data) or data['version'] != self.VERSION or data['story'] != self.story.fingerprint:
            raise StoryError('会话或故事版本已变化，请使用新的存档目录')
        if not isinstance(data['points'], list) or not isinstance(data['segment'], list):
            raise StoryError('存档点或观察记录无效')
        probe = Engine(self.story, initialize=False)
        probe.restore(data['current'])
        if not data['segment'] or probe.observations[-len(data['segment']):] != data['segment']:
            raise StoryError('观察记录与实际路径不一致')
        seen = set()
        for point in data['points']:
            if not isinstance(point, dict) or set(point) != {'id', 'kind', 'label', 'parent', 'created_at', 'snapshot'}:
                raise StoryError('存档点格式无效')
            if point['id'] != f'cp-{len(seen)+1:04}' or point['kind'] not in ('chapter', 'node', 'manual'):
                raise StoryError('存档点编号或类型无效')
            if point['parent'] is not None and point['parent'] not in seen:
                raise StoryError('剧情图的前置节点无效')
            if not isinstance(point['label'], str) or not isinstance(point['created_at'], str):
                raise StoryError('存档点描述无效')
            probe.restore(point['snapshot'])
            if point['kind'] == 'chapter' and not probe.state['chapter_pending']:
                raise StoryError('章节存档必须位于章节入口')
            seen.add(point['id'])
        if data['active'] not in seen:
            raise StoryError('当前存档点不存在')

    def _commit(self, data):
        if self.persist:
            atomic_json(self.path, data)
        self.data = data
        if self.engine is not None:
            self.collection.update(self.engine, persist=self.persist)

    def flush(self):
        atomic_json(self.path, self.data)
        atomic_json(self.collection.path, self.collection.data)

    def start(self):
        previous, active = self.engine, self.data['active']
        self.engine = Engine(self.story)
        self.data['active'] = None
        try:
            self.capture(force=True)
        except Exception:
            self.engine, self.data['active'] = previous, active
            raise
        return self.engine

    def capture(self, label=None, *, bookmark=False, force=False):
        if self.engine is None:
            raise StoryError('请先开始游戏')
        snapshot = self.engine.export()
        data = dict(self.data, points=list(self.data['points']))
        # A redraw or repeat observation never adds another checkpoint.
        if not force and label is None and data['current'] == snapshot:
            return data['active']
        # Persist current dialogue on every click. Archive navigable checkpoints
        # at decisions, popups, chapter entries, endings and explicit saves.
        # This keeps long novels from storing the whole history once per line.
        meaningful = (force or label is not None or self.engine.state['chapter_pending']
                      or self.engine.state['page_id'] == 'START' or self.engine.choices
                      or self.engine.popup or self.engine.state['ended'])
        if not bookmark and meaningful:
            kind = 'manual' if label is not None else 'chapter' if self.engine.state['chapter_pending'] else 'node'
            node = self.story.page(self.engine.state['page_id'], self.engine.state['chapter_id'])
            title = self.engine.chapter['title'] if kind == 'chapter' else node.get('title') or self.engine.page['text'][:32] or self.engine.state['page_id']
            point = {'id': f"cp-{len(data['points'])+1:04}", 'kind': kind, 'label': label or title,
                     'parent': data['active'], 'created_at': datetime.now(timezone.utc).isoformat(), 'snapshot': snapshot}
            data['points'].append(point)
            data['active'] = point['id']
        data['current'] = snapshot
        data['segment'] = [self.engine.observe()]
        self._commit(data)
        return data['active']

    def apply(self, operation, *args):
        if self.engine is None:
            raise StoryError('请先开始游戏')
        before = self.engine.export()
        try:
            result = getattr(self.engine, operation)(*args)
            self.capture(bookmark=operation == 'toggle_bookmark')
            return result
        except Exception:
            self.engine.restore(before)
            raise

    def load(self, point_id):
        point = next((p for p in self.data['points'] if p['id'] == point_id), None)
        if point is None:
            raise StoryError('存档点不存在或尚未到达')
        candidate = Engine(self.story, initialize=False)
        candidate.restore(point['snapshot'])
        data = deepcopy(self.data)
        data.update(current=candidate.export(), active=point_id, segment=[candidate.observe()])
        self._commit(data)
        self.engine = candidate
        return candidate

    def import_snapshot(self, snapshot):
        candidate = Engine(self.story, initialize=False)
        candidate.restore(snapshot)
        previous, active = self.engine, self.data['active']
        self.engine, self.data['active'] = candidate, None
        try:
            self.capture('读取手动存档')
        except Exception:
            self.engine, self.data['active'] = previous, active
            raise
        return candidate

    def set_segment(self, segment):
        data = deepcopy(self.data)
        data['segment'] = deepcopy(segment)
        self._commit(data)

    def points(self):
        return [{k: p[k] for k in ('id', 'kind', 'label', 'parent', 'created_at')} | {
            'chapter_id': p['snapshot']['state']['chapter_id'], 'page_id': p['snapshot']['state']['page_id'],
            'at_current_state': p['id'] == self.data['active']
        } for p in self.data['points']]

    def flowchart(self):
        from .flowchart import chapter_tree
        return chapter_tree(self.story, self.data['points'], self.data['current'])
