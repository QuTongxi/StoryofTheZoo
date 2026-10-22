"""The menu unlocks a second story, never a branch in the first story."""
import json
from pathlib import Path
import subprocess
import sys

import pygame
import pytest

from core import Engine, StoryError
from core.library import Library
from tools.build_story import audit_json
from tools.check_routes import walk, load_stories

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def milestones():
    story = load_stories()['visitor']
    completed, *_ = walk(story, 'TV')
    e = Engine(story)
    before = None
    for op in completed.actions:
        if e.state['chapter_id'] == 'V14':
            before = e.export()
        if op['kind'] == 'advance':
            e.advance()
        elif op['kind'] == 'choose':
            e.choose(op['index'])
        else:
            e.use_item(op['item_id'])
        if e.state['chapter_id'] == 'V15':
            return before, e.export()
    raise AssertionError('Missing aquarium milestone')


def test_separate_documents_shared_script_and_auditable_actions():
    stories = load_stories()
    assert stories['visitor'].initial_chapter == 'V01'
    assert stories['employee'].initial_chapter == 'E01'
    ids = [{c['id'] for c in s.chapters} for s in stories.values()]
    assert not ids[0] & ids[1]
    for key in stories:
        text = (ROOT/f'data/{key}.json').read_text()
        data = json.loads(text)
        assert data['script'] == 'logic.py'
        assert text == audit_json(data)+'\n'
        action_lines = 0
        for line in text.splitlines():
            if line.lstrip().startswith(('{"property":', '{"function":')):
                json.loads(line.strip().rstrip(','))
                action_lines += 1
        assert action_lines == sum(len(n.get('actions', [])) for c in data['chapters'] for n in c['contents']) + sum(len(i.get('on_use', [])) for i in data['items'])
    assert not (ROOT/'data/story.json').exists()


def test_milestone_permanent_across_restart_and_rollback(tmp_path, milestones):
    library = Library(tmp_path)
    assert not library.unlocked('employee')
    with pytest.raises(StoryError):
        library.session('employee')
    assert not (tmp_path/'employee').exists()
    session = library.session('visitor')
    session.import_snapshot(milestones[0])
    library.record('visitor', session)
    assert not library.unlocked('employee')
    session.import_snapshot(milestones[1])
    library.record('visitor', session)
    assert library.unlocked('employee')
    session.import_snapshot(milestones[0])
    library.record('visitor', session)
    session.start()
    library.record('visitor', session)
    loaded = Library(tmp_path)
    assert loaded.unlocked('employee')
    employee = loaded.session('employee')
    employee.start()
    assert employee.engine.state['chapter_id'] == 'E01'
    assert not employee.engine.rulebooks and not employee.engine.inventory
    assert loaded.session('visitor').engine.state['chapter_id'] == 'V01'


def test_gui_title_selection_popup_and_cross_story_load(tmp_path, milestones):
    from gui.app import App
    library = Library(tmp_path)
    app = App(library.stories['visitor'], tmp_path, library=library, muted=True)
    def click(action, value=None):
        app.render()
        button = next(b for b in app.buttons if b.action == action and b.value == value)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.rect.center))
    try:
        app.render()
        assert [b.text for b in app.buttons] == ['新游戏', '载入存档', '设置', '退出游戏']
        click('new_game')
        assert app.scene == 'stories' and app.engine is None
        click('select_story', 'employee')
        assert app.menu_popup and app.engine is None
        assert not (tmp_path/'employee').exists()
        app.render()
        assert [b.action for b in app.buttons] == ['popup_continue']
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
        assert app.menu_popup  # No keyboard choice can penetrate the modal.
        click('popup_continue')
        assert app.scene == 'stories' and app.engine is None
        click('select_story', 'visitor')
        assert app.scene == 'chapter' and app.engine.state['chapter_id'] == 'V01'
        app.session.import_snapshot(milestones[1])
        app.sync_page(restored=True)
        assert library.unlocked('employee')
        app.action('save_slot', 1)
        visitor_saved = (tmp_path/'visitor/slot-1.json').read_bytes()
        app.action('to_title')
        app.render()
        assert len(app.buttons) == 4
        click('new_game')
        click('select_story', 'employee')
        assert app.story_id == 'employee' and app.engine.state['chapter_id'] == 'E01'
        assert not app.engine.rulebooks
        app.action('save_slot', 1)
        assert (tmp_path/'visitor/slot-1.json').read_bytes() == visitor_saved
        app.action('to_title')
        click('load')
        click('load_story_tab', 'visitor')
        click('load_slot', 1)
        assert app.story_id == 'visitor' and app.engine.state['chapter_id'] == 'V15'
        app.action('to_title')
        click('load')
        click('load_story_tab', 'employee')
        click('load_auto')
        assert app.story_id == 'employee' and app.engine.state['chapter_id'] == 'E01'
        app.render()
    finally:
        pygame.quit()


def cli(directory, *args):
    result = subprocess.run([sys.executable, str(ROOT/'game.py'), '--cli', '--session-dir', str(directory), *args],
                            cwd=ROOT, capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


def test_cli_gate_including_direct_file_and_real_milestone(tmp_path, milestones):
    directory = tmp_path/'session'
    assert cli(directory)[1]['status'] == 'story_selection'
    for args in [('--select-story', 'employee'), ('--story', str(ROOT/'data/employee.json'))]:
        code, locked = cli(directory, *args)
        assert code == 0 and locked['status'] == 'locked' and 'popup' in locked
        assert 'segment' not in locked
        assert not (directory/'employee').exists()
    # A failed batch must not unlock even if it passed the milestone in memory.
    commands = []
    for op in milestones[1]['actions']:
        commands.append({'action': 'continue'} if op['kind'] == 'advance' else
                        {'action': 'choose', 'index': op['index']+1} if op['kind'] == 'choose' else
                        {'action': 'use', 'item': op['item_id']})
    batch = tmp_path/'batch.json'
    batch.write_text(json.dumps(commands + [{'action': 'use', 'item': 'missing'}]))
    assert cli(directory, '--select-story', 'visitor', '--batch', str(batch))[0] == 2
    assert not Library(directory).unlocked('employee')
    batch.write_text(json.dumps(commands))
    code, result = cli(directory, '--select-story', 'visitor', '--batch', str(batch))
    assert code == 0 and result['chapter_id'] == 'V15'
    code, result = cli(directory, '--select-story', 'employee')
    assert code == 0 and result['chapter_id'] == 'E01'
    assert result['inventory'] == [] and result['rulebooks'] == []
    assert (directory/'visitor/session.json').exists() and (directory/'employee/session.json').exists()
    assert cli(directory, '--new')[1]['status'] == 'story_selection'
