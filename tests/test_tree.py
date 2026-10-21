"""Chapter-level branching, metadata, tree geometry and viewport interaction."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pygame
import pytest
from core import Story, StoryError
from core.session import Session
from core.flowchart import tree_text
from gui.tree_ui import layout_tree, VIEW


def branching_story(root):
    def chapter(id, title, destinations=(), **metadata):
        actions = [{'property': 'dialogue', 'value': title}]
        if destinations:
            actions.append({'property': 'decision', 'value': [
                {'text': target, 'actions': [{'property': 'chapter', 'value': target}]} for target in destinations]})
        return {'id': id, 'title': title, 'description': f'{title}的简介', **metadata,
                'contents': [{'id': 'START', 'actions': actions}, {'id': 'END'}]}
    doc = {'StoryName': '章节树示例', 'chapters': [
        chapter('gate', '第一章 · 入园', ['meadow', 'night']),
        chapter('meadow', '第二章 · 草食动物区', ['escape', 'death', 'return']),
        chapter('night', '第二章 · 夜间园区', ['escape']),
        chapter('escape', '结局 · 平安离园', ending='normal'),
        chapter('death', '结局 · 围栏之后', ending='death'),
        chapter('return', '结局 · 再次入园', ending='normal')]}
    path = root / 'tree.json'
    path.write_text(json.dumps(doc, ensure_ascii=False))
    return Story.load(path), doc


def explored_session(root):
    story, _ = branching_story(root)
    session = Session(story, root / 'session.json')
    session.start()
    session.apply('advance')
    first_choice = session.data['active']
    session.apply('choose', 0)
    session.apply('advance')
    meadow_choice = session.data['active']
    for option in range(3):
        session.load(meadow_choice)
        session.apply('choose', option)
        session.apply('advance')
        session.apply('advance')
    session.load(first_choice)
    session.apply('choose', 1)
    session.apply('advance')
    session.apply('choose', 0)
    session.apply('advance')
    session.apply('advance')
    return session


def test_tree_collapses_pages_retains_siblings_and_distinct_paths(tmp_path):
    session = explored_session(tmp_path)
    tree = session.flowchart()
    by_id = {n['id']: n for n in tree['nodes']}
    root = by_id[tree['roots'][0]]
    assert len(tree['roots']) == 1 and len(tree['nodes']) == 7
    assert [by_id[c]['chapter_id'] for c in root['children']] == ['meadow', 'night']
    meadow = by_id[root['children'][0]]
    assert [by_id[c]['chapter_id'] for c in meadow['children']] == ['escape', 'death', 'return']
    death = next(n for n in tree['nodes'] if n['chapter_id'] == 'death')
    assert death['ending'] == 'death' and death['completed'] and not death['children']
    assert death['description'] == '结局 · 围栏之后的简介'
    escape = [n for n in tree['nodes'] if n['chapter_id'] == 'escape']
    assert len(escape) == 2 and escape[0]['parent'] != escape[1]['parent']
    assert sum(n['current'] for n in tree['nodes']) == 1
    assert all(session.data['points'][int(n['load_point'][3:]) - 1]['snapshot']['state']['chapter_pending'] for n in tree['nodes'])
    session.load(death['load_point'])
    assert session.engine.state['chapter_id'] == 'death' and session.engine.state['chapter_pending']
    assert Session(session.story, session.path).flowchart() == session.flowchart()
    text = tree_text(tree)
    assert '├─' in text and '└─' in text and '[死亡结局]' in text and '的简介' in text


def test_replay_and_rollback_dont_create_false_chapter_edges(tmp_path):
    story, _ = branching_story(tmp_path)
    session = Session(story, tmp_path / 'session.json')
    session.start(); session.apply('advance'); session.apply('choose', 0)
    tree = session.flowchart()
    session.apply('rollback')  # back in gate: don't make gate a child of meadow
    assert len(session.flowchart()['nodes']) == 2
    assert next(n for n in session.flowchart()['nodes'] if n['chapter_id'] == 'gate')['current']
    session.apply('choose', 0)
    assert session.flowchart() == tree
    session.start()  # identical starting state shares the tree root
    assert len(session.flowchart()['roots']) == 1
    assert len(session.flowchart()['nodes']) == 2


def test_loaded_foreign_manual_snapshot_gets_resumable_chapter_card(tmp_path):
    session = explored_session(tmp_path)
    target = Session(session.story, tmp_path / 'imported.json')
    target.import_snapshot(session.engine.export())
    tree = target.flowchart()
    assert len(tree['nodes']) == 1 and tree['nodes'][0]['completed']
    assert not tree['nodes'][0]['entry']
    target.load(tree['nodes'][0]['load_point'])
    assert target.engine.export() == session.engine.export()


def test_subtrees_have_disjoint_width_and_children_share_depth(tmp_path):
    tree = explored_session(tmp_path).flowchart()
    positions, extent = layout_tree(tree)
    by_id = {n['id']: n for n in tree['nodes']}
    for node in tree['nodes']:
        rect = positions[node['id']]
        for other in tree['nodes']:
            if node['id'] != other['id']:
                assert not rect.colliderect(positions[other['id']])
        children = [positions[c] for c in node['children']]
        if children:
            assert len({r.y for r in children}) == 1
            assert min(r.y for r in children) > rect.bottom
            assert abs(rect.centerx - (children[0].centerx + children[-1].centerx) / 2) <= 1
        assert rect.right <= extent[0] and rect.bottom <= extent[1]
    meadow, night = [positions[c] for c in by_id[tree['roots'][0]]['children']]
    assert meadow.y == night.y and meadow.right < night.left


def test_large_deep_tree_layout_is_iterative():
    nodes = [{'id': str(i), 'parent': str(i - 1) if i else None, 'children': [str(i + 1)] if i < 1199 else []} for i in range(1200)]
    positions, extent = layout_tree({'roots': ['0'], 'nodes': nodes})
    assert len(positions) == 1200 and extent[1] > 100000
    assert len({r.x for r in positions.values()}) == 1


@pytest.mark.parametrize('field,value', [('description', None), ('description', []), ('ending', 'unknown'), ('ending', None)])
def test_bad_chapter_tree_metadata(tmp_path, field, value):
    _, doc = branching_story(tmp_path)
    doc['chapters'][0][field] = value
    with pytest.raises(StoryError):
        Story(doc, tmp_path)


def test_description_falls_back_to_subtitle_and_unvisited_chapters_hidden(tmp_path):
    _, doc = branching_story(tmp_path)
    del doc['chapters'][0]['description']
    doc['chapters'][0]['subtitle'] = '09:00 入园'
    session = Session(Story(doc, tmp_path), tmp_path / 'session.json')
    session.start()
    assert len(session.flowchart()['nodes']) == 1
    assert session.flowchart()['nodes'][0]['description'] == '09:00 入园'


def test_gui_tree_pan_zoom_selection_and_clipped_clicks(tmp_path):
    from gui.app import App
    session = explored_session(tmp_path)
    app = App(session.story, tmp_path, muted=True)
    try:
        app.action('continue_game'); app.action('flowchart'); app.render()
        nodes = [b for b in app.buttons if b.action == 'select_point']
        assert len(nodes) == 7
        assert not any(b.action == 'graph_chapter' for b in app.buttons)
        death = next(n for n in session.flowchart()['nodes'] if n['chapter_id'] == 'death')
        button = next(b for b in nodes if b.value == death['id'])
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.rect.center))
        assert app.graph_selected == death['id']
        app.action('graph_zoom', 2.5); app.render()
        assert all(VIEW.contains(b.rect) for b in app.buttons if b.action == 'select_point')
        start = (VIEW.x + 2, VIEW.y + 2)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start))
        app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(start[0] - 40, start[1] - 30)))
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=start))
        assert app.graph_pan != [0, 0] and app.graph_drag is None
        app.action('graph_fit');app.render()
        assert app.graph_pan == [0, 0]
        load = next(b for b in app.buttons if b.action == 'load_point')
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=load.rect.center))
        assert app.scene == 'chapter' and app.engine.state['chapter_id'] == 'death'
    finally:
        pygame.quit()


def test_cli_exports_chapter_tree_and_text(tmp_path):
    session = explored_session(tmp_path)
    result = subprocess.run([sys.executable, 'game.py', '--cli', '--story', str(tmp_path / 'tree.json'),
                             '--session-dir', str(tmp_path), '--flowchart'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload['tree'] == session.flowchart() and '[死亡结局]' in payload['tree_text']
