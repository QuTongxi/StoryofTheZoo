"""AI interface: one command, one observation, shared chapter checkpoints."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

from core import Story, StoryError
from core.session import Session, atomic_json
from .presentation import present_segment, present_inventory

ROOT = Path(__file__).resolve().parents[1]
CliError = StoryError


@contextmanager
def session_lock(path):
    """OS-owned advisory lock releases even if the process crashes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise CliError('另一个命令正在使用此会话，请稍后重试') from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CliError('另一个命令正在使用此会话，请稍后重试') from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise StoryError(message)


def run_until_choice(session):
    segment, seen = [session.engine.observe()], set()
    for _ in range(1000):
        engine = session.engine
        if not engine.popup and (engine.state['ended'] or engine.is_decision):
            return segment
        marker = json.dumps({'state': engine.state, 'view': engine.page, 'resume': engine.export()['resume']}, sort_keys=True)
        if marker in seen:
            raise StoryError('自动推进遇到循环')
        seen.add(marker)
        session.apply('advance')
        segment.append(session.engine.observe())
    raise StoryError('连续自动推进超过 1000 页')


def main(argv=None):
    parser = Parser(description='动物园：AI 命令行入口')
    parser.add_argument('--story', type=Path, default=ROOT / 'data/story.json')
    parser.add_argument('--session-dir', type=Path, default=ROOT / 'saves/cli')
    parser.add_argument('--output-dir', type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--choose')
    actions.add_argument('--choose-index', type=int)
    actions.add_argument('--continue', dest='continue_story', action='store_true')
    actions.add_argument('--use', metavar='ITEM_ID')
    actions.add_argument('--list-load-point', action='store_true')
    actions.add_argument('--flowchart', action='store_true')
    actions.add_argument('--achievements', action='store_true')
    actions.add_argument('--load', metavar='POINT_ID')
    actions.add_argument('--save', metavar='LABEL')
    actions.add_argument('--new', action='store_true')
    actions.add_argument('--inventory', action='store_true')
    actions.add_argument('--rules', nargs='?', const='', metavar='BOOK_ID')
    actions.add_argument('--bookmark', metavar='BOOK_ID:ENTRY_ID')
    actions.add_argument('--batch', type=Path, metavar='OPERATIONS_JSON', help='依次执行显式操作；失败时不提交整批进度')
    actions.add_argument('--collection', action='store_true', help='查看本地跨周目资料馆，不改变角色知识')
    try:
        args = parser.parse_args(argv)
        story = Story.load(args.story)
        directory = args.session_dir.resolve()
        output = (args.output_dir or (ROOT / 'runtime/cli' if directory == (ROOT / 'saves/cli').resolve() else directory / 'view')).resolve()
        with session_lock(directory / '.lock'):
            session = Session(story, directory / 'session.json', persist=False)
            result = {'ok': True, 'protocol_version': 2}
            if args.collection:
                result['collection'] = session.collection.data
            elif args.list_load_point:
                result.update(session_exists=session.engine is not None, load_points=session.points())
            elif args.flowchart:
                from core.flowchart import tree_text
                result['tree'] = session.flowchart()
                result['tree_text'] = tree_text(result['tree'])
            elif args.inventory or args.rules is not None or args.achievements:
                if session.engine is None:
                    raise StoryError('请先开始游戏')
                if args.inventory:
                    result['inventory'] = present_inventory(story, session.engine.inventory)
                elif args.achievements:
                    result['achievements'] = session.engine.achievements
                else:
                    books = session.engine.rulebooks
                    if args.rules:
                        books = [b for b in books if b['id'] == args.rules]
                        if not books:
                            raise StoryError('尚未获得这本守则')
                    result['rulebooks'] = books
            else:
                operation = any((args.choose is not None, args.choose_index is not None, args.use is not None,
                                 args.continue_story, args.load is not None, args.save is not None, args.bookmark is not None))
                if session.engine is None and operation:
                    raise StoryError('尚无会话，请先运行 --cli')
                advance = False
                if args.batch is not None:
                    if args.batch.stat().st_size > 4*1024*1024:
                        raise StoryError('批量操作文件过大')
                    commands=json.loads(args.batch.read_text(encoding='utf-8'))
                    if not isinstance(commands,list) or not 1<=len(commands)<=3000:
                        raise StoryError('批量操作应为 1 至 3000 个操作组成的列表')
                    if session.engine is None:
                        session.start()
                    transcript=[session.engine.observe()]
                    for number,command in enumerate(commands,1):
                        if not isinstance(command,dict):
                            raise StoryError(f'第 {number} 个操作格式无效')
                        if command=={'action':'continue'}:
                            if not session.apply('advance'):
                                raise StoryError(f'第 {number} 步不能直接继续')
                        elif set(command)=={'action','index'} and command['action']=='choose' and type(command['index']) is int:
                            session.apply('choose',command['index']-1)
                        elif set(command)=={'action','item'} and command['action']=='use':
                            session.apply('use_item',command['item'])
                        else:
                            raise StoryError(f'第 {number} 个操作不受支持')
                        transcript.append(session.engine.observe())
                    session.set_segment([session.engine.observe()])
                    result['batch_steps']=len(commands)
                    result['batch_transcript']=str(output/'playback.json')
                    atomic_json(output/'playback.json',present_segment(transcript))
                elif args.new or session.engine is None:
                    session.start()
                elif args.load is not None:
                    session.load(args.load)
                elif args.save is not None:
                    result['manual_load_point'] = session.capture(args.save)
                elif args.bookmark is not None:
                    session.apply('toggle_bookmark', args.bookmark)
                elif args.choose is not None or args.choose_index is not None:
                    choices = session.engine.choices
                    if args.choose_index is not None:
                        index = args.choose_index - 1
                    else:
                        indexes = [i for i, c in enumerate(choices) if c['text'] == args.choose]
                        if len(indexes) != 1:
                            raise StoryError('选项文本必须完整匹配且唯一')
                        index = indexes[0]
                    session.apply('choose', index)
                    advance = True
                elif args.use is not None:
                    session.apply('use_item', args.use)
                    advance = True
                elif args.continue_story:
                    if not session.apply('advance'):
                        raise StoryError('当前不能直接继续')
                    advance = True
                if advance or session.engine.popup:
                    session.set_segment(run_until_choice(session))
                from .scene_export import SceneExporter
                segment = SceneExporter(story, output).export(present_segment(session.data['segment']))
                engine = session.engine
                status = ('ended' if engine.state['ended'] else 'chapter_intro' if engine.state['chapter_pending']
                          else 'awaiting_choice' if engine.choices else 'awaiting_action')
                result.update(status=status, story_name=story.name, chapter=engine.chapter['title'],
                              chapter_id=engine.state['chapter_id'],
                              chapter_info={key: engine.chapter.get(key) for key in ('id', 'title', 'subtitle', 'description', 'ending')}, page_id=engine.state['page_id'], segment=segment,
                              choices=[{'index': i + 1, 'text': c['text']} for i, c in enumerate(engine.choices)],
                              inventory=present_inventory(story, engine.inventory), rulebooks=engine.rulebooks, achievements=engine.achievements,
                              can_continue=engine.can_advance, auto_load_point=session.data['active'],
                              session_file=str(session.path),
                              current_images={'background': str(output / 'background.png'), 'scene': str(output / 'scene.png')},
                              hint='章节入口已自动存档，--continue 进入章节。' if status == 'chapter_intro' else
                                   '可用 --flowchart 查看已走过的剧情，--load 存档点返回。')
                atomic_json(output / 'observation.json', result)
                session.flush()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (StoryError, OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'ok': False, 'protocol_version': 2, 'error': str(exc)}, ensure_ascii=False))
        return 2
