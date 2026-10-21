from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pygame
import pytest

from core import Engine as CoreEngine, Story
from core.story import StoryError
from core.richtext import parse_rich

ROOT = Path(__file__).resolve().parents[1]


def Engine(story, *, initialize=True):
    """Existing action tests start just after the explicit chapter title gate."""
    engine = CoreEngine(story, initialize=initialize)
    if initialize:
        engine.advance()
    return engine


def dialogue(text):
    return {'property': 'dialogue', 'value': text}


def make(tmp_path, nodes, script=None, items=None):
    nodes = deepcopy(nodes)
    if not any(node['id'] == 'START' for node in nodes):
        nodes.insert(0, {'id': 'START', 'actions': [{'property': 'jump', 'value': nodes[0]['id']}]})
    if not any(node['id'] == 'END' for node in nodes):
        nodes.append({'id': 'END', 'actions': []})
    document = {'StoryName': '测试', 'chapters': [{'id': 'one', 'title': '一', 'contents': nodes}]}
    if script:
        (tmp_path / 'story.py').write_text(script)
        document['script'] = 'story.py'
    if items:
        document['items'] = items
    (tmp_path / 'story.json').write_text(json.dumps(document, ensure_ascii=False))
    return Story.load(tmp_path / 'story.json')


def test_function_order_nested_state_and_decision_after_actions(tmp_path):
    story = make(tmp_path, [
        {'id': '1', 'actions': [{'function': 'step'}, dialogue('结果'),
                              {'property': 'decision', 'num': '1', 'value': [{'text': '继续', 'next_id': '2'}]},
                              {'function': {'name': 'step', 'args': {'n': 2}}}]},
        {'id': '2', 'actions': [dialogue('结束')]},
    ], "INITIAL_STATE = {'stats': {'visits': 0}}\ndef step(state,args,context):\n state['stats']['visits'] += args.get('n', 1)\n return [{'property':'dialogue','value':str(state['stats']['visits'])}]\n")
    engine = Engine(story)
    assert engine.page['text'] == '1\n结果\n3'
    assert engine.state['variables'] == {'stats': {'visits': 3}}
    assert len(engine.choices) == 1
    assert not engine.advance()
    engine.choose(0)
    assert engine.page['text'] == '结束' and not engine.state['ended']
    engine.advance()
    assert engine.state['ended']


def test_jump_replaces_remaining_queue_and_ends_at_end_id(tmp_path):
    story = make(tmp_path, [
        {'id': '1', 'actions': [dialogue('起点'), {'property': 'jump', 'options': 'to', 'value': '10000'}, dialogue('不能出现')]},
        {'id': '2', 'actions': [dialogue('也不能出现')]},
        {'id': '10000', 'actions': [dialogue('支线'), {'property': 'jump', 'value': 'END'}]},
        {'id': 'END', 'actions': []},
    ])
    engine = Engine(story)
    assert engine.state['page_id'] == 'END'
    assert engine.page['text'] == '起点\n支线'
    assert not engine.advance()
    assert engine.state['ended']


def test_item_any_node_resume_and_choice_function(tmp_path):
    story = make(tmp_path, [
        {'id': '1', 'actions': [dialogue('开场'), {'property': 'item', 'options': 'get', 'id': 'map', 'name': '地图', 'desc': '纸',
            'function': {'name': 'read', 'args': {}}, 'on_use': [dialogue('展开地图')]}]},
        {'id': '2', 'actions': [dialogue('岔路'), {'property': 'decision', 'value': [
            {'text': '已读地图', 'when': {'read': True}, 'function': 'choose', 'next_id': '3'},
            {'text': '离开', 'next_id': '3'}]}]},
        {'id': '3', 'actions': [dialogue('结束')]},
    ], "INITIAL_STATE={'read':False}\ndef read(state,args,context):\n state['read']=True\ndef choose(state,args,context):\n state['chosen']=context['page_id']\n")
    engine = Engine(story)
    engine.advance()
    assert len(engine.choices) == 1
    before = engine.export()
    engine.use_item('map')
    assert engine.page['text'] == '展开地图'
    assert not engine.choices
    saved = engine.export()
    engine.advance()  # return to the suspended decision, not its following node
    assert engine.state['page_id'] == '2' and engine.page['text'] == '岔路'
    assert len(engine.choices) == 2
    engine.choose(0)
    assert engine.state['variables']['chosen'] == '2'
    engine.restore(saved)
    assert engine.page['text'] == '展开地图'
    engine.rollback()
    assert engine.export() == before


def test_item_jump_abandons_interrupted_node_and_consumes(tmp_path):
    story = make(tmp_path, [
        {'id': '1', 'actions': [{'property': 'item', 'options': 'get', 'value': 'key'}, dialogue('锁') ]},
        {'id': '2', 'actions': [dialogue('普通路')]},
        {'id': '10000', 'actions': [dialogue('暗门')]},
    ], items=[{'id': 'key', 'name': '钥匙', 'description': '旧钥匙', 'consume': 1,
               'on_use': [{'property': 'jump', 'value': '10000'}]}])
    engine = Engine(story)
    engine.use_item('key')
    assert engine.page['text'] == '暗门' and not engine.inventory and not engine._resume
    engine.advance()
    assert engine.state['ended']
    engine.rollback()
    engine.rollback()
    assert engine.state['inventory'] == {'key': 1}


def test_restore_rollback_and_cli_reads_never_call_functions_again(tmp_path):
    script = "INITIAL_STATE={}\nCALLS=0\ndef increment(state,args,context):\n global CALLS\n CALLS+=1\n state['n']=state.get('n',0)+1\n"
    story = make(tmp_path, [{'id': '1', 'actions': [{'function': 'increment'}, dialogue('1')]},
                            {'id': '2', 'actions': [{'function': 'increment'}, dialogue('2')]}], script)
    engine = Engine(story)
    engine.advance()
    saved = engine.export()
    assert story.script.CALLS == 2
    fresh = Engine(story, initialize=False)
    fresh.restore(json.loads(json.dumps(saved)))
    assert story.script.CALLS == 2
    fresh.rollback()
    assert story.script.CALLS == 2 and fresh.state['variables']['n'] == 1
    fresh.advance()  # a new forward action really invokes it
    assert story.script.CALLS == 3
    corrupt = deepcopy(saved)
    corrupt['calls'][0]['request']['name'] = 'different'
    before = fresh.export()
    with pytest.raises(StoryError):
        fresh.restore(corrupt)
    assert fresh.export() == before


def test_function_failure_and_jump_cycle_are_atomic(tmp_path):
    story = make(tmp_path, [
        {'id': '1', 'actions': [{'property': 'decision', 'value': [
            {'text': '错误', 'function': 'fail', 'next_id': '2'}, {'text': '循环', 'next_id': '2'}]}]},
        {'id': '2', 'actions': [{'property': 'jump', 'value': '2'}]},
    ], "def fail(state,args,context):\n state['changed']=True\n raise ValueError('boom')\n")
    engine = Engine(story)
    before = engine.export()
    for index in (0, 1):
        with pytest.raises(StoryError):
            engine.choose(index)
        assert engine.export() == before


@pytest.mark.parametrize('action', [
    {'property': 'jump', 'value': 'missing'},
    {'property': 'START', 'function': 'unknown'},
    {'property': 'END', 'value': 'x'},
    {'property': 'decision', 'num': 2, 'value': [{'text': 'x', 'next_id': 'END'}]},
    {'property': 'dialogue', 'value': '<red>unclosed'},
    {'property': 'background', 'options': 'rotate', 'value': None},
    {'property': 'function', 'value': 'missing'},
    {'property': 'unknown'},
])
def test_action_validation(tmp_path, action):
    with pytest.raises(StoryError):
        make(tmp_path, [{'id': '1', 'actions': [action]}])


def test_script_change_invalidates_save(tmp_path):
    story = make(tmp_path, [{'id': '1', 'actions': [dialogue('x')]}], 'INITIAL_STATE={}\n')
    saved = Engine(story).export()
    (tmp_path / 'story.py').write_text('INITIAL_STATE={}\n# modified\n')
    changed = Story.load(tmp_path / 'story.json')
    with pytest.raises(StoryError):
        Engine(changed).restore(saved)


def test_rich_text_visible_offsets():
    text, spans = parse_rich('甲<red>乙<blue>丙</blue>丁</red>戊')
    assert text == '甲乙丙丁戊'
    assert [(s, e) for s, e, c in spans] == [(1, 4), (2, 3)]


def test_real_gui_color_animations_and_mid_dialogue_item_use(tmp_path):
    from gui.app import App
    story = make(tmp_path, [{'id': 'START', 'actions': [dialogue('请保管好'), {'property': 'item', 'options': 'get', 'value': 'map'}]}], "INITIAL_STATE={'map_reads':0}\ndef read(state,args,context):\n state['map_reads']+=1\n", items=[{'id':'map','name':'地图','description':'地图','on_use':[{'function':'read'}, dialogue('<red>请记住</red>')]}])
    app = App(story, tmp_path, muted=True)
    app.action("new_game")
    app.action("chapter_continue")
    try:
        assert app.revealed == 0
        app.action('inventory')
        app.render()
        assert any(button.action == 'use_item' for button in app.buttons)
        app.action('use_item', 'map')
        assert '请记住' in app.engine.page['text'] and '<red>' not in app.engine.page['text']
        assert app.engine.state['variables']['map_reads'] == 1
        app.revealed = app.chunk_length
        app.render()
        red = (191, 60, 48)
        assert any(app.canvas.get_at((x, y))[:3] == red for x in range(76, 1200) for y in range(610, 718))
        app.advance()
        assert app.engine.state['page_id'] == 'START' and '请保管好' in app.engine.page['text']
    finally:
        pygame.quit()


def test_cli_cross_process_global_item_and_load(tmp_path):
    base = [sys.executable, str(ROOT / 'game.py'), '--cli', '--story', str(ROOT / 'tests/fixtures/demo/story.json'),
            '--session-dir', str(tmp_path / 'session')]
    def run(*args):
        result = subprocess.run(base + list(args), capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    assert run()['status'] == 'chapter_intro'
    first = run('--continue')
    assert first['page_id'] == 'START'
    cp = first['auto_load_point']
    result = run('--use', 'map')
    assert '展开地图' in result['segment'][0]['text']
    assert run()['segment'] == result['segment']
    assert run('--continue')['page_id'] == 'START'
    assert run('--continue')['page_id'] == 'route'
    run('--choose', '帮兽医递送样本')
    assert run('--continue')['status'] == 'chapter_intro'
    assert run('--continue')['chapter_id'] == 'meadow'
    assert run('--use', 'goat_blood')['inventory'] == [i for i in first['inventory'] if i['id'] == 'map']
    run('--continue')
    assert run('--continue')['status'] == 'awaiting_choice'
    run('--choose', '按地图沿蓝色步道离园')
    assert run('--continue')['status'] == 'chapter_intro'
    run('--continue')
    run('--continue')
    assert run('--continue')['status'] == 'ended'
    assert run()['status'] == 'ended'
    loaded = run('--load', cp)
    assert loaded['page_id'] == 'START' and loaded['chapter_id'] == 'arrival'
    assert not next(a for a in loaded['achievements'] if a['id'] == 'home')['completed']


def test_cli_queries_do_not_repeat_initial_callback(tmp_path):
    counter = tmp_path / 'callback-count.txt'
    script = f"from pathlib import Path\nINITIAL_STATE={{}}\ndef start(state,args,context):\n p=Path({str(counter)!r})\n p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n state['started']=True\n"
    make(tmp_path, [{'id': '1', 'actions': [{'function': 'start'}, {'property': 'decision', 'value': [{'text': '结束', 'next_id': 'END'}]}]}], script)
    base = [sys.executable, str(ROOT / 'game.py'), '--cli', '--story', str(tmp_path / 'story.json'), '--session-dir', str(tmp_path / 'session')]
    assert subprocess.run(base, capture_output=True).returncode == 0
    assert not counter.exists()
    for args in (['--continue'], [], ['--list-load-point'], ['--load', 'cp-0002'], ['--inventory']):
        p = subprocess.run(base + args, capture_output=True, text=True)
        assert p.returncode == 0, p.stdout + p.stderr
        assert counter.read_text() == '1'
    p = subprocess.run(base + ['--new'], capture_output=True, text=True)
    assert p.returncode == 0 and counter.read_text() == '1'
    assert subprocess.run(base + ['--continue'], capture_output=True).returncode == 0
    assert counter.read_text() == '2'


def test_item_without_dialogue_preserves_new_effects(tmp_path):
    story = make(tmp_path, [{'id': '1', 'actions': [dialogue('原文'), {'property': 'item', 'options': 'get', 'value': 'lamp'}]}],
                 items=[{'id': 'lamp', 'name': '灯', 'description': '灯', 'on_use': [
                     {'property': 'effect', 'value': {'type': 'flash', 'duration': 1}}]}])
    engine = Engine(story)
    engine.use_item('lamp')
    assert engine.page['text'] == '原文'
    assert engine.page['effect']['type'] == 'flash'
    assert not engine._resume


def test_start_lookup_and_sequential_end_before_later_branches(tmp_path):
    story = make(tmp_path, [
        {'id': 'unused', 'actions': [{'function': 'fail'}]},
        {'id': 'START', 'actions': [dialogue('从这里开始')]},
        {'id': 'END'},
        {'id': '10000', 'actions': [{'function': 'fail'}]},
    ], "def fail(state,args,context):\n raise RuntimeError('不应执行')\n")
    engine = Engine(story)
    assert engine.state['page_id'] == 'START'
    assert engine.page['text'] == '从这里开始' and not engine.calls
    before = engine.export()
    engine.advance()
    assert engine.state['page_id'] == 'END' and engine.state['ended']
    assert not engine.advance() and not engine.choices and not engine.item_uses
    saved = engine.export()
    restored = Engine(story, initialize=False)
    restored.restore(json.loads(json.dumps(saved)))
    assert restored.export() == saved
    restored.rollback()
    assert restored.export() == before


@pytest.mark.parametrize('route', ['choice', 'function', 'item'])
def test_end_via_all_control_flow_routes(tmp_path, route):
    trigger = {
        'choice': {'property': 'decision', 'value': [{'text': '结束', 'next_id': 'END'}]},
        'function': {'property': 'decision', 'value': [{'text': '结束', 'function': 'finish'}]},
        'item': {'property': 'item', 'options': 'get', 'value': 'ticket'},
    }[route]
    story = make(tmp_path, [
        {'id': 'END', 'actions': []},
        {'id': 'START', 'actions': [dialogue('入口'), trigger]},
        {'id': 'later', 'actions': [dialogue('不应出现')]},
    ], "def finish(state,args,context):\n state['done']=True\n return [{'property':'jump','value':'END'}, {'property':'dialogue','value':'不应执行'}]\n",
        items=[{'id': 'ticket', 'name': '门票', 'description': '离园票', 'consume': 1,
                'on_use': [dialogue('离园'), {'property': 'jump', 'value': 'END'}, dialogue('不应执行')]}])
    engine = Engine(story)
    before = engine.export()
    engine.use_item('ticket') if route == 'item' else engine.choose(0)
    assert engine.state['ended'] and engine.state['page_id'] == 'END'
    assert '不应' not in engine.page['text'] and not engine._resume
    assert not engine.can_advance and not engine.is_decision
    restored = Engine(story, initialize=False)
    restored.restore(json.loads(json.dumps(engine.export())))
    assert restored.state['ended']
    restored.rollback()
    assert restored.export() == before


@pytest.mark.parametrize('nodes', [
    [{'id': '1', 'actions': []}, {'id': 'END'}],
    [{'id': 'START', 'actions': []}],
    [{'id': 'START'}, {'id': 'START'}, {'id': 'END'}],
    [{'id': 'START'}, {'id': 'END'}, {'id': 'END'}],
    [{'id': 'START'}, {'id': 'END', 'actions': [dialogue('不能放在终点')]}],
    [{'id': 'START', 'actions': [{'property': 'START'}]}, {'id': 'END'}],
    [{'id': 'START', 'actions': [{'property': 'END'}]}, {'id': 'END'}],
])
def test_boundary_contract_validation(tmp_path, nodes):
    with pytest.raises(StoryError):
        Story({'StoryName': 'test', 'chapters': [{'id': 'one', 'title': '一', 'contents': nodes}]}, tmp_path)


def test_cli_sequential_end_and_terminal_text_not_lost(tmp_path):
    make(tmp_path, [
        {'id': 'unused', 'actions': [dialogue('不能出现')]},
        {'id': 'START', 'actions': [dialogue('开头')]},
        {'id': 'closing', 'actions': [dialogue('终章内容'), {'property': 'jump', 'value': 'END'}]},
        {'id': 'END'},
        {'id': '10000', 'actions': [dialogue('不能出现')]},
    ])
    base = [sys.executable, str(ROOT / 'game.py'), '--cli', '--story', str(tmp_path / 'story.json'), '--session-dir', str(tmp_path / 'session')]
    def run(*args):
        p = subprocess.run(base + list(args), capture_output=True, text=True)
        assert p.returncode == 0, p.stdout + p.stderr
        return json.loads(p.stdout)
    assert run()['status'] == 'chapter_intro'
    first = run('--continue')
    assert first['status'] == 'ended' and first['page_id'] == 'END'
    assert [row['text'] for row in first['segment']] == ['开头', '终章内容']
    assert run() == first
    manual = run('--save', '结局')['manual_load_point']
    assert run('--load', manual)['status'] == 'ended'


def test_gui_terminal_dialogue_can_still_be_paged(tmp_path):
    from gui.app import App
    story = make(tmp_path, [{'id': 'START', 'actions': [dialogue('结局仍然可以逐页阅读。' * 100),
                                                         {'property': 'jump', 'value': 'END'}]}, {'id': 'END'}])
    app = App(story, tmp_path / 'saves', muted=True)
    app.action('new_game')
    app.action('chapter_continue')
    try:
        assert app.engine.state['ended'] and len(app.chunks) > 1
        before = app.engine.export()
        for chunk in range(len(app.chunks)):
            assert app.chunk_index == chunk
            app.advance()
            assert app.complete
            app.advance()
        assert app.all_text_read and app.engine.export() == before
    finally:
        pygame.quit()


@pytest.mark.parametrize('document', [
    [{'id': 'START', 'text': '旧页面'}],
    {'StoryName': 'x', 'Chapter': '1', 'contents': [{'id': 'START', 'content': [{'attribute': '文字', 'text': '旧内容'}]}, {'id': 'END'}]},
    {'StoryName': 'x', 'Chapter': '1', 'contents': [{'id': 'START', 'actions': [], 'next': 'END'}, {'id': 'END'}]},
    {'StoryName': 'x', 'Chapter': '1', 'contents': [{'id': 'START', 'actions': [{'property': 'jump', 'value': None}]}, {'id': 'END'}]},
])
def test_only_current_json_contract_is_accepted(tmp_path, document):
    path = tmp_path / 'story.json'
    path.write_text(json.dumps(document))
    with pytest.raises(StoryError):
        Story.load(path)


def test_no_implicit_end_after_last_node(tmp_path):
    story = make(tmp_path, [{'id': 'END'}, {'id': 'START', 'actions': [dialogue('缺少终点跳转')]}])
    engine = Engine(story)
    before = engine.export()
    with pytest.raises(StoryError, match='END'):
        engine.advance()
    assert engine.export() == before


def test_core_and_cli_import_without_gui_or_pygame():
    code = "import sys; from core import Story, Engine; import cli.app; e=Engine(Story.load('tests/fixtures/demo/story.json')); assert e.state['page_id']=='START'; assert 'pygame' not in sys.modules; assert not any(n=='gui' or n.startswith('gui.') for n in sys.modules)"
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_rules_bookmarks_and_failed_item_action_restore_atomically(tmp_path):
    def rules(entries):
        return {'property': 'rules', 'value': {'book_id': 'visitors', 'title': '游客守则', 'entries': entries}}
    story = make(tmp_path, [
        {'id': 'START', 'actions': [rules([{'id': '01', 'text': '原规则'}]), {'property': 'item', 'options': 'get', 'value': 'map'}]},
        {'id': 'second', 'actions': [rules([{'id': '01', 'text': '更新规则'}, {'id': '02', 'text': '新条目'}])]},
        {'id': 'END'},
    ], items=[{'id': 'map', 'name': '地图', 'description': '纸', 'consume': 1, 'on_use': [
        {'property': 'item', 'options': 'remove', 'value': 'map'}]}])
    engine = Engine(story)
    engine.toggle_bookmark('visitors:01')
    saved = engine.export()
    engine.advance()
    assert engine.rulebooks[0]['entries'][0] == {'id': '01', 'text': '更新规则', 'bookmarked': True}
    engine.rollback()
    assert engine.export() == saved
    with pytest.raises(StoryError):
        engine.use_item('map')
    assert engine.export() == saved
    with pytest.raises(StoryError):
        engine.toggle_bookmark('unseen:01')
    assert engine.export() == saved


def test_gui_menus_save_load_and_resized_clicks(tmp_path):
    from gui.app import App
    app = App(Story.load(ROOT / 'tests/fixtures/demo/story.json'), tmp_path / 'saves', muted=True)
    def click(name, value=None):
        app.render()
        button = next(b for b in app.buttons if b.action == name and b.value == value)
        x, y = button.rect.center
        x = app.viewport.x + round(x * app.viewport.width / 1280)
        y = app.viewport.y + round(y * app.viewport.height / 800)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)))
    try:
        app.screen = pygame.display.set_mode((900, 650), pygame.RESIZABLE)
        click('new_game')
        click('chapter_continue')
        click('popup_continue')
        app.render()
        assert {b.action for b in app.buttons} == {'settings', 'inventory', 'rules'}
        click('rules')
        click('bookmark', 'visitor:1')
        click('close')
        saved = app.engine.export()
        click('settings')
        click('save')
        click('save_slot', 1)
        app.session.apply('advance')
        app.sync_page()
        click('settings')
        click('load')
        click('load_slot', 1)
        assert app.engine.export() == saved and app.complete
        path = app.store.path(1)
        path.write_text('{bad json')
        app.action('load_slot', 1)
        assert app.engine.export() == saved and '失败' in app.notice
        click('settings')
        click('history')
        app.render()
    finally:
        pygame.quit()


def test_cli_read_queries_do_not_start_story_and_invalid_moves_do_not_commit(tmp_path):
    counter = tmp_path / 'calls.txt'
    make(tmp_path, [{'id': 'START', 'actions': [{'function': 'begin'}, {'property': 'decision', 'value': [{'text': '结束', 'next_id': 'END'}]}]}, {'id': 'END'}],
         f"def begin(state,args,context):\n from pathlib import Path\n Path({str(counter)!r}).write_text('called')\n")
    base = [sys.executable, str(ROOT / 'game.py'), '--cli', '--story', str(tmp_path / 'story.json'), '--session-dir', str(tmp_path / 'session')]
    for args in (['--list-load-point'], ['--inventory'], ['--rules']):
        result = subprocess.run(base + args, capture_output=True, text=True)
        assert json.loads(result.stdout)['ok'] is (args == ['--list-load-point'])
        assert not counter.exists()
    result = subprocess.run(base, capture_output=True, text=True)
    assert result.returncode == 0 and not counter.exists()
    result = subprocess.run(base + ['--continue'], capture_output=True, text=True)
    assert result.returncode == 0 and counter.exists()
    path = tmp_path / 'session/session.json'
    before = path.read_bytes()
    for args in (['--choose', '不存在'], ['--continue'], ['--use', 'map'], ['--load', 'missing']):
        result = subprocess.run(base + args, capture_output=True, text=True)
        assert result.returncode == 2 and not json.loads(result.stdout)['ok']
        assert path.read_bytes() == before


def test_media_channels_and_png_export_without_display(tmp_path):
    from gui.media import Media
    from cli.scene_export import SceneExporter
    story = Story.load(ROOT / 'tests/fixtures/demo/story.json')
    try:
        media = Media(story)
        assert media.enabled
        media.sync({'music': None, 'ended': False}, {'voice': 'audio/bell.wav', 'sound': 'audio/bell.wav'})
        assert pygame.mixer.Channel(0).get_sound() is not None
        assert pygame.mixer.Channel(1).get_sound() is not None
        media.sync({'music': None, 'ended': False}, {}, transient=False)
        assert pygame.mixer.Channel(0).get_sound() is None
        pygame.quit()
        assert not pygame.display.get_init()
        rows = SceneExporter(story, tmp_path).export([Engine(story).observe()])
        for key in ('background_image', 'scene_image'):
            assert Path(rows[0][key]).read_bytes().startswith(b'\x89PNG')
        assert not pygame.display.get_init() and not pygame.mixer.get_init()
    finally:
        pygame.quit()
