"""Local, cumulative extras. Never used as character knowledge or game state."""
from pathlib import Path
import json
import logging


class Collection:
    def __init__(self, story, path):
        self.story, self.path = story, Path(path)
        self.data = {'version':1,'story':story.name,'achievements':[], 'rulebooks':{}, 'endings':[]}
        if self.path.exists():
            try:
                candidate=json.loads(self.path.read_text())
                if (set(candidate)==set(self.data) and candidate['version']==1
                        and candidate['story']==story.name
                        and isinstance(candidate['achievements'],list)
                        and isinstance(candidate['rulebooks'],dict)
                        and isinstance(candidate['endings'],list)):
                    self.data=candidate
            except (OSError, ValueError, TypeError):
                logging.getLogger(__name__).warning('资料馆记录无法读取，本次重新收集；剧情存档仍可独立读取。')

    def update(self, engine, persist=True):
        before=json.dumps(self.data,sort_keys=True,ensure_ascii=False)
        self.data['achievements']=sorted(set(self.data['achievements'])|{
            a['id'] for a in engine.achievements if a['completed']})
        for book in engine.rulebooks:
            self.data['rulebooks'][book['id']]={**book,'entries':[
                {**entry,'bookmarked':False} for entry in book['entries']]}
        # Unlock CG only after reaching the ending's achievement, not its intro.
        for chapter in self.story.chapters:
            if chapter.get('ending') and 'end_'+chapter['id'] in self.data['achievements']:
                self.data['endings']=sorted(set(self.data['endings'])|{chapter['id']})
        if persist and before!=json.dumps(self.data,sort_keys=True,ensure_ascii=False):
            from .session import atomic_json
            try:
                atomic_json(self.path,self.data)
            except OSError as exc:
                logging.getLogger(__name__).warning('资料馆未能写入：%s',exc)

    @property
    def achievements(self):
        return [{**a,'completed':a['id'] in self.data['achievements']} for a in self.story.achievement_definitions]

    @property
    def rulebooks(self):
        return list(self.data['rulebooks'].values())
