"""CGs are complete compositions; rendering and replay must preserve the boundary."""
import json
from pathlib import Path

import pygame
import pytest

from core import Engine, Story
from core.story import StoryError
from cli.scene_export import SceneExporter
from tools.check_routes import walk, CASES, load_stories

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def layered_story(tmp_path):
    for name, size, color in [('bg', (1280, 800), (80, 120, 160)),
                              ('cg', (1600, 900), (60, 80, 110)),
                              ('char', (80, 120), (215, 55, 95))]:
        surface = pygame.Surface(size)
        surface.fill(color)
        pygame.image.save(surface, str(tmp_path / f'{name}.png'))
    def node(key, *actions):
        return {'id': key, 'actions': list(actions) + [{'property': 'dialogue', 'value': key}]}
    char = {'property': 'character', 'value': 'char.png'}  # no slot: LEFT
    doc = {'StoryName': '分层测试', 'chapters': [
        {'id': 'scene', 'title': '场景', 'background': 'bg.png', 'contents': [
            node('START', char),
            node('cg', {'property': 'illustration', 'value': 'cg.png'}, char),
            node('still_cg', dict(char, slot='right')),
            node('back', {'property': 'background', 'value': 'bg.png'}),
            node('talk', char),
            {'id': 'next', 'actions': [{'property': 'chapter', 'value': 'ending'}]}, {'id': 'END'}]},
        {'id': 'ending', 'title': '结局', 'background': 'cg.png', 'visual_mode': 'illustration',
         'contents': [node('START', char), {'id': 'END'}]}]}
    path = tmp_path / 'story.json'
    path.write_text(json.dumps(doc))
    return Story.load(path)


def test_cg_clears_and_suppresses_portraits_then_requires_explicit_reentry(layered_story):
    e = Engine(layered_story)
    e.advance()
    assert e.state['characters'] == {'left': 'char.png'}
    e.advance()
    assert e.state['visual_mode'] == 'illustration' and not e.state['characters']
    e.advance()
    assert not e.state['characters']
    restored = Engine(layered_story, initialize=False)
    restored.restore(e.export())
    assert restored.observe() == e.observe()
    e.advance()
    assert e.state['visual_mode'] == 'background' and not e.state['characters']
    e.advance()
    assert e.state['characters'] == {'left': 'char.png'}
    e.advance()  # chapter intro also uses illustration mode
    assert e.state['visual_mode'] == 'illustration' and not e.state['characters']
    e.advance()
    assert not e.state['characters']


def test_gui_cli_same_pixels_and_cg_preserves_full_frame(layered_story, tmp_path):
    from gui.app import App
    app = App(layered_story, tmp_path / 'gui')
    exporter = SceneExporter(layered_story, tmp_path / 'cli')
    try:
        app.action('new_game')
        app.action('chapter_continue')
        for expected in ('background', 'illustration', 'illustration', 'background', 'background'):
            visual = app.engine.observe()['visual']
            assert visual['visual_mode'] == expected
            _, scene = exporter.surfaces(visual)
            app.draw_scene()
            assert pygame.image.tobytes(scene, 'RGB') == pygame.image.tobytes(app.canvas, 'RGB')
            if expected == 'illustration':
                assert all(abs(actual - wanted) <= 3 for actual, wanted in zip(scene.get_at((270, 400))[:3], (60, 80, 110)))
                assert scene.get_at((640, 10))[:3] == (12, 20, 18)  # letterbox, no crop
                # Even a stale adapter input cannot reintroduce a sprite over CG.
                _, hostile = exporter.surfaces(visual | {'characters': {'left': 'char.png'}})
                assert pygame.image.tobytes(hostile, 'RGB') == pygame.image.tobytes(scene, 'RGB')
                before = app.engine.export()
                app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
                app.render()
                assert app.ui_hidden and not app.buttons
                assert pygame.image.tobytes(scene, 'RGB') == pygame.image.tobytes(app.canvas, 'RGB')
                app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
                assert not app.ui_hidden and app.engine.export() == before
            app.revealed = app.chunk_length
            app.action('advance')
    finally:
        pygame.quit()


@pytest.mark.parametrize('mode', ['cg', None, 1])
def test_unknown_chapter_visual_mode_is_rejected(layered_story, tmp_path, mode):
    path = tmp_path / 'story.json'
    doc = json.loads(path.read_text())
    doc['chapters'][0]['visual_mode'] = mode
    path.write_text(json.dumps(doc))
    with pytest.raises(StoryError):
        Story.load(path)


def test_all_production_routes_respect_layers_and_every_event_cg_is_reached():
    story = load_stories()
    seen = set()
    for ending in CASES:
        e, *_ = walk(story, ending)
        for obs in e.observations:
            visual = obs['visual']
            asset = visual['background'] or ''
            if visual['visual_mode'] == 'illustration':
                assert not visual['characters'], (ending, obs['chapter_id'], obs['page_id'])
                seen.add(asset)
            else:
                assert set(visual['characters']) <= {'left'}
                assert '/illustrations/' not in asset and '/endings/' not in asset
    expected = {str(p.relative_to(ROOT / 'data')) for p in (ROOT / 'data/art/illustrations').glob('*.png')}
    assert expected <= seen
    assert {f'art/endings/{ending}.png' for ending in CASES} <= seen


@pytest.mark.parametrize('ending,absent', [
    ('BV1', 'map_ready'), ('NV1', 'rain_entry'), ('BE2', 'lion_rescue'),
    ('BE4', 'lion_rescue'), ('NE1', 'red_handover'), ('BE5', 'overheard_confession'),
    ('BE6', 'entrance_defense'), ('BE7', 'entrance_defense')])
def test_success_illustration_does_not_spoil_or_contradict_other_branch(ending, absent):
    e, *_ = walk(load_stories(), ending)
    assert not any(o['visual']['background'] == f'art/illustrations/{absent}.png' for o in e.observations)
