"""Game-level invariants: real inventory, optional knowledge and all endings."""
import json
from pathlib import Path
import pytest
from core import Story, Engine
from core.session import Session
from tools.check_routes import walk, CASES

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def production():
    return Story.load(ROOT/'data/story.json')

@pytest.mark.parametrize('ending',list(CASES))
def test_every_ending_is_reachable_with_real_actions(production,ending):
    engine,*_=walk(production,ending)
    assert engine.state['ended']
    assert next(a for a in engine.achievements if a['id']=='end_'+ending)['completed']

def test_optional_notes_do_not_leak_and_collection_does_not_teach_actor(production,tmp_path):
    visitor,*_=walk(production,'TV',{('V05','note_choice'):1})
    assert 'visitor_note' not in visitor.state['rulebooks']
    worker,*_=walk(production,'TE',{('E11','room_note'):1,('E14','guard_note'):1})
    assert 'room_note' not in worker.state['rulebooks'] and 'guard' not in worker.state['rulebooks']
    session=Session(production,tmp_path/'session.json')
    session.import_snapshot(visitor.export())
    assert session.collection.data['endings']==['TV']
    session.start()
    assert not session.engine.rulebooks
    assert 'TV' in session.collection.data['endings']
    loaded=Session(production,session.path)
    assert loaded.collection.data==session.collection.data
    assert not loaded.engine.rulebooks

def test_blood_changes_picture_without_eating_and_toy_is_visibly_collected(production):
    engine,*_=walk(production,'TV',{'buy_blood':True,'buy_toy':True})
    assert not engine.state['variables']['goat_eaten']
    assert not engine.state['inventory'].get('rabbit_blood')
    assert engine.state['inventory']['goat_meat']==1
    assert not engine.state['inventory'].get('rabbit_toy')
    assert any('玩偶放进工作推车' in h['text'] for h in engine.history)
    assert production.items['goat_meat'].icon!=production.items['rabbit_blood'].icon

def test_whole_documents_and_both_routes_collect_all_nine(production):
    visitor,*_=walk(production,'TV')
    worker,*_=walk(production,'TE')
    books=visitor.state['rulebooks']|worker.state['rulebooks']
    assert len(books)==9
    all_text='\n'.join(text for book in books.values() for text in book['entries'].values())
    assert '【隐藏文字' in all_text and '~~' in all_text and '**' in all_text
    updates=[a['value'] for c in production.chapters for n in c['contents'] for a in n['actions'] if a.get('property')=='rules']
    for update in updates:
        assert {e['id']:e['text'] for e in update['entries']}==books[update['book_id']]['entries']

def test_wrong_ticket_can_be_corrected_before_leaving(production):
    engine=Engine(production)
    target,*_=walk(production,'TV')
    for op in target.actions:
        if op['kind']=='advance':engine.advance()
        elif op['kind']=='choose':engine.choose(op['index'])
        elif op['kind']=='use_item':
            if op['item_id']=='map':
                engine.choose(1) # explicitly tear ticket first
                while not engine.choices:engine.advance()
            engine.use_item(op['item_id'])
    assert engine.state['chapter_id']=='TV' and engine.state['ended']
    assert not engine.state['variables']['ticket_intact']
    assert any('包里。两半。' in h['text'] for h in engine.history)
