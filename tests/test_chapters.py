"""Chapter transitions, achievements, durable visited paths and full GUI routes."""
from copy import deepcopy
from pathlib import Path
import json

import pygame
import pytest

from core import Engine, Story, StoryError
from core.session import Session

ROOT = Path(__file__).resolve().parents[1]


def sample(tmp_path):
    (tmp_path / 'logic.py').write_text("INITIAL_STATE={'visits':0,'route':''}\nCALLS=0\ndef visit(state,args,context):\n global CALLS\n CALLS+=1\n state['visits']+=1\n state['last_chapter']=context['chapter_id']\ndef route(state,args,context):\n state['route']=args['route']\n")
    definition = {'id': 'travel', 'title': '旅行', 'description': '跨越章节'}
    document = {'StoryName': '两章', 'script': 'logic.py', 'achievements': [definition],
                'items': [{'id': 'map', 'name': '地图', 'description': '纸', 'on_use': [
                    {'property': 'achievement', 'options': 'complete', 'value': 'travel'}]}],
                'chapters': [
        {'id': 'a', 'title': '第一章', 'background': None, 'contents': [
            {'id': 'START', 'actions': [
                {'function': 'visit'}, {'property': 'item', 'options': 'get', 'value': 'map'},
                {'property': 'rules', 'value': {'book_id': 'rules', 'title': '守则', 'entries': [{'id': 'one', 'text': '保持安静'}]}},
                {'property': 'decision', 'value': [
                    {'text': route, 'function': {'name': 'route', 'args': {'route': route}}, 'actions': [{'property': 'chapter', 'value': 'b'}]}
                    for route in ('left', 'right')]}]}, {'id': 'END'}]},
        {'id': 'b', 'title': '第二章', 'subtitle': '新的地方', 'contents': [
            {'id': 'START', 'actions': [{'function': 'visit'}, {'property': 'achievement', 'options': 'complete', 'value': 'travel'}, {'property': 'dialogue', 'value': '已抵达'}]},
            {'id': 'END'}]}]}
    return Story(document, tmp_path), document


def test_chapter_gate_carries_state_and_exact_callback_receipts(tmp_path):
    story, _ = sample(tmp_path)
    engine = Engine(story)
    assert engine.state['chapter_pending'] and story.script.CALLS == 0
    engine.advance()
    engine.toggle_bookmark('rules:one')
    first = engine.export()
    engine.choose(0)
    entry = engine.export()
    assert engine.state['chapter_id'] == 'b' and engine.state['chapter_pending']
    assert engine.state['variables'] == {'visits': 1, 'route': 'left', 'last_chapter': 'a'}
    assert engine.state['inventory'] == {'map': 1}
    assert engine.state['bookmarks'] == ['rules:one'] and engine.rulebooks[0]['entries'][0]['text'] == '保持安静'
    assert not engine.achievements[0]['completed']
    assert not engine.item_uses
    engine.advance()
    assert story.script.CALLS == 2 and engine.state['variables']['visits'] == 2
    assert engine.state['variables']['last_chapter'] == 'b' and engine.achievements[0]['completed']
    engine.restore(entry)
    assert story.script.CALLS == 2 and not engine.achievements[0]['completed']
    engine.rollback()
    assert engine.export() == first and story.script.CALLS == 2
    engine.advance()  # a decision cannot be skipped
    assert engine.export() == first


def test_session_branches_are_separate_and_load_is_durable(tmp_path):
    story, _ = sample(tmp_path)
    path = tmp_path / 'session.json'
    session = Session(story, path)
    assert session.flowchart() == {'roots': [], 'nodes': []}
    session.start()
    assert session.points()[0]['kind'] == 'chapter'
    assert [c['chapter_id'] for c in session.flowchart()['nodes']] == ['a']
    session.apply('advance')
    source = session.data['active']
    session.apply('choose', 0)
    left = session.data['active']
    assert session.points()[-1]['kind'] == 'chapter'
    session.apply('advance')
    completed = session.data['active']
    session.load(source)
    session.apply('choose', 1)
    right = session.data['active']
    assert right != left
    chapter_nodes = [n for n in session.flowchart()['nodes'] if n['chapter_id'] == 'b']
    assert [n['parent'] for n in chapter_nodes if n['id'] in (left, right)] == ['cp-0001', 'cp-0001']
    session.load(left)
    assert session.engine.state['variables']['route'] == 'left'
    session.load(right)
    assert session.engine.state['variables']['route'] == 'right'
    assert not session.engine.achievements[0]['completed']
    calls = story.script.CALLS
    reloaded = Session(story, path)
    assert story.script.CALLS == calls and reloaded.data == session.data
    reloaded.load(completed)
    assert reloaded.engine.achievements[0]['completed']
    assert reloaded.engine.state['variables']['route'] == 'left'
    assert story.script.CALLS == calls


def test_new_game_at_initial_checkpoint_keeps_valid_archive(tmp_path):
    story, _ = sample(tmp_path)
    session = Session(story, tmp_path / 'session.json')
    session.start()
    session.start()
    assert len(session.points()) == 2
    assert session.points()[-1]['parent'] is None
    assert Session(story, session.path).data == session.data


def test_session_write_failure_does_not_change_live_progress(tmp_path, monkeypatch):
    story, _ = sample(tmp_path)
    session = Session(story, tmp_path / 'session.json')
    session.start()
    data, engine, disk = deepcopy(session.data), session.engine.export(), session.path.read_bytes()
    def fail(*args):
        raise OSError('磁盘不可用')
    monkeypatch.setattr('core.session.atomic_json', fail)
    with pytest.raises(OSError):
        session.apply('advance')
    assert session.data == data and session.engine.export() == engine and session.path.read_bytes() == disk
    with pytest.raises(OSError):
        session.start()
    assert session.data == data and session.engine.export() == engine


def test_register_complete_idempotence_and_item_toast(tmp_path):
    story, _ = sample(tmp_path)
    engine = Engine(story)
    engine.advance()
    engine.use_item('map')
    assert engine.page['new_achievements'] == ['旅行']
    assert engine.choices  # item has no dialogue, resumes immediately
    engine.use_item('map')
    assert not engine.page.get('new_achievements')
    engine.rollback()
    assert engine.achievements[0]['completed']
    engine.rollback()
    assert not engine.achievements[0]['completed']


@pytest.mark.parametrize('bad', [None, {}, 'a'])
def test_invalid_achievement_metadata(tmp_path, bad):
    _, doc = sample(tmp_path)
    doc['achievements'] = bad
    with pytest.raises(StoryError, match='achievements'):
        Story(doc, tmp_path)


@pytest.mark.parametrize('operation', ['direct', 'function', 'item'])
def test_chapter_action_all_entry_paths(tmp_path, operation):
    _, doc = sample(tmp_path)
    action = {'property': 'chapter', 'value': 'b'}
    if operation == 'function':
        with (tmp_path / 'logic.py').open('a') as stream:
            stream.write("\ndef transfer(state,args,context):\n return [{'property':'chapter','value':'b'}]\n")
        action = {'function': 'transfer'}
    if operation == 'item':
        doc['items'][0]['on_use'] = [action]
    else:
        doc['chapters'][0]['contents'][0]['actions'] = [action, {'property': 'dialogue', 'value': '不能执行'}]
    story = Story(doc, tmp_path)
    engine = Engine(story)
    engine.advance()
    if operation == 'item':
        engine.use_item('map')
    assert engine.state['chapter_id'] == 'b' and engine.state['chapter_pending']
    assert engine.page['text'] == '' and not engine._resume
    engine.advance()
    assert engine.page['text'] == '已抵达'
    engine.advance()
    assert engine.state['ended']


def test_scoped_jumps_and_chapter_background_reset(tmp_path):
    _, doc = sample(tmp_path)
    (tmp_path / 'bg.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"/>')
    doc['chapters'][1]['background'] = 'bg.svg'
    story = Story(doc, tmp_path)
    engine = Engine(story)
    engine.advance()
    engine.choose(0)
    assert engine.state['background'] == 'bg.svg'
    assert engine.state['characters'] == {} and engine.state['music'] is None
    doc['chapters'][0]['contents'][0]['actions'] = [{'property': 'jump', 'value': 'other'}]
    doc['chapters'][1]['contents'].insert(1, {'id': 'other', 'actions': []})
    with pytest.raises(StoryError, match='当前章节'):
        Story(doc, tmp_path)


@pytest.mark.parametrize('value', ['missing', [], None])
def test_invalid_chapter_destination(tmp_path, value):
    _, doc = sample(tmp_path)
    doc['chapters'][0]['contents'][0]['actions'] = [{'property': 'chapter', 'value': value}]
    with pytest.raises(StoryError, match='chapter.value'):
        Story(doc, tmp_path)


def test_achievement_action_registration_and_failure_atomicity(tmp_path):
    _, doc = sample(tmp_path)
    definition = {'id': 'new', 'title': '新成就', 'description': '发现'}
    doc['chapters'][0]['contents'][0]['actions'] = [
        {'property': 'achievement', 'options': 'register', 'value': definition},
        {'property': 'achievement', 'options': 'complete', 'value': 'new'}]
    engine = Engine(Story(doc, tmp_path))
    engine.advance()
    assert engine.achievements[-1] == definition | {'completed': True}
    engine.rollback()
    assert len(engine.achievements) == 1
    doc['chapters'][0]['contents'][0]['actions'].append({'property': 'achievement', 'options': 'complete', 'value': 'unknown'})
    engine = Engine(Story(doc, tmp_path))
    before = engine.export()
    with pytest.raises(StoryError, match='尚未注册'):
        engine.advance()
    assert engine.export() == before


def test_gui_complete_demo_flow_and_graph_branch_reload(tmp_path):
    from gui.app import App
    app = App(Story.load(ROOT / 'tests/fixtures/demo/story.json'), tmp_path, muted=True)
    def click(action, value=None):
        app.render()
        button = next(b for b in app.buttons if b.action == action and b.value == value)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.rect.center))
    def next_page():
        for _ in range(len(app.chunks) + 1):
            app.revealed = app.chunk_length
            if app.chunk_index == len(app.chunks) - 1:
                break
            app.advance()
        app.action('advance')
    try:
        assert app.scene == 'title' and app.engine is None
        click('new_game')
        assert app.scene == 'chapter' and app.session.points()[-1]['kind'] == 'chapter'
        click('chapter_continue')
        click('popup_continue')
        click('inventory')
        click('use_item', 'map')
        assert app.engine.achievements[1]['completed']
        next_page()  # resume arrival START
        next_page()  # entrance decision
        app.revealed = app.chunk_length
        click('choose', 1)  # walk without sample
        next_page()
        assert app.scene == 'chapter' and app.engine.state['chapter_id'] == 'meadow'
        click('chapter_continue')
        next_page()
        branch = app.session.data['active']
        app.revealed = app.chunk_length
        click('choose', 0)  # map route
        next_page()
        click('chapter_continue')
        next_page()
        next_page()
        assert app.engine.state['ended'] and next(a for a in app.engine.achievements if a['id'] == 'home')['completed']
        click('settings')
        click('achievements')
        app.render()
        click('close')
        click('settings')
        click('flowchart')
        chapter_point = next(n['id'] for n in app.session.flowchart()['nodes'] if n['chapter_id'] == 'meadow')
        click('select_point', chapter_point)
        click('load_point', chapter_point)
        click('chapter_continue')
        next_page()
        app.revealed = app.chunk_length
        assert app.engine.state['chapter_id'] == 'meadow' and not app.engine.state['ended']
        assert not next(a for a in app.engine.achievements if a['id'] == 'home')['completed']
        click('choose', 1)  # green route, source snapshot retains map knowledge
        next_page()
        click('chapter_continue')
        next_page()
        next_page()
        assert app.engine.state['ended'] and app.engine.achievements[-1]['id'] == 'loop' and app.engine.achievements[-1]['completed']
        click('settings')
        click('to_title')
        assert app.scene == 'title'
        click('continue_game')
        assert app.engine.state['ended']
        # Loading the title screen again must retain Continue without starting callbacks.
        second = App(app.story, tmp_path, muted=True)
        assert second.scene == 'title' and second.engine.export() == app.engine.export()
    finally:
        pygame.quit()
