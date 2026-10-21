"""Story-owned scripts and the ordered actions format; no GUI dependencies."""
from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import sys

from .items import load_items


class StoryError(ValueError):
    """Invalid story data, state, or player operation."""


def matches(condition, variables):
    return all(k in variables and type(variables[k]) is type(v) and variables[k] == v
               for k, v in condition.items())


PROPERTIES = ('background', 'character', 'dialogue', 'music', 'voice',
              'sound', 'effect', 'decision', 'item', 'rules', 'function', 'jump', 'chapter', 'achievement', 'popup')


def json_copy(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (ValueError, TypeError, OverflowError) as exc:
        raise StoryError('故事状态和函数结果必须可以保存为 JSON') from exc


def duration(value):
    if isinstance(value, str) and value.endswith('s'):
        try:
            value = float(value[:-1])
        except ValueError:
            pass
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 30:
        raise StoryError('动画 args 需要 (0, 30] 秒数，例如 0.5 或 "0.5s"')
    return value


class Story:
    def __init__(self, document, root):
        if not isinstance(document, dict):
            raise StoryError('剧情必须是包含 StoryName、chapters 的 JSON 对象')
        self.root = Path(root).resolve()
        self._keys(document, {'StoryName', 'script', 'chapters', 'items', 'title', 'achievements'}, '故事')
        if not isinstance(document.get('StoryName'), str) or not document['StoryName'].strip():
            raise StoryError('故事需要非空 StoryName')
        self.name = document['StoryName']
        self.title = deepcopy(document.get('title', {}))
        if not isinstance(self.title, dict):
            raise StoryError('title 必须是对象')
        self._keys(self.title, {'subtitle', 'background'}, 'title')
        if not isinstance(self.title.get('subtitle', ''), str):
            raise StoryError('title.subtitle 必须是字符串')
        if self.title.get('background') is not None:
            self.asset(self.title['background'])
        self.chapters = deepcopy(document.get('chapters'))
        if not isinstance(self.chapters, list) or not self.chapters:
            raise StoryError('chapters 必须是非空章节列表')
        self.by_chapter, self.node_indexes = {}, {}
        for chapter in self.chapters:
            if not isinstance(chapter, dict):
                raise StoryError('章节必须是对象')
            self._keys(chapter, {'id', 'title', 'subtitle', 'description', 'ending', 'background', 'contents', 'achievements'}, 'chapter')
            if not all(isinstance(chapter.get(k), str) and chapter[k].strip() for k in ('id', 'title')):
                raise StoryError('章节需要非空 id 和 title')
            chapter_id = chapter['id']
            if chapter_id in self.by_chapter:
                raise StoryError(f'重复章节 id：{chapter_id}')
            if not isinstance(chapter.get('subtitle', ''), str):
                raise StoryError('章节 subtitle 必须是字符串')
            if not isinstance(chapter.get('description', ''), str):
                raise StoryError('章节 description 必须是字符串')
            if 'ending' in chapter and chapter['ending'] not in ('normal', 'death'):
                raise StoryError('章节 ending 只支持 normal/death；普通章节省略此字段')
            if chapter.get('background') is not None:
                self.asset(chapter['background'])
            pages = chapter.get('contents')
            if not isinstance(pages, list) or not pages:
                raise StoryError('章节 contents 必须是非空节点列表')
            indexes = {}
            for i, page in enumerate(pages):
                if not isinstance(page, dict) or not isinstance(page.get('id'), str) or not page['id']:
                    raise StoryError('每个节点需要非空字符串 id')
                self._keys(page, {'id', 'title', 'actions'}, 'node')
                if not isinstance(page.get('title', ''), str):
                    raise StoryError('节点 title 必须是字符串')
                if page['id'] in indexes:
                    raise StoryError(f"章节 {chapter_id} 内重复节点 id：{page['id']}")
                indexes[page['id']] = i
            for boundary in ('START', 'END'):
                if boundary not in indexes:
                    raise StoryError(f'章节 {chapter_id} 缺少 {boundary} 节点 ID')
                pages[indexes[boundary]].setdefault('actions', [])
            if pages[indexes['END']]['actions'] != []:
                raise StoryError('END 的 actions 必须为空；结束对白请写在 END 之前')
            self.by_chapter[chapter_id] = chapter
            self.node_indexes[chapter_id] = indexes
        self.initial_chapter = self.chapters[0]['id']
        self.achievement_definitions = deepcopy(document.get('achievements', []))
        if not isinstance(self.achievement_definitions, list) or any(not isinstance(c.get('achievements', []), list) for c in self.chapters):
            raise StoryError('achievements 必须是成就定义列表')
        declarations = self.achievement_definitions + [a for c in self.chapters for a in c.get('achievements', [])]
        for a in declarations:
            self.validate_achievement(a)
        self.script = None
        script_bytes = b''
        if document.get('script'):
            path = self.asset(document['script'])
            if path.suffix != '.py':
                raise StoryError('script 必须指向 Python 文件')
            script_bytes = path.read_bytes()
            name = '_story_' + hashlib.sha256(str(path).encode() + script_bytes).hexdigest()
            spec = importlib.util.spec_from_file_location(name, path)
            self.script = importlib.util.module_from_spec(spec)
            sys.modules[name] = self.script
            # Compile the selected source directly: do not accept stale same-second .pyc files.
            try:
                with redirect_stdout(sys.stderr):
                    exec(compile(script_bytes, str(path), 'exec'), self.script.__dict__)
            except Exception as exc:
                raise StoryError(f'无法导入故事脚本：{exc}') from exc
        self.variables = json_copy(getattr(self.script, 'INITIAL_STATE', {}))
        if not isinstance(self.variables, dict):
            raise StoryError('脚本 INITIAL_STATE 必须是字典')
        definitions = deepcopy(document.get('items', []))
        if not isinstance(definitions, list):
            raise StoryError('items 必须是列表')
        self.item_actions = {}
        self.item_consumes = {}
        normalized = []
        for definition in definitions:
            if not isinstance(definition, dict):
                raise StoryError('物品定义必须是对象')
            self._keys(definition, {'id', 'name', 'description', 'icon', 'on_use', 'consume'}, 'item')
            normalized.append({k: v for k, v in definition.items() if k not in ('on_use', 'consume')})
            self.item_actions[definition.get('id')] = deepcopy(definition.get('on_use', []))
            self.item_consumes[definition.get('id')] = definition.get('consume', 0)
        # Inline get definitions may occur in a branch or another item's on_use actions.
        def collect(actions):
            if not isinstance(actions, list):
                return
            for action in actions:
                if not isinstance(action, dict):
                    continue
                if action.get('property') == 'item' and action.get('options') == 'get' and 'name' in action:
                    item_id = action.get('id', action['name'])
                    entry = {'id': item_id, 'name': action['name'], 'description': action.get('desc', ''),
                             'icon': action.get('value')}
                    previous = next((d for d in normalized if d.get('id') == item_id), None)
                    if previous is not None and previous != entry:
                        raise StoryError(f'物品 {item_id} 重复定义不一致')
                    if previous is None:
                        normalized.append(entry)
                    use = deepcopy(action.get('on_use', []))
                    if action.get('function'):
                        use.insert(0, {'function': action['function']})
                    if item_id in self.item_actions and self.item_actions[item_id] != use:
                        raise StoryError(f'物品 {item_id} 的 on_use 定义不一致')
                    self.item_actions[item_id] = use
                    self.item_consumes[item_id] = action.get('consume', 0)
                collect(action.get('on_use', []))
                for choice in action.get('value', []) if action.get('property') == 'decision' and isinstance(action.get('value'), list) else []:
                    if isinstance(choice, dict):
                        collect(choice.get('actions', []))
        for chapter in self.chapters:
            for page in chapter['contents']:
                collect(page.get('actions'))
        self.items = load_items(normalized)
        for item in self.items.values():
            if item.icon:
                self.asset(item.icon)
            count = self.item_consumes.get(item.id, 0)
            if type(count) is not int or count < 0:
                raise StoryError('consume 必须是非负整数')
        for chapter in self.chapters:
            for page in chapter['contents']:
                self.validate_actions(page.get('actions'), chapter_id=chapter['id'])
        for actions in self.item_actions.values():
            self.validate_actions(actions)
        signature = ['chapters-v1', document, normalized, self.item_actions, self.item_consumes, self.variables]
        self.fingerprint = hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode() + script_bytes).hexdigest()

    def function_spec(self, spec):
        if isinstance(spec, str):
            spec = {'name': spec}
        if not isinstance(spec, dict):
            raise StoryError('function 需要函数名或 {name, args}')
        self._keys(spec, {'name', 'args'}, 'function')
        name = spec.get('name')
        if not isinstance(name, str) or name.startswith('_'):
            raise StoryError('function 需要公开函数名 name')
        function = getattr(self.script, name, None)
        if not inspect.isfunction(function) or function.__module__ != self.script.__name__:
            raise StoryError(f'故事脚本中不存在函数：{name}')
        try:
            inspect.signature(function).bind({}, {}, {})
        except TypeError as exc:
            raise StoryError(f'{name} 的签名必须接受 (state, args, context)') from exc
        return name, json_copy(spec.get('args', {}))

    def validate_actions(self, actions, depth=0, chapter_id=None):
        if depth > 20 or not isinstance(actions, list) or len(actions) > 1000:
            raise StoryError('actions 必须是列表，最多 1000 条，嵌套不能超过 20 层')
        for a in actions:
            if not isinstance(a, dict):
                raise StoryError('action 必须是对象')
            p = a.get('property', 'function' if 'function' in a else None)
            allowed = {'property', 'options', 'value', 'args', 'function', 'when'}
            allowed |= {'character': {'slot'}, 'dialogue': {'speaker'}, 'popup': {'title'}, 'decision': {'num'},
                        'item': {'id', 'name', 'desc', 'count', 'consume', 'on_use'}}.get(p, set())
            self._keys(a, allowed, 'action')
            if p not in PROPERTIES:
                raise StoryError(f'未知 property：{p}')
            if 'when' in a and not isinstance(a['when'], dict):
                raise StoryError('when 必须是变量相等条件字典')
            if 'function' in a:
                self.function_spec(a['function'])
            if p == 'function' and 'function' not in a:
                self.function_spec(a.get('value'))
            if p in ('background', 'character'):
                option = a.get('options', 'show')
                if option not in ('show', 'hide', 'fade in', 'zoom in'):
                    raise StoryError(f'{p} 不支持 options={option}')
                if option != 'hide' and a.get('value') is not None:
                    self.asset(a['value'])
                if option in ('fade in', 'zoom in'):
                    duration(a.get('args', 0.6))
                if p == 'character' and a.get('slot', 'center') not in ('left', 'center', 'right'):
                    raise StoryError('character.slot 需要 left/center/right')
            elif p == 'popup':
                if a.get('options', 'show') != 'show' or not isinstance(a.get('value'), str) or not isinstance(a.get('title', '提示'), str):
                    raise StoryError('popup 需要 show 和字符串 value / title')
                from .richtext import parse_rich
                if not parse_rich(a['value'])[0].strip():
                    raise StoryError('popup 消息不能为空')
            elif p == 'dialogue':
                if a.get('options', 'show') != 'show' or not isinstance(a.get('value'), str) or not isinstance(a.get('speaker', ''), str):
                    raise StoryError('dialogue 需要 show 和字符串 value / speaker')
                from .richtext import parse_rich
                parse_rich(a['value'])
            elif p in ('music', 'voice', 'sound'):
                if a.get('options', 'play') not in ('play', 'stop'):
                    raise StoryError(f'{p} 只支持 play/stop')
                if a.get('options') != 'stop' and a.get('value') is not None:
                    self.asset(a['value'])
            elif p == 'jump':
                if a.get('options', 'to') != 'to' or 'value' not in a:
                    raise StoryError('jump 需要 options=to 和目标 value')
                self._target(a['value'], 'jump', chapter_id)
            elif p == 'chapter':
                if a.get('options', 'to') != 'to' or not isinstance(a.get('value'), str) or a['value'] not in self.by_chapter:
                    raise StoryError('chapter.value 必须是已声明的章节 ID')
            elif p == 'achievement':
                if a.get('options') == 'register':
                    self.validate_achievement(a.get('value'))
                elif a.get('options') == 'complete':
                    if not isinstance(a.get('value'), str) or not a['value']:
                        raise StoryError('achievement.complete 需要成就 ID')
                else:
                    raise StoryError('achievement.options 需要 register/complete')
            elif p == 'decision':
                choices = a.get('value')
                if not isinstance(choices, list) or not 1 <= len(choices) <= 6:
                    raise StoryError('decision 需要 1 到 6 个选项')
                if 'num' in a and str(a['num']) != str(len(choices)):
                    raise StoryError('decision.num 必须与选项数量一致，可省略')
                for c in choices:
                    if not isinstance(c, dict):
                        raise StoryError('选项必须是对象')
                    self._keys(c, {'text', 'next_id', 'function', 'actions', 'when'}, 'decision')
                    if not isinstance(c.get('text'), str) or not c['text']:
                        raise StoryError('选项需要非空 text')
                    if 'next_id' in c:
                        self._target(c['next_id'], 'decision.next_id', chapter_id)
                    if not any(k in c for k in ('next_id', 'function', 'actions')):
                        raise StoryError('选项需要 next_id、function 或 actions')
                    if 'when' in c and not isinstance(c['when'], dict):
                        raise StoryError('选项 when 必须是字典')
                    if 'function' in c:
                        self.function_spec(c['function'])
                    self.validate_actions(c.get('actions', []), depth + 1, chapter_id)
            elif p == 'item':
                if a.get('options') not in ('get', 'remove'):
                    raise StoryError('item.options 需要 get/remove')
                item_id = self.item_id(a)
                if not isinstance(item_id, str) or item_id not in self.items:
                    raise StoryError('item 引用了未定义的物品')
                if type(a.get('count', 1)) is not int or a.get('count', 1) <= 0:
                    raise StoryError('item.count 必须是正整数')
                self.validate_actions(a.get('on_use', []), depth + 1)
            elif p == 'rules':
                self._validate_rules(a.get('value'))
            elif p == 'effect':
                self._validate_effect(a.get('value'))

    @staticmethod
    def item_id(action):
        return action.get('id', action.get('name', action.get('value')))

    @classmethod
    def load(cls, path):
        path = Path(path)
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise StoryError(f'无法读取剧情 {path}：{exc}') from exc
        return cls(document, path.parent)

    def asset(self, value: str) -> Path:
        if not isinstance(value, str) or not value:
            raise StoryError("素材路径必须是非空字符串")
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise StoryError(f"素材路径不能离开 data 目录：{value}")
        if not path.is_file():
            raise StoryError(f"找不到素材：{value}")
        return path

    @staticmethod
    def _keys(value, allowed, where):
        extra = set(value) - set(allowed)
        if extra:
            raise StoryError(f"{where} 存在未知字段：{', '.join(sorted(extra))}")

    def chapter(self, chapter_id):
        return self.by_chapter[chapter_id]

    def page(self, page_id, chapter_id):
        return self.chapter(chapter_id)['contents'][self.node_indexes[chapter_id][page_id]]

    def _target(self, value, where, chapter_id=None):
        indexes = [self.node_indexes[chapter_id]] if chapter_id else self.node_indexes.values()
        if not isinstance(value, str) or not any(value in index for index in indexes):
            raise StoryError(f'{where} 需要当前章节的节点 ID；结束请指定 END：{value}')

    @staticmethod
    def validate_achievement(value):
        if not isinstance(value, dict):
            raise StoryError('成就定义必须是对象')
        Story._keys(value, {'id', 'title', 'description'}, 'achievement')
        if not all(isinstance(value.get(k), str) and value[k].strip() for k in ('id', 'title', 'description')):
            raise StoryError('成就需要非空 id、title、description')

    def _validate_rules(self, update):
        if not isinstance(update, dict):
            raise StoryError('rules.value 必须是守则更新对象')
        self._keys(update, {'book_id', 'title', 'entries'}, 'rules')
        for key in ('book_id', 'title'):
            if not isinstance(update.get(key), str) or not update[key].strip():
                raise StoryError(f'守则需要非空 {key}')
        if ':' in update['book_id'] or update['book_id'] == '__bookmarks__':
            raise StoryError('book_id 不能包含冒号或使用 __bookmarks__')
        entries = update.get('entries')
        if not isinstance(entries, list) or not entries:
            raise StoryError('守则 entries 必须是非空列表')
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise StoryError('守则条目必须是对象')
            self._keys(entry, {'id', 'text'}, 'rules.entries')
            if not all(isinstance(entry.get(k), str) and entry[k].strip() for k in ('id', 'text')):
                raise StoryError('守则条目需要非空 id 和 text')
            if ':' in entry['id'] or entry['id'] in seen:
                raise StoryError('同次更新的守则条目 id 不能重复或包含冒号')
            seen.add(entry['id'])

    def _validate_effect(self, effect):
        if not isinstance(effect, dict):
            raise StoryError('effect.value 必须是特效对象')
        self._keys(effect, {'type', 'duration', 'blocking'}, 'effect')
        if effect.get('type') not in ('fade', 'flash', 'shake'):
            raise StoryError('effect.type 需要 fade/flash/shake')
        value = effect.get('duration', 0.6)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 30:
            raise StoryError('effect.duration 必须在 (0, 30] 秒之间')
        if 'blocking' in effect and type(effect['blocking']) is not bool:
            raise StoryError('effect.blocking 必须是布尔值')
