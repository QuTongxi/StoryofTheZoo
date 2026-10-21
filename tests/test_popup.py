"""Blocking action continuations, rich message rendering and saved acknowledgments."""
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pygame
import pytest
from core import Story, Engine, StoryError
from core.session import Session


def popup(text='规则已更新，<red>请查看</red>。'):
    return {'property': 'popup', 'options': 'show', 'title': '游园提示', 'value': text}


def make(root, actions, *, items=None):
    (root / 'script.py').write_text("INITIAL_STATE={'count':0}\nCALLS=0\ndef count(state,args,context):\n global CALLS\n CALLS+=1\n state['count']+=1\ndef message(state,args,context):\n return [{'property':'popup','value':'函数消息'},{'function':'count'}]\n")
    doc = {'StoryName': '弹窗测试', 'script': 'script.py', 'items': items or [], 'chapters': [
        {'id': 'one', 'title': '第一章', 'contents': [{'id': 'START', 'actions': actions}, {'id': 'END'}]},
        {'id': 'two', 'title': '第二章', 'contents': [{'id': 'START', 'actions': [{'function': 'count'}]}, {'id': 'END'}]}]}
    (root / 'story.json').write_text(json.dumps(doc, ensure_ascii=False))
    return Story.load(root / 'story.json')


def test_popup_suspends_remaining_actions_and_records_ack(tmp_path):
    story = make(tmp_path, [{'function': 'count'}, popup(), {'function': 'count'}, popup('第二个'), {'property': 'jump', 'value': 'END'}])
    session = Session(story, tmp_path / 'session.json')
    session.start();session.apply('advance')
    checkpoint = session.data['active']
    assert story.script.CALLS == 1 and session.engine.state['variables']['count'] == 1
    assert session.engine.popup['text'] == '规则已更新，请查看。'
    assert session.engine.popup['text_spans'][0] == {'start': 6, 'end': 9, 'color': [191, 60, 48]}
    before = session.engine.export()
    assert Session(story, session.path).engine.export() == before and story.script.CALLS == 1
    session.apply('advance')
    assert session.engine.popup['text'] == '第二个' and story.script.CALLS == 2
    session.apply('advance')
    assert session.engine.state['ended'] and not session.engine.popup
    session.load(checkpoint)
    assert session.engine.export() == before and story.script.CALLS == 2
    session.apply('advance')
    assert story.script.CALLS == 3
    session.apply('rollback')
    assert session.engine.export() == before and story.script.CALLS == 3


def test_popup_blocks_choice_items_and_defers_validation_until_complete(tmp_path):
    decision = {'property': 'decision', 'value': [{'text': '结束', 'when': {'count': 1}, 'next_id': 'END'}]}
    story = make(tmp_path, [{'property': 'item', 'options': 'get', 'value': 'map'}, decision, popup(), {'function': 'count'}],
                 items=[{'id': 'map', 'name': '地图', 'description': '纸', 'on_use': [popup('物品消息')]}])
    engine = Engine(story);engine.advance()
    assert engine.can_advance and engine.is_decision and not engine.choices and not engine.item_uses
    before = engine.export()
    with pytest.raises(StoryError):engine.choose(0)
    with pytest.raises(StoryError):engine.use_item('map')
    assert engine.export() == before
    engine.advance()
    assert engine.choices and not engine.can_advance and engine.item_uses
    engine.choose(0)
    assert engine.state['ended']


def test_item_popup_preserves_return_and_consumes_once(tmp_path):
    story = make(tmp_path, [{'property': 'dialogue', 'value': '原对白'}, {'property': 'item', 'options': 'get', 'value': 'map'}],
        items=[{'id': 'map', 'name': '地图', 'description': '纸', 'consume': 1, 'on_use': [popup(), {'function': 'count'}]}])
    engine = Engine(story);engine.advance();engine.use_item('map')
    before = engine.export()
    assert engine.popup and not engine.inventory and len(engine._resume) == 1
    engine.advance()
    assert not engine.popup and engine.page['text'] == '原对白' and not engine._resume
    assert not engine.inventory and engine.state['variables']['count'] == 1
    engine.restore(before)
    assert engine.popup and len(engine._resume) == 1 and story.script.CALLS == 1
    engine.rollback()
    assert engine.state['inventory'] == {'map': 1} and not engine.popup


def test_function_popup_continues_before_outer_actions_and_chapter(tmp_path):
    story = make(tmp_path, [{'function': 'message'}, {'function': 'count'}, {'property': 'chapter', 'value': 'two'}])
    engine = Engine(story);engine.advance()
    assert engine.popup['text'] == '函数消息' and engine.state['variables']['count'] == 0
    engine.advance()
    assert engine.state['chapter_id'] == 'two' and engine.state['chapter_pending']
    assert engine.state['variables']['count'] == 2 and not engine.popup


def test_failed_ack_restores_popup_queue_and_live_state(tmp_path):
    story = make(tmp_path, [popup(), {'property': 'achievement', 'options': 'complete', 'value': 'missing'}])
    engine = Engine(story);engine.advance();before = engine.export()
    with pytest.raises(StoryError):engine.advance()
    assert engine.export() == before


@pytest.mark.parametrize('action', [popup(''), popup('<red></red>'), popup('<red>不配对'),
                                   {'property': 'popup', 'value': 1}, {'property': 'popup', 'value': '消息', 'options': 'hide'},
                                   {'property': 'popup', 'value': '消息', 'title': []}])
def test_invalid_popup_data(tmp_path, action):
    with pytest.raises(StoryError):make(tmp_path, [action])


def test_cli_popup_is_hidden_and_auto_acknowledged_across_processes(tmp_path):
    make(tmp_path, [popup(), {'function': 'count'}, popup('第二条'), {'property': 'jump', 'value': 'END'}])
    base = [sys.executable, 'game.py', '--cli', '--story', str(tmp_path / 'story.json'), '--session-dir', str(tmp_path / 'saves')]
    def run(*args):
        result = subprocess.run(base + list(args), capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    run()
    first = run('--continue')
    assert first['status'] == 'ended'
    assert 'popup' not in first and all('popup' not in row for row in first['segment'])
    assert '规则已更新' not in json.dumps(first, ensure_ascii=False)
    assert '第二条' not in json.dumps(first, ensure_ascii=False)
    assert run() == first
    checkpoint = first['auto_load_point']
    assert run('--load', checkpoint)['status'] == 'ended'
    # Even an explicit load of a pending popup checkpoint is settled for CLI.
    pending = json.loads((tmp_path / 'saves/session.json').read_text())['points'][1]['id']
    assert run('--load', pending)['status'] == 'ended'


def test_gui_centered_rich_popup_blocks_background_and_paginates(tmp_path):
    from gui.app import App
    from gui.popup_ui import PANEL
    text = '<red>规则已更新</red>，通过<blue>规则界面</blue>查看<green>所有告示</green>。\n' + '很长的提示文字。' * 70
    story = make(tmp_path, [popup(text), {'function': 'count'}, {'property': 'dialogue', 'value': '后续对白'}])
    app = App(story, tmp_path / 'saves', muted=True)
    try:
        app.action('new_game');app.action('chapter_continue');app.render()
        assert PANEL.center == (640, 400) and len(app.popup_chunks) > 1
        assert {b.action for b in app.buttons} == {'popup_continue'}
        colors = {app.canvas.get_at((x, y))[:3] for x in range(260, 1012) for y in range(272, 315)}
        assert {(191, 60, 48), (65, 120, 195), (50, 140, 85)} <= colors
        for key in (pygame.K_r, pygame.K_b, pygame.K_ESCAPE, pygame.K_1):
            app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(950, 25)))
        assert app.overlay is None and app.engine.popup and story.script.CALLS == 0
        for index in range(len(app.popup_chunks) - 1):
            app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            assert app.popup_index == index + 1 and story.script.CALLS == 0
        app.screen = pygame.display.set_mode((900, 650), pygame.RESIZABLE)
        app.render()
        x = app.viewport.x + round(PANEL.centerx * app.viewport.width / 1280)
        y = app.viewport.y + round(PANEL.centery * app.viewport.height / 800)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)))
        assert not app.engine.popup and story.script.CALLS == 1
        assert app.engine.page['text'] == '后续对白' and not app.engine.state['ended']
    finally:
        pygame.quit()
