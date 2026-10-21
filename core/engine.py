"""Sequential node execution with story-local state and recorded callback results."""
from copy import deepcopy
from contextlib import redirect_stdout
import sys

from .story import StoryError, matches, json_copy, duration
from .richtext import parse_rich


class Engine:
    SAVE_VERSION = 5
    MAX_ACTIONS = 100_000
    MAX_BATCH = 1000

    def __init__(self, story, *, initialize=True, receipts=None):
        self.story = story
        self.state = {'chapter_id': story.initial_chapter, 'chapter_pending': True,
                      'page_id': 'START', 'variables': deepcopy(story.variables),
                      'background': None, 'characters': {}, 'music': None, 'ended': False,
                      'rulebooks': {}, 'bookmarks': [], 'inventory': {}, 'achievements': {}}
        self.history, self.actions, self.calls, self.observations = [], [], [], []
        self._cached_calls = receipts
        self._page = {'id': self.state['page_id'], 'text': '', 'speaker': ''}
        self._resume = []
        if initialize:
            for definition in story.achievement_definitions:
                self._register_achievement(definition)
            self._enter_chapter(story.initial_chapter)
            self._finish()

    @property
    def page(self):
        return self._page

    @property
    def popup(self):
        return deepcopy(self.page.get('popup'))

    @property
    def choices(self):
        return [] if self.state['ended'] or self.popup else [c for c in self.page.get('choices', [])
                if matches(c.get('when', {}), self.state['variables'])]

    @property
    def item_uses(self):
        if self.state['ended'] or self.state['chapter_pending'] or self.popup:
            return []
        return [{'item_id': item_id} for item_id, count in self.state['inventory'].items()
                if self.story.item_actions.get(item_id) and count >= max(1, self.story.item_consumes.get(item_id, 0))]

    @property
    def is_decision(self):
        return not self.state['ended'] and bool(self.popup or self.state['chapter_pending'] or self.choices or self.item_uses)

    @property
    def can_advance(self):
        return not self.state['ended'] and not self.choices

    @property
    def chapter(self):
        return self.story.chapter(self.state['chapter_id'])

    @property
    def achievements(self):
        return deepcopy(list(self.state['achievements'].values()))

    def _register_achievement(self, definition):
        existing = self.state['achievements'].get(definition['id'])
        if existing and any(existing[k] != definition[k] for k in ('title', 'description')):
            raise StoryError('成就 ID 重复且定义不同')
        if not existing:
            self.state['achievements'][definition['id']] = deepcopy(definition) | {'completed': False}

    def _enter_chapter(self, chapter_id):
        chapter = self.story.chapter(chapter_id)
        self.state.update(chapter_id=chapter_id, chapter_pending=True, page_id='START',
                          background=chapter.get('background'), characters={}, music=None, ended=False)
        self._resume = []
        self._blank()
        for definition in chapter.get('achievements', []):
            self._register_achievement(definition)

    def _blank(self):
        self._page = {'id': self.state['page_id'], 'text': '', 'speaker': ''}

    def _end(self):
        self.state.update(page_id='END', ended=True)
        self._page['id'] = 'END'
        self._page.pop('choices', None)
        self._resume = []

    def observe(self):
        return {'chapter_id': self.state['chapter_id'], 'chapter_title': self.chapter['title'],
                'chapter_pending': self.state['chapter_pending'], 'page_id': self.state['page_id'], 'speaker': self.page.get('speaker', ''),
                'text': self.page.get('text', ''), 'rule_updates': deepcopy(self.page.get('rules', [])),
                **({'popup': self.popup} if self.popup else {}),
                'text_spans': json_copy(self.page.get('text_spans', [])),
                'new_achievements': deepcopy(self.page.get('new_achievements', [])),
                **({'audio': {'music': None if self.state['ended'] else self.state['music'],
                              'voice': None if self.state['ended'] else self.page.get('voice'),
                              'sound': None if self.state['ended'] else self.page.get('sound')}}
                   if self.state['music'] or 'voice' in self.page or 'sound' in self.page else {}),
                'visual': deepcopy({'background': self.state['background'], 'characters': self.state['characters']})}

    def _finish(self):
        if 'choices' in self.page and not self.choices and not self.state['ended'] and not self.popup:
            raise StoryError('当前 decision 没有可见选项，请提供可用分支')
        self.history.append({'chapter_id': self.state['chapter_id'], 'page_id': self.state['page_id'], 'speaker': self.page.get('speaker', ''),
                             'text': self.page.get('text', ''), 'choice': None,
                             **({'popup': self.popup} if self.popup else {})})
        self.observations.append(self.observe())

    def _call(self, spec):
        name, args = self.story.function_spec(spec)
        context = {'chapter_id': self.state['chapter_id'], 'page_id': self.state['page_id'], 'inventory': deepcopy(self.state['inventory'])}
        request = {'name': name, 'args': args, 'context': context, 'before': deepcopy(self.state['variables'])}
        if self._cached_calls is not None:
            index = len(self.calls)
            if index >= len(self._cached_calls):
                raise StoryError('存档缺少函数执行记录')
            receipt = deepcopy(self._cached_calls[index])
            if not isinstance(receipt, dict) or set(receipt) != {'request', 'state', 'actions'} or receipt['request'] != request:
                raise StoryError('存档函数执行记录与路径不匹配')
        else:
            state = deepcopy(self.state['variables'])
            try:
                with redirect_stdout(sys.stderr):
                    result = getattr(self.story.script, name)(state, deepcopy(args), deepcopy(context))
                receipt = {'request': request, 'state': json_copy(state),
                           'actions': json_copy([] if result is None else result)}
            except Exception as exc:
                raise StoryError(f'故事函数 {name} 执行失败：{exc}') from exc
        if not isinstance(receipt['state'], dict):
            raise StoryError('函数执行后的 state 必须是字典')
        self.story.validate_actions(receipt['actions'], chapter_id=self.state['chapter_id'])
        self.state['variables'] = json_copy(receipt['state'])
        self.calls.append(receipt)
        return deepcopy(receipt['actions'])

    def _execute(self, actions):
        self.story.validate_actions(actions, chapter_id=self.state['chapter_id'])
        queue = deepcopy(actions)
        count = 0
        while queue:
            count += 1
            if count > self.MAX_BATCH:
                raise StoryError('连续 action 超过 1000 条，可能存在 jump 或函数循环')
            a = queue.pop(0)
            p = a.get('property', 'function')
            if not matches(a.get('when', {}), self.state['variables']):
                continue
            # Item.function is its use handler, not an acquisition callback.
            if 'function' in a and p != 'item':
                continuation = {k: v for k, v in a.items() if k != 'function'}
                returned = self._call(a['function'])
                queue = returned + ([continuation] if p != 'function' else []) + queue
                continue
            if p == 'function':
                queue = self._call(a['value']) + queue
            elif p == 'jump':
                target = a['value']
                self._resume = []
                self._page.pop('choices', None)
                if target == 'END':
                    self._end()
                    break
                self.state['page_id'] = target
                self._page['id'] = target
                queue = deepcopy(self.story.page(target, self.state['chapter_id'])['actions'])
            elif p == 'chapter':
                self._enter_chapter(a['value'])
                break
            elif p == 'achievement':
                if a['options'] == 'register':
                    self._register_achievement(a['value'])
                else:
                    achievement = self.state['achievements'].get(a['value'])
                    if achievement is None:
                        raise StoryError('不能完成尚未注册的成就')
                    if not achievement['completed']:
                        achievement['completed'] = True
                        self._page.setdefault('new_achievements', []).append(achievement['title'])
            elif p == 'popup':
                text, spans = parse_rich(a['value'])
                self._page['popup'] = {'title': a.get('title', '提示'), 'text': text,
                    'text_spans': [{'start': start, 'end': end, 'color': list(color)} for start, end, color in spans]}
                self._page['pending_actions'] = queue
                break
            elif p == 'dialogue':
                text, spans = parse_rich(a['value'])
                offset = len(self._page['text']) + bool(self._page['text'])
                self._page['text'] += ('\n' if self._page['text'] else '') + text
                self._page['speaker'] = a.get('speaker', '')
                self._page.setdefault('text_spans', []).extend(
                    {'start': start + offset, 'end': end + offset, 'color': color} for start, end, color in spans)
            elif p in ('background', 'character'):
                value = None if a.get('options') == 'hide' else a.get('value')
                slot = a.get('slot', 'center')
                if p == 'background':
                    self.state['background'] = value
                elif value is None:
                    self.state['characters'].pop(slot, None)
                else:
                    self.state['characters'][slot] = value
                if a.get('options') in ('fade in', 'zoom in'):
                    self._page.setdefault('animations', []).append({'property': p, 'slot': slot,
                        'type': a['options'], 'duration': duration(a.get('args', 0.6))})
            elif p in ('music', 'voice', 'sound'):
                value = None if a.get('options') == 'stop' else a.get('value')
                (self.state if p == 'music' else self._page)[p] = value
            elif p == 'effect':
                self._page['effect'] = deepcopy(a.get('value'))
            elif p == 'decision':
                if 'choices' in self._page:
                    raise StoryError('同一批 actions 只能展示一组 decision')
                self._page['choices'] = deepcopy(a['value'])
            elif p == 'item':
                item_id = self.story.item_id(a)
                current = self.state['inventory'].get(item_id, 0)
                current += a.get('count', 1) * (1 if a['options'] == 'get' else -1)
                if current < 0:
                    raise StoryError('物品数量不足')
                if current:
                    self.state['inventory'][item_id] = current
                else:
                    self.state['inventory'].pop(item_id, None)
            elif p == 'rules':
                update = a['value']
                book = self.state['rulebooks'].setdefault(update['book_id'], {'title': update['title'], 'entries': {}})
                book['title'] = update['title']
                book['entries'].update({entry['id']: entry['text'] for entry in update['entries']})
                self._page.setdefault('rules', []).append(deepcopy(update))

    def _transaction(self, action, operation):
        # Replays run in a disposable candidate; failures never affect the live
        # engine. Avoid copying an ever-growing history at every replayed click.
        if self._cached_calls is not None:
            self._record(action)
            operation()
            return True
        backup = {key: deepcopy(getattr(self, key)) for key in ('state', '_page', '_resume')}
        # These logs are append-only, except for the choice on the last history
        # row. Retain old records, copying only the row that can be changed.
        for key in ('history', 'actions', 'calls', 'observations'):
            backup[key] = list(getattr(self, key))
        if backup['history']:
            backup['history'][-1] = deepcopy(backup['history'][-1])
        try:
            self._record(action)
            operation()
            return True
        except Exception:
            for key, value in backup.items():
                setattr(self, key, value)
            raise

    def advance(self):
        if not self.can_advance:
            return False
        def operation():
            if self.popup:
                self._page.pop('popup')
                remaining = self._page.pop('pending_actions')
                for key in ('voice', 'sound', 'effect', 'animations', 'rules', 'new_achievements'):
                    self._page.pop(key, None)
                self._execute(remaining)
                self._resume_item_if_empty()
                self._finish()
                return
            if self.state['chapter_pending']:
                self.state['chapter_pending'] = False
                self._blank()
                self._execute(self.story.page('START', self.state['chapter_id'])['actions'])
                self._finish()
                return
            if self._resume:
                self._page = self._resume.pop()
                self._page.pop('voice', None)
                self._page.pop('sound', None)
                self._page.pop('effect', None)
                self._page.pop('animations', None)
                self._page.pop('rules', None)
                self._page.pop('new_achievements', None)
                self._finish()
                return
            pages = self.chapter['contents']
            index = self.story.node_indexes[self.state['chapter_id']][self.state['page_id']] + 1
            if index == len(pages):
                raise StoryError('剧情已到列表末尾但未到 END，请配置 jump 到 END')
            if pages[index]['id'] == 'END':
                self._end()
                for key in ('voice', 'sound', 'effect', 'animations', 'rules', 'new_achievements'):
                    self._page.pop(key, None)
                self._finish()
                return
            node = pages[index]
            self.state['page_id'] = node['id']
            self._blank()
            self._execute(node['actions'])
            self._finish()
        return self._transaction({'kind': 'advance'}, operation)

    def choose(self, index):
        choices = self.choices
        if type(index) is not int or not 0 <= index < len(choices):
            raise StoryError('无效的选项编号')
        choice = choices[index]
        def operation():
            self.history[-1]['choice'] = choice['text']
            self._blank()
            actions = ([{'function': choice['function']}] if 'function' in choice else []) + deepcopy(choice.get('actions', []))
            if 'next_id' in choice:
                actions.append({'property': 'jump', 'value': choice['next_id']})
            self._execute(actions)
            self._finish()
        return self._transaction({'kind': 'choose', 'index': index}, operation)

    def use_item(self, item_id):
        if not isinstance(item_id, str) or not any(op['item_id'] == item_id for op in self.item_uses):
            raise StoryError('未持有该物品、数量不足，或物品没有使用动作')
        def operation():
            self.history[-1]['choice'] = f'使用物品：{self.story.items[item_id].name}'
            self._resume.append(deepcopy(self.page))
            self._blank()
            remaining = self.state['inventory'][item_id] - self.story.item_consumes.get(item_id, 0)
            if remaining:
                self.state['inventory'][item_id] = remaining
            else:
                del self.state['inventory'][item_id]
            self._execute(self.story.item_actions[item_id])
            self._resume_item_if_empty()
            self._finish()
        return self._transaction({'kind': 'use_item', 'item_id': item_id}, operation)

    def _resume_item_if_empty(self):
        if not self.page['text'] and not self.page.get('choices') and not self.popup and self._resume and not self.state['ended']:
            transient = ('voice', 'sound', 'effect', 'animations', 'rules', 'new_achievements')
            events = {key: deepcopy(self.page[key]) for key in transient if key in self.page}
            self._page = self._resume.pop()
            for key in transient:
                self._page.pop(key, None)
            self._page.update(events)

    def export(self):
        return deepcopy({'version': self.SAVE_VERSION, 'story': self.story.fingerprint,
                         'state': self.state, 'history': self.history, 'actions': self.actions,
                         'calls': self.calls, 'view': self.page, 'resume': self._resume})

    @classmethod
    def replay(cls, story, actions, calls, *, complete=True):
        if not isinstance(actions, list) or len(actions) > cls.MAX_ACTIONS or not isinstance(calls, list):
            raise StoryError('存档操作或函数记录无效')
        candidate = cls(story, receipts=calls)
        for action in actions:
            if action == {'kind': 'advance'}:
                if not candidate.advance():
                    raise StoryError('存档包含非法推进')
            elif isinstance(action, dict) and set(action) == {'kind', 'index'} and action['kind'] == 'choose':
                candidate.choose(action['index'])
            elif isinstance(action, dict) and set(action) == {'kind', 'item_id'} and action['kind'] == 'use_item':
                candidate.use_item(action['item_id'])
            elif isinstance(action, dict) and set(action) == {'kind', 'reference'} and action['kind'] == 'bookmark':
                candidate.toggle_bookmark(action['reference'])
            else:
                raise StoryError('存档包含未知操作')
        if complete and len(candidate.calls) != len(calls):
            raise StoryError('存档含有多余函数记录')
        candidate._cached_calls = None
        return candidate

    def _replace(self, candidate):
        for key in ('state', 'history', 'actions', 'calls', 'observations', '_page', '_resume'):
            setattr(self, key, getattr(candidate, key))
        self._cached_calls = None

    def restore(self, payload):
        if not isinstance(payload, dict) or payload.get('version') != self.SAVE_VERSION or payload.get('story') != self.story.fingerprint:
            raise StoryError('存档版本或故事脚本已变化，无法恢复')
        if set(payload) != {'version', 'story', 'state', 'history', 'actions', 'calls', 'view', 'resume'}:
            raise StoryError('存档结构无效')
        candidate = self.replay(self.story, payload['actions'], payload['calls'])
        import json
        if json.dumps(candidate.export(), sort_keys=True) != json.dumps(payload, sort_keys=True):
            raise StoryError('存档状态与执行记录不一致')
        self._replace(candidate)

    def rollback(self):
        index = next((i for i in range(len(self.actions) - 1, -1, -1) if self.actions[i]['kind'] != 'bookmark'), None)
        if index is None:
            return False
        self._replace(self.replay(self.story, self.actions[:index], self.calls, complete=False))
        return True

    def _record(self, action):
        if len(self.actions) >= self.MAX_ACTIONS:
            raise StoryError("本次游玩步数达到上限，请开始新游戏")
        self.actions.append(action)

    @property
    def inventory(self):
        usable = {op['item_id'] for op in self.item_uses}
        return [{'id': item_id, 'name': self.story.items[item_id].name,
                 'description': self.story.items[item_id].description,
                 'icon': self.story.items[item_id].icon, 'count': count, 'usable': item_id in usable}
                for item_id, count in self.state['inventory'].items()]

    @property
    def rulebooks(self):
        return [{'id': book_id, 'title': book['title'], 'entries': [
            {'id': entry_id, 'text': text, 'bookmarked': f'{book_id}:{entry_id}' in self.state['bookmarks']}
            for entry_id, text in book['entries'].items()
        ]} for book_id, book in self.state['rulebooks'].items()]

    def toggle_bookmark(self, reference):
        if not isinstance(reference, str) or ':' not in reference:
            raise StoryError('书签格式为 book_id:entry_id')
        book_id, entry_id = reference.split(':', 1)
        if entry_id not in self.state['rulebooks'].get(book_id, {}).get('entries', {}):
            raise StoryError('不能给尚未获得的守则条目添加书签')
        self._record({'kind': 'bookmark', 'reference': reference})
        if reference in self.state['bookmarks']:
            self.state['bookmarks'].remove(reference)
            return False
        self.state['bookmarks'].append(reference)
        return True
