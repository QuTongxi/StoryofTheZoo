"""Exercise every ending through real choices and item operations, never by
editing state. Saves selected reached snapshots for GUI smoke verification.
"""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core import Engine, Story

DEFAULTS={('V07','photo'):2,('V08','aquarium'):1,('V10','overnight'):1,
          ('E07','shift'):1,('E08','red_offer'):1}
CASES={
 'TV':{},'TE':{},
 'NV1':{('V07','photo'):0},'NV2':{('V10','overnight'):0},'NV3':{('V13','confess'):1},
 'NE1':{('E07','shift'):0},'NE2':{('E14','offer'):1},
 'BV1':{'no_map':True},'BV2':{('V04','fork'):1},'BV3':{('V06','elephant'):1},
 'BV4':{('V09','food'):3},'BV5':{('V11','black'):1},
 'BV6':{('V14','night_window'):1,('V14','lamp_confirm'):1},
 'BE1':{'no_handbook':True},'BE2':{('E01','stock'):1,('E05','equipment'):1,('E05','empty_choice'):1},
 'BE3':{('E06','symptoms'):1},'BE4':{('E05','lion'):1},
 'BE5':{('E09','rooms_menu'):'先搁置',('E09','neglect'):1},
 'BE6':{('E10','intruder'):1},'BE7':{('E10','intruder'):3},
 'BE8':{('E11','darkness'):1},'BE9':{('E13','handover'):1},
 'BX1':{'buy_toy':True,('V07','photo'):0},
}

def walk(story,target,options=None,*,snapshots=False):
    plan=DEFAULTS|CASES.get(target,{})|(options or {})
    e=Engine(story)
    employee=target.startswith(('TE','NE','BE'))
    visited=set(); decisions=[]; saved={}; once=set()
    for step in range(1600):
        cid,pid=e.state['chapter_id'],e.state['page_id']
        visited.add(cid)
        if snapshots and not e.state['chapter_pending'] and e.page['text'] and not e.popup:
            if cid in ('V02','V05','V13','E04','E10','TE','TV') and cid not in saved and (e.page.get('speaker') or cid in ('V13','E04','TE','TV')):
                saved[cid]=e.export()
        if e.state['ended']:
            assert cid==target,(target,cid,decisions)
            restored=Engine(story,initialize=False);restored.restore(e.export())
            assert restored.export()==e.export()
            return e,visited,decisions,saved
        if e.popup or e.state['chapter_pending']:
            e.advance();continue
        if e.choices:
            key=(cid,pid)
            if key==('prologue','route'):
                choice=int(employee)
            elif key==('V03','map_window') and not plan.get('no_map') and not e.state['variables']['map_piece']:
                e.use_item('map');continue
            elif key==('E02','handbook_window') and not plan.get('no_handbook') and not e.state['variables']['staff_page']:
                e.use_item('handbook');continue
            elif key==('V05','shop'):
                buy=next((k for k in ('buy_toy','buy_blood','buy_water','buy_patch') if plan.get(k) and k not in once),None)
                if buy:
                    once.add(buy);choice={'buy_toy':3,'buy_blood':2,'buy_water':0,'buy_patch':1}[buy]
                else:choice=4
            elif key==('E09','rooms_menu') and key not in plan:
                choice=next((i for i,c in enumerate(e.choices) if c['text'].startswith('检查')),0)
            else:
                choice=plan.get(key,0)
                if isinstance(choice,str):
                    choice=next(i for i,c in enumerate(e.choices) if c['text'].startswith(choice))
            decisions.append([cid,pid,e.choices[choice]['text']]);e.choose(choice)
        else:
            e.advance()
    raise AssertionError(('route did not finish',target,e.state['chapter_id'],e.state['page_id']))

def main():
    p=argparse.ArgumentParser();p.add_argument('--logic-only',action='store_true');args=p.parse_args()
    if args.logic_only:
        # Draft validation while image production is still in flight. The final
        # normal run validates every real file with Story.load as well.
        Story.asset=lambda self,value: self.root/value
    story=Story.load(ROOT/'data/story.json')
    started=time.monotonic();report=[];union=set();snapshot_dir=ROOT/'runtime/verification'
    snapshot_dir.mkdir(parents=True,exist_ok=True)
    for target in CASES:
        e,visited,decisions,saved=walk(story,target,snapshots=target in ('TV','TE'))
        if target in ('TV','TE'):union.update(e.state['rulebooks'])
        report.append({'ending':target,'steps':len(e.actions),'chapters':len(visited),'choices':len(decisions)})
        commands=[]
        for op in e.actions:
            if op['kind']=='advance': commands.append({'action':'continue'})
            elif op['kind']=='choose': commands.append({'action':'choose','index':op['index']+1})
            elif op['kind']=='use_item': commands.append({'action':'use','item':op['item_id']})
        (snapshot_dir/(target+'-operations.json')).write_text(json.dumps(commands,ensure_ascii=False))
        for name,snapshot in saved.items():
            (snapshot_dir/(name+'.json')).write_text(json.dumps(snapshot,ensure_ascii=False))
        print(target,'OK',len(e.actions),'actions',flush=True)
    assert len(union)==9,union
    extra=[('NV1',{('V07','photo'):1}),('NV1',{('V08','aquarium'):0}),
           ('NV3',{('V13','confess'):2}),('NE1',{('E08','red_offer'):0}),
           ('BV6',{('V14','night_window'):2,('V14','door_confirm'):1}),
           ('BE3',{('E06','symptoms'):2}),('BE6',{('E10','intruder'):2}),
           ('TE',{('E01','stock'):1,('E05','equipment'):1}),
           ('TV',{'buy_blood':True,('V05','note_choice'):1}),
           ('TV',{'buy_toy':True}),('TE',{('E11','room_note'):1,('E14','guard_note'):1})]
    for target,options in extra:
        e,*_=walk(story,target,options)
        if options.get('buy_blood'):
            assert e.state['inventory'].get('goat_meat')==1 and not e.state['inventory'].get('rabbit_blood')
            assert not e.state['variables']['read_vnote']
        if options.get('buy_toy'):
            assert not e.state['inventory'].get('rabbit_toy')
    payload={'mode':'logic only, media unchecked' if args.logic_only else 'full assets and routes',
             'routes':report,'additional_variants':len(extra),'whole_rulebooks':sorted(union),
             'seconds':round(time.monotonic()-started,2)}
    (snapshot_dir/'routes.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print(json.dumps(payload,ensure_ascii=False))

if __name__=='__main__':main()
