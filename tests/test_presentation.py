"""Audit all action properties against both adapters, with real assets and saves."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pygame
import pytest
from core import Story
from core.story import PROPERTIES
from core.session import Session
from cli.presentation import present_segment

ROOT = Path(__file__).resolve().parents[1]


def presentation_story(root):
    for name, size, color in [('bg', (1280, 800), (80, 120, 160)), ('char', (80, 120), (215, 55, 95))]:
        surface = pygame.Surface(size);surface.fill(color);pygame.image.save(surface, str(root / f'{name}.png'))
    shutil.copyfile(ROOT / 'tests/fixtures/demo/audio/bell.wav', root / 'bell.wav')
    (root / 'logic.py').write_text("INITIAL_STATE={'ready':False}\ndef ready(state,args,context):\n state['ready']=True\n")
    actions = [
        {'property': 'background', 'options': 'fade in', 'value': 'bg.png', 'args': '.5s'},
        {'property': 'character', 'options': 'zoom in', 'value': 'char.png', 'slot': 'right', 'args': '1s'},
        *[{'property': p, 'value': 'bell.wav'} for p in ('music', 'voice', 'sound')],
        {'property': 'effect', 'value': {'type': 'flash', 'duration': .2, 'blocking': True}},
        {'property': 'dialogue', 'speaker': '管理员', 'value': '<red>红色正文</red>'},
        {'property': 'achievement', 'options': 'register', 'value': {'id': 'start', 'title': '启程', 'description': '开始游览'}},
        {'property': 'achievement', 'options': 'complete', 'value': 'start'},
        {'property': 'item', 'options': 'get', 'value': 'map'},
        {'property': 'rules', 'value': {'book_id': 'book', 'title': '游客守则', 'entries': [{'id': '1', 'text': '沿蓝色道路走。'}]}},
        {'property': 'popup', 'value': 'ONLY_HUMAN_TUTORIAL'},
        {'property': 'function', 'value': 'ready'},
        {'property': 'dialogue', 'value': '后续对白'},
        {'property': 'decision', 'value': [{'text': '去下一章', 'when': {'ready': True}, 'next_id': 'leave'}]}]
    leave = [
        {'property': 'background', 'options': 'hide'}, {'property': 'character', 'options': 'hide', 'slot': 'right'},
        *[{'property': p, 'options': 'stop'} for p in ('music', 'voice', 'sound')],
        {'property': 'effect', 'value': {'type': 'shake', 'duration': .1}},
        {'property': 'item', 'options': 'remove', 'value': 'map'}, {'property': 'jump', 'value': 'gate'}]
    doc = {'StoryName': '双入口审计', 'script': 'logic.py', 'items': [
        {'id': 'map', 'name': '地图', 'description': '折页', 'icon': 'bg.png', 'on_use': [
            {'property': 'popup', 'value': 'ONLY_HUMAN_ITEM_HINT'}, {'property': 'dialogue', 'value': '地图上标着蓝色的路。'}]}],
        'chapters': [
            {'id': 'one', 'title': '第一章', 'contents': [{'id': 'START', 'actions': actions}, {'id': 'leave', 'actions': leave},
                 {'id': 'gate', 'actions': [{'property': 'dialogue', 'value': '画面和声音都已关闭。'},
                     {'property': 'decision', 'value': [{'text': '跨章', 'next_id': 'next'}]}]},
                 {'id': 'next', 'actions': [{'property': 'chapter', 'value': 'two'}]}, {'id': 'END'}]},
            {'id': 'two', 'title': '第二章', 'subtitle': '10:00 / 兽舍', 'description': '一切正常。', 'background': 'bg.png',
             'contents': [{'id': 'START', 'actions': [{'property': 'dialogue', 'value': '抵达。'},
                 {'property': 'decision', 'value': [{'text': '结束', 'next_id': 'END'}]}]}, {'id': 'END'}]}]}
    exercised = {a['property'] for c in doc['chapters'] for node in c['contents'] for a in node.get('actions', [])}
    assert exercised == set(PROPERTIES)  # Adding a property requires adding adapter coverage.
    (root / 'story.json').write_text(json.dumps(doc, ensure_ascii=False))
    return Story.load(root / 'story.json')


def normalized(value):
    return json.loads(json.dumps(value))


def test_all_properties_gui_cli_semantics_and_actual_output(tmp_path):
    from gui.app import App
    story = presentation_story(tmp_path)
    app = App(story, tmp_path / 'gui')
    command = [sys.executable, 'game.py', '--cli', '--story', str(tmp_path / 'story.json'), '--session-dir', str(tmp_path / 'cli')]
    def run(*args):
        result = subprocess.run(command + list(args), capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'ONLY_HUMAN' not in result.stdout
        return json.loads(result.stdout)
    def same_state():
        disk = json.loads((tmp_path / 'cli/session.json').read_text())['current']
        assert normalized(app.engine.export()) == disk
    try:
        assert run()['status'] == 'chapter_intro'
        app.action('new_game');app.action('chapter_continue')
        assert app.engine.popup and app.blocked and app.effect['type'] == 'flash'
        assert {a['type'] for a in app.animations} == {'fade in', 'zoom in'}
        assert app.media.music == 'bell.wav' and app.media.enabled
        assert pygame.mixer.Channel(0).get_sound() and pygame.mixer.Channel(1).get_sound()
        app.effect_time = 2
        app.draw_scene()
        assert app.canvas.get_at((20, 200))[:3] == (80, 120, 160)
        assert app.canvas.get_at((1010, 400))[:3] == (215, 55, 95)
        app.action('popup_continue')
        shown = run('--continue')
        same_state()
        assert shown['status'] == 'awaiting_choice' and shown['choices'][0]['text'] == '去下一章'
        assert len(shown['segment']) == 1
        row = shown['segment'][0]
        assert row['text'] == '红色正文\n后续对白' and row['text_spans'][0]['color'] == [191, 60, 48]
        assert row['speaker'] == '' and 'popup' not in row and 'effect' not in row and 'animations' not in row
        assert row['rule_updates'][0]['entries'][0]['text'] == '沿蓝色道路走。'
        assert row['new_achievements'] == ['启程'] and shown['achievements'][0]['completed']
        assert shown['inventory'][0]['icon'] == str(tmp_path / 'bg.png') and shown['inventory'][0]['id'] == 'map' and shown['rulebooks'][0]['id'] == 'book'
        assert row['audio'] == {'music': str(tmp_path / 'bell.wav'), 'voices': [str(tmp_path / 'bell.wav')], 'sounds': [str(tmp_path / 'bell.wav')]}
        scene = pygame.image.load(row['scene_image'])
        assert scene.get_at((20, 200))[:3] == (80, 120, 160)
        assert scene.get_at((1010, 400))[:3] == (215, 55, 95)
        before = app.engine.export()
        assert run()['segment'] == shown['segment']
        assert app.engine.export() == before
        # Same item event; only GUI pauses for its instructional popup.
        app.action('use_item', 'map');assert app.engine.popup
        app.action('popup_continue')
        assert run('--use', 'map')['segment'][0]['text'] == '地图上标着蓝色的路。'
        same_state()
        app.revealed = app.chunk_length;app.action('advance')
        run('--continue');same_state()
        app.revealed = app.chunk_length;app.action('choose', 0)
        hidden = run('--choose', '去下一章');same_state()
        assert hidden['status'] == 'awaiting_choice' and hidden['page_id'] == 'gate'
        assert not hidden['segment'][-1]['has_background'] and not hidden['inventory']
        assert app.engine.state['characters'] == {} and app.engine.state['background'] is None and app.media.music is None
        assert not pygame.mixer.Channel(0).get_sound() and not pygame.mixer.Channel(1).get_sound()
        assert hidden['segment'][-1]['audio'] == {'music': None, 'voices': [], 'sounds': []}
        assert pygame.image.load(hidden['segment'][-1]['scene_image']).get_at((1010, 400))[:3] == (25, 45, 40)
        app.effect_time = 1
        app.revealed = app.chunk_length;app.action('choose', 0)
        second = run('--choose', '跨章');same_state()
        assert second['status'] == 'chapter_intro' and not second['inventory']
        assert second['chapter_info']['subtitle'] == '10:00 / 兽舍' and second['chapter_info']['description'] == '一切正常。'
        assert app.engine.state['characters'] == {} and app.media.music is None
        assert second['segment'][-1]['audio'] == {'music': None, 'voices': [], 'sounds': []}
        app.action('chapter_continue');run('--continue');same_state()
        app.revealed = app.chunk_length;app.action('choose', 0)
        assert run('--choose', '结束')['status'] == 'ended';same_state()
    finally:
        pygame.quit()


def test_projection_preserves_changed_visuals_and_audio_across_popups(tmp_path):
    story = presentation_story(tmp_path)
    session = Session(story, tmp_path / 'session.json', persist=False)
    session.start();session.apply('advance')
    before = session.engine.observe()
    # Different scenes cannot be collapsed just because the node ID matches.
    after = normalized(before);after.pop('popup');after['visual']['background'] = 'char.png'
    rows = present_segment([before, after])
    assert len(rows) == 2 and all('popup' not in row for row in rows)
    # Repeated voice clips are separate audio events, not silently deduplicated.
    after['visual'] = before['visual']
    rows = present_segment([before, after])
    assert rows[0]['audio']['voices'] == ['bell.wav', 'bell.wav']


def test_cli_popup_loop_fails_without_committing(tmp_path):
    presentation_story(tmp_path)
    data = json.loads((tmp_path / 'story.json').read_text())
    data['chapters'][0]['contents'][0]['actions'] = [
        {'property': 'popup', 'value': 'ONLY_HUMAN_LOOP'}, {'property': 'jump', 'value': 'START'}]
    (tmp_path / 'story.json').write_text(json.dumps(data))
    command = [sys.executable, 'game.py', '--cli', '--story', str(tmp_path / 'story.json'), '--session-dir', str(tmp_path / 'cli')]
    assert subprocess.run(command, capture_output=True).returncode == 0
    before = (tmp_path / 'cli/session.json').read_bytes()
    result = subprocess.run(command + ['--continue'], capture_output=True, text=True)
    assert result.returncode == 2 and '循环' in result.stdout and 'ONLY_HUMAN_LOOP' not in result.stdout
    assert (tmp_path / 'cli/session.json').read_bytes() == before
