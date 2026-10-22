"""Story selection and permanent milestones, separate from character knowledge."""
import json
from pathlib import Path

from .story import Story, StoryError
from .session import Session, atomic_json

DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / 'data/stories.json'


class Library:
    def __init__(self, directory, catalog=DEFAULT_CATALOG):
        self.directory = Path(directory)
        self.catalog = Path(catalog)
        data = json.loads(self.catalog.read_text(encoding='utf-8'))
        self.title = data['title']
        self.entries = {entry['id']: entry for entry in data['stories']}
        self.stories = {key: Story.load(self.catalog.parent / entry['file']) for key, entry in self.entries.items()}
        for entry in self.entries.values():
            rule = entry.get('unlock')
            if rule:
                self.stories[rule['story']].chapter(rule['chapter'])
        self.path = self.directory / 'library.json'
        self.progress = {'version': 1, 'selected': 'visitor', 'unlocked': ['visitor']}
        if self.path.exists():
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(saved, dict) or set(saved) != set(self.progress) or saved['version'] != 1
                    or saved['selected'] not in self.entries or not isinstance(saved['unlocked'], list)
                    or any(key not in self.entries for key in saved['unlocked']) or 'visitor' not in saved['unlocked']):
                raise StoryError('故事解锁记录无效，请保留文件后检查 library.json')
            self.progress = saved

    def unlocked(self, key):
        if key not in self.entries:
            raise StoryError('故事不存在')
        return key in self.progress['unlocked']

    def popup(self, key):
        action = self.entries[key]['locked_popup']
        return {'title': action['title'], 'text': action['value'], 'text_spans': []}

    def cards(self):
        return [{'id': key, 'name': entry['name'], 'unlocked': self.unlocked(key),
                 'status': '可游玩' if self.unlocked(key) else '未解锁'} for key, entry in self.entries.items()]

    def session_dir(self, key):
        return self.directory / key

    def session(self, key, *, persist=True):
        if not self.unlocked(key):
            raise StoryError(self.popup(key)['text'])
        return Session(self.stories[key], self.session_dir(key) / 'session.json', persist=persist)

    def record(self, key, session):
        """Only called after a successful GUI operation / CLI transaction."""
        if not self.unlocked(key):
            raise StoryError('故事尚未解锁')
        progress = dict(self.progress, selected=key, unlocked=list(self.progress['unlocked']))
        visited = {o['chapter_id'] for o in session.engine.observations} if session.engine else set()
        for target, entry in self.entries.items():
            rule = entry.get('unlock')
            if rule and rule['story'] == key and rule['chapter'] in visited and target not in progress['unlocked']:
                progress['unlocked'].append(target)
        if progress != self.progress or not self.path.exists():
            atomic_json(self.path, progress)
            self.progress = progress


def production_key(path):
    """Explicit production file paths still go through the unlock gate."""
    if path is not None:
        for key in ('visitor', 'employee'):
            if Path(path).resolve() == (DEFAULT_CATALOG.parent / f'{key}.json').resolve():
                return key
    return None
