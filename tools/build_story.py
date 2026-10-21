"""Compile the authored novel and complete source documents into engine JSON.

Scene slices are intentional: production directions and alternative outcomes are
never simply concatenated into the player's dialogue. Run from any directory.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS, ACHIEVEMENTS = [], []
TEXT, TITLES = {}, {}
for filename in ('游客线.md', '员工线.md', '结局集.md'):
    source = (ROOT / 'story' / filename).read_text()
    for match in re.finditer(r'^## (\w+)｜([^\n]+)\n(.*?)(?=^## |\Z)', source, re.M | re.S):
        key, title, body = match.groups()
        TEXT[key], TITLES[key] = body, title

def action(prop, value=None, **kwargs):
    return dict(property=prop, **({'value': value} if value is not None else {}), **kwargs)

def fn(name, **args):
    return {'function': {'name': name, 'args': args}}

def state(**args):
    return fn('set_state', **args)

def jump(target):
    return action('jump', target)

def go(target):
    return action('chapter', target)

def ach(key, title, description):
    if key not in [a['id'] for a in ACHIEVEMENTS]:
        ACHIEVEMENTS.append(dict(id=key, title=title, description=description))
    return action('achievement', key, options='complete')

def bg(key, folder='backgrounds'):
    return action('background', f'art/{folder}/{key}.png', options='fade in', args=.55)

def sound(key):
    return action('sound', f'audio/{key}.wav')

def give(key):
    return action('item', key, options='get')

BOOK_IDS = ['visitor', 'blue', 'outer', 'visitor_note', 'inner', 'red', 'guard', 'director', 'room_note']
BOOKS = {}
source = (ROOT / 'reference/动物园怪谈正文.md').read_text()
for key, match in zip(BOOK_IDS, re.finditer(r'^## [^、]+、([^\n]+)\n(.*?)(?=^## |\Z)', source, re.M | re.S)):
    title, body = match.groups()
    paragraphs = re.split(r'\n\s*\n', body.strip())
    BOOKS[key] = {'book_id': key, 'title': title, 'entries': [
        {'id': f'{key}-{i:02}', 'text': re.sub(r'^\s*> ?', '', p, flags=re.M).strip()}
        for i, p in enumerate(paragraphs, 1) if p.strip()]}

def book(key):
    return action('rules', BOOKS[key])

# Remove author-facing instructions from scene directions, keeping the scene.
OMIT = ('图像要求', '图像：', '声音：', '音效：', '此处对应游客真结局',
        '进入后完整显示', '不把门自动锁死', '这段固定正确处理', '眼部不画成',
        '此后她不再劝吃', '展开地图：', '规则界面关闭后', '后续镜头：')
CUT = ('此处不', '不宣称', '不展示保证', '不为每', '伏笔镜头', '此句是',
       '这里的袭击', '不是新的地图', '这里表现原作', '不借助未', '不跟着他解释',
       '镜头不增加', '不拍救援', '此处只有', '只给一秒', '不重播',
       '明确不是', '蓝衣加班不', '镜头和台词', '不是把纸', '也不需要钻箱',
       '不宣布作者', '画面不证实', '不高速闪烁', '最长线中', '不把所有',
       '不能配成', '游客不知道', '不连续播放', '不做换衣', '若制作',
       '不得因跨线', '不在台词里', '不替另一条', '不是凭空失踪',
       '不叙述他已死', '不使用色情化', '不画“它”', '不给游客线',
       '不叙述完整', '不呈现具体施害者', '不让角色凭空', '不能看到完整',
       '镜头不让', '不让玩家实际', '不虚构', '不要求她', '不由一句',
       '时间锚点', '不放在随时', '不新增', '不把这个选择写成')

def clean(paragraph):
    p = paragraph.strip()
    if not p or p.startswith(('＜', '#', '-')):
        return ''
    if p.startswith('['):
        body = p.strip('[]')
        replacements = {
            '承接V15。背景：':'', '承接E14。':'',
            '承接V03。地图未撕，或只撕了门票。':'',
            '镜头停在入口外，不拍完整异常动物。':'',
            '镜头起初只给躯干，随后一条长长的轮廓贴近玻璃。':'一条长长的轮廓贴近玻璃。',
            '时间以饮水、低声谈学校、长久沉默的短镜头推进到00:35。':'喝水，低声谈学校，又沉默了很久。手机上的时间到了00:35。',
            '这里不切员工行动镜头。':'',
            '这里与游客入口隔着工作人员的视角距离。':'',
            '画面先显示正常标牌，再慢慢露出栏内白色的巨大躯干。':'标牌后面，白色的巨大躯干缓缓抬起。',
            '她不触发“人物长额外眼睛”的必定镜头。':'',
            '墙上的旧便签只给远景，未进入查看，不解锁内容。':'墙上挂着旧便签，离得太远，看不清字。',
            '画面出现一次不超过半秒的主观构图错位：':'一瞬间，',
            '镜头不带她追声。':'她没有追过去。',
            '这里不安排凌晨两点仍当班的保安。':'',
            '她不把便签理解成自己已证明无效的错误规则，也不宣布只要勇敢就免疫。':'她轻轻按平卷起的纸角。',
            '故事不替玩家完成尚未作出的恋爱承诺。':'',
            '折起来的开衫':'折起来的薄毯',
            '开衫的褶皱':'薄毯的褶皱',
            '开衫垫的位置':'薄毯垫的位置',
            '镜头落到仍完整的地图，或者两半无效的门票。':'该握着的那张纸还没有准备好。',
            '画面跳接：':'记忆忽然断开。',
            '省略的时间没有可靠的主观叙述，她不知道换衣的完整经过。':'她已经记不清，自己是什么时候换的衣服。',
            '这里是本作的结局安排，不宣称原作存在一夜晋升的固定制度。':'',
            '桌面的文件被她面前的交接夹板暂时遮住，未接任前不偷分段解锁。':'桌面的文件被交接夹板遮住了。',
            '她不知道同学在里面，因此不能把这个选择写成明知同学待救却抛弃他们。':'',
        }
        for old,new in replacements.items():
            body=body.replace(old,new)
        if body.startswith(OMIT):
            return ''
        body = re.sub(r'(?:音乐|音效|声音)：[^。]*。?', '', body)
        body = re.sub(r'^(?:背景|转场|第三人称远景|第三人称|最后切第三人称远景|景别切近|午后蒙太奇|蒙太奇|时间转场)：?', '', body).lstrip('。')
        sentences = re.split(r'(?<=[。；])', body)
        body = ''.join(s for s in sentences if not any(word in s for word in CUT))
        body = body.replace('此处不继续讨论姓名，不解释员工行为。', '').replace('镜头不回看员工。', '')
        body = body.replace('镜头两页内结束，解释游客看到的背影：此时没有进入海洋馆。', '')
        body = body.replace('这里是本作的结局安排，不宣称原作存在一夜晋升的固定制度。', '')
        body = body.replace('画面可辨是叙事展示，不代表房内另有一盏光源。', '')
        body = body.replace('；不', '。不')
        return '[' + body.strip() + ']' if body.strip() else ''
    return p

class Scene:
    def __init__(self, key, background, music='day', folder='backgrounds', title=None, ending=None):
        self.key, self.nodes, self.count = key, [], 0
        self.chapter = dict(id=key, title=title or TITLES.get(key, key), subtitle=(
            '今天的约会' if key.startswith('V') else '今天的值班' if key.startswith('E') else '动物园 · 留园须知'),
            background=f'art/{folder}/{background}.png', contents=self.nodes)
        if ending:
            self.chapter['ending'] = ending
        CHAPTERS.append(self.chapter)
        self.node('START', action('music', f'audio/{music}.mp3'))

    def node(self, key=None, *actions):
        self.count += 1
        key = key or f'p{self.count:03}'
        assert all(n['id'] != key for n in self.nodes), (self.key, key)
        self.nodes.append(dict(id=key, actions=list(actions)))
        return key

    def say(self, text, key=None):
        p = clean(text)
        if not p:
            return
        speaker = None
        match = re.match(r'^([^：\[（\n]{1,12})：(.*)', p, re.S)
        if match:
            speaker, p = match.groups()
        visuals = []
        night = self.key in ('V10','V11','V12','V13','V14','V15','TV','NV2','NV3')
        red = self.key in ('E09','E10','E11','E12','E13','E14','TE','NE2','BE5','BE6','BE7','BE8','BE9')
        lin = ('lin_night_relief' if self.key=='V15' else 'lin_night' if self.key in ('V10','V12')
               else 'lin_night_scared' if night else 'lin_worried' if self.key in ('V02','V03','V04','V06','V08') else 'lin_day')
        su = ('su_red' if self.key=='E09' else 'su_red_tired' if red else
              'su_blue_tense' if self.key in ('E02','E04','E05','E06') else 'su_blue')
        portraits = {'林夏': lin,
            '苏晚晴':su, '蓝衣员工':'su_blue_tense',
            '红衣员工':'su_red', '许岚':'xulan', '何川':'he', '杜衡':'du', '保安':'du',
            '灰袖黑衣':'gray','缝扣黑衣':'button','陈女士':'chen','魏先生':'wei',
            '园长':'director','邵先生':'passerby','游客':'passerby','路人':'passerby',
            '年轻人':'passerby','售票员':'he'}
        # Endings are full illustration compositions. Environmental pages never
        # retain a sprite from the preceding line and obscure an animal or clue.
        visuals = [action('character', options='hide', slot=s) for s in ('left','center','right')]
        if speaker in portraits and not self.chapter.get('ending') and not getattr(self, 'hide_portraits', False):
            portrait = portraits[speaker]
            if speaker == '林夏' and not night and any(w in p for w in ('就是我们', '只请一个', '笑了')):
                portrait = 'lin_blush'
            visuals.append(action('character', f'art/characters/{portrait}.png', slot='right', options='show'))
        d = action('dialogue', p)
        if speaker:
            d['speaker'] = speaker
        self.node(key, *visuals, d)

    def prose(self, start=None, end=None, source=None):
        text = TEXT[source or self.key]
        if start:
            assert start in text, (self.key, start)
            text = text[text.index(start):]
        if end:
            assert end in text, (self.key, end)
            text = text[:text.index(end)]
        for p in text.splitlines():
            self.say(p)

    def choice(self, key, prompt, options):
        records = []
        for record in options:
            label, dest, *rest = record
            opt = dict(text=label, next_id=dest)
            if rest:
                if isinstance(rest[0], dict) and 'when' in rest[0]:
                    opt.update(rest[0])
                else:
                    opt['actions'] = rest[0]
            records.append(opt)
        self.node(key, action('dialogue', prompt), action('decision', records))

    def end(self, dest=None):
        if dest:
            self.node(None, go(dest))
        self.node('END')

def visitor():
    s = Scene('V01','visitor',folder='covers')
    s.node(None, state(route='visitor'), bg('bus_day'))
    s.prose(end='＜选择：')
    s.choice('date','今天的约定。',[("今天听你的安排。",'ticket',[action('dialogue','真的吗？那第一项是……先进去。后面的还可以商量。',speaker='林夏')]),
        ('先说好，今天只有我们两个？','ticket',[action('dialogue','嗯。没有学习小组，没有临时赶来的室友。……就是我们两个。',speaker='林夏')]),
        ('你把回程也查好了？','ticket',[action('dialogue','查了。但最后一班先不告诉你。怕你刚到就想着走。',speaker='林夏')])])
    s.node('ticket',bg('ticket_window'))
    s.prose('[转场：售票窗口','＜获得：')
    s.node(None, give('ticket'),give('map'),give('wallet'),book('visitor'),ach('arrival','今天的门票','领取完整的游客守则。'),action('popup','已获得门票和游园地图。守则 R 可重读整份文字；背包 B 可以操作物品。查看与阅读不会消耗游戏时间。'))
    s.node(None,bg('gate_day'))
    s.prose('[规则界面关闭后','＜进入V02')
    s.end('V02')
    s = Scene('V02','rabbit_day')
    s.prose(end='＜选择＞')
    s.choice('rabbit','兔子抬起了头。',[("拉住林夏的手腕，一起退到步道中央。",'retreat',[action('dialogue','[林夏立刻站起，跟着我退开，没有再去捡脚边的纸巾。]')]),
        ('先退开，叫林夏跟上。','retreat',[action('dialogue','林夏，先过来。',speaker='我')])])
    s.node('retreat')
    s.prose('[兔子朝我们','＜进入V03')
    s.end('V03')
    s = Scene('V03','rabbit_shadow','unease')
    s.node(None,sound('laugh'))
    s.prose(end='＜操作窗口')
    s.choice('map_window','离开前可以打开背包使用物品，或重读守则。阅读不推进时间。',[
        ('沿步道离开。','depart'),('把门票撕开。','wrong_ticket'),('再听一下，留在当前操作窗口。','listen')])
    s.node('wrong_ticket',fn('tear_ticket'));s.node(None,jump('map_window'))
    s.say('（笑声从围栏里传来。林夏已经握住自己的纸片，等着我。）','listen');s.node(None,jump('map_window'))
    s.node('depart',fn('check',**{'if':{'map_piece':True,'map_held':True},'yes':'V04','no':'BV1'}));s.end()
    s = Scene('V04','ape_fork','unease')
    s.prose(end='＜选择＞')
    s.choice('fork','两条路。地图上本来只有一条。',[('走左路，尽快离开。','left'),('右边人多，跟着他们。','wrong')])
    s.node('wrong',go('BV2'))
    s.node('left',bg('ape_exit'))
    s.prose('[我们没有停下来','＜进入V05');s.end('V05')
    s = Scene('V05','rest_day')
    s.prose(end='＜可选调查')
    s.choice('note_choice','长椅脚边露出一角折纸。',[('走过去捡起来看。','note'),('继续坐着。','lunch')])
    s.node('note',book('visitor_note'),state(read_vnote=True),give('visitor_note'),ach('visitor_note','长椅旁的纸','找到游客留下的纸条。'))
    s.prose('林夏：这个人写到后面','＜公共正文')
    s.node(None,jump('lunch'))
    s.node('lunch');s.prose('[饮料店那边','＜进入V06')
    s.node(None,bg('drink_shop'))
    s.say('[饮料柜旁还有一处纪念品摊。蓝衣离开后，一个黑色袖口出现在柜台后面。]')
    s.say('林夏：水在自动售货机里买就好。那个红瓶子，票上写过不能买。')
    s.choice('shop','零钱 60 元起。可以买普通水，也可以直接离开。',[
        ('从售货机买水（3 元）。','shop',[fn('buy',item='water',price=3)]),
        ('买一包创可贴（5 元）。','shop',[fn('buy',item='firstaid',price=5)]),
        ('仍向黑衣购买兔子血（12 元）。','shop',[fn('buy',item='rabbit_blood',price=12)]),
        ('仍给自己购买兔子玩偶（20 元，成人）。','shop',[fn('buy',item='rabbit_toy',price=20)]),
        ('收好东西，离开柜台。','leave_shop')])
    s.node('leave_shop',go('V06'));s.end()
    s = Scene('V06','elephant_gate','unease')
    s.prose(end='＜选择＞')
    s.choice('elephant','兔耳饰在人群中晃过去。',[('今天不看了，我们走。','retreat'),('只进去看一眼，马上出来。','wrong')])
    s.node('wrong',go('BV3'));s.node('retreat')
    s.prose('[一个保安','＜进入V07');s.end('V07')
    s = Scene('V07','path_afternoon','day')
    s.node(None,bg('lion_public'));s.prose(end='＜选择＞')
    s.choice('photo','今天还要继续走吗？',[
        ('今天到这里，回去一起吃晚饭。','return',[state(return_variant='early')]),
        ('在出口再拍一张，就回去。','return',[state(photo=True,return_variant='photo')]),
        ('再陪我走一小段吧，我想补一张好看的。','continue',[state(photo=True)])])
    s.node('return',fn('visitor_departure',target='NV1'))
    s.node('continue',bg('photo_spot'),ach('photo','风吹过的合照','留下两个人的合照。'))
    s.prose('[背景：15:35','＜时间：16:20');s.end('V08')
    s = Scene('V08','aquarium_rain','unease')
    s.prose(end='＜抵达门前')
    s.node(None,book('outer'),action('popup','规则已更新：海洋馆门口告示。完整告示已收进守则册。'))
    s.prose('林夏：外面说','＜选择。')
    s.choice('aquarium','门开着，里面没有人迎接。',[
        ('按游客守则离开，并打电话报告。','return',[state(return_variant='report')]),
        ('先进去避雨。不换衣服。（违背游客守则）','enter')])
    s.node('return',fn('visitor_departure',target='NV1'))
    s.node('enter');s.prose('我：你先坐一会儿','[音效：')
    s.node(None,bg('aquarium_lobby'),sound('pump'),book('inner'),fn('enter_aquarium'),action('popup','规则已更新：海洋馆内部告示。入馆时间 16:20。'))
    s.prose('林夏：四个小时。','＜进入V09');s.end('V09')
    s = Scene('V09','jelly_day','night')
    s.prose(end='[时间转场：17:05')
    s.node(None,bg('food_shelf'));s.prose('[时间转场：17:05','＜操作窗口')
    s.choice('food','食品标签可以看清。',[
        ('拿普通包装面包和水。','whale',[give('water'),action('dialogue','[我检查包装，林夏接过水，先替我拧开瓶盖。]')]),
        ('先不吃。','whale',[action('dialogue','那水留着，饿了再说。',speaker='林夏')]),
        ('取一份山羊肉放进背包，暂时不吃。','whale',[give('goat_meat')]),
        ('取山羊肉，尝一口。','whale',[give('goat_meat'),fn('strange_food',item='goat_meat')])])
    s.node('whale',bg('whale_swim'),sound('submerged'))
    s.prose('[时间转场：18:10','[时间转场：19:30')
    s.node(None,bg('jelly_day'));s.prose('[时间转场：19:30','＜进入V10');s.end('V10')
    s = Scene('V10','jelly_night','night')
    s.prose(end='＜选择＞')
    s.choice('overnight','20:20，已经满足停留四小时。',[('离馆，找仍在值班的保安帮助离园。','leave'),('按告示借宿，等天亮一起走。','stay')])
    s.node('leave',fn('visitor_departure',target='NV2',night=True))
    s.node('stay',bg('guest_lit'));s.prose('我：先找房间','[两人先在公共水母区')
    s.node(None,bg('jelly_night'));s.prose('[两人先在公共水母区','＜进入V11');s.end('V11')
    s = Scene('V11','hall_night','night')
    s.prose(end='＜选择＞')
    s.choice('black','纸边已经被汗浸软。',[('不交出地图，退回亮着的水母区。','refuse'),('把地图虚线部分交给他。','give',[state(map_held=False)])])
    s.node('give',go('BV5'));s.node('refuse',bg('jelly_night'));s.prose('我：不用。请让一下。','＜两人回到');s.end('V12')
    s = Scene('V12','guest_lit','night')
    s.node(None,sound('knock'));s.prose(end='＜操作：')
    s.choice('lamp','红衣员工等在门边。',[('自己关闭小夜灯。','off',[action('dialogue','好。休息吧。',speaker='红衣员工')]),
        ('还想问她是不是同学。','off',[action('dialogue','我先替你们关。',speaker='红衣员工')])])
    s.node('off',bg('guest_dark'),state(room_lamp=False),sound('switch'))
    s.node(None,action('dialogue','[红衣员工看见床边的兔子玩偶，示意我把它交出来。她将玩偶放进工作推车，没有让我们再碰。]',when={'rabbit_owned':True}),fn('dispose_toy'))
    s.prose('＜公共正文：＞','＜进入V13')
    s.end('V13')
    s = Scene('V13','confession','romance',folder='covers')
    s.node(None,bg('guest_dark'))
    s.prose(end='[床沿轻轻下陷。')
    s.hide_portraits = True
    s.node(None,bg('confession',folder='covers'))
    s.prose('[床沿轻轻下陷。','＜选择。')
    s.choice('confess','她的手也在抖。',[
        ('我也喜欢你。今天本来就想告诉你。','accept',[state(lin_relation='accepted')]),
        ('出去以后，我想在能看清你的地方认真回答。','pending',[state(lin_relation='pending')]),
        ('我很珍惜你，但不想因为害怕答应没想清楚的事。','friends',[state(lin_relation='friends')])])
    s.say('[她的额头轻轻抵住我的肩膀。]','accept');s.say('林夏：那明天也约我。别只约今天。');s.say('我：好。');s.node(None,jump('noise'))
    s.say('林夏：那我记住了。不许假装没听见。','pending');s.say('我：嗯，先一起出去。');s.node(None,jump('noise'))
    s.say('[她沉默了一会儿，手指没有突然抽走。]','friends');s.say('林夏：……谢谢你没有骗我。那明天，也一起回去吧。');s.say('我：好。');s.node(None,jump('noise'))
    s.node('noise',sound('metal'),action('music',options='stop'),bg('guest_dark'))
    s.prose('[门外一阵','＜进入V14');s.end('V14')
    s = Scene('V14','guest_dark','night')
    s.node(None,sound('drag'));s.prose(end='＜最后夜间')
    s.choice('night_window','门外的声音停下了。',[('保持关灯、闭门和握纸，留在她身边。','safe'),('重新开小夜灯。','lamp_on'),('把门打开一条缝，查看走廊。','door_open')])
    s.node('lamp_on',bg('guest_lit'),state(room_lamp=True),sound('switch'))
    s.choice('lamp_confirm','[水母小夜灯亮起，林夏看向我的手。]',[('立刻关回去。','reset'),('保持亮灯，继续等。','bad',[state(return_variant='lamp')])])
    s.node('door_open',bg('hall_night'),state(room_open=True),sound('door'))
    s.choice('door_confirm','[凉意从门缝贴着脚踝进来。林夏还坐在原处。]',[('立刻关上门。','reset'),('走出去，追查声音。','bad',[state(return_variant='door')])])
    s.node('bad',go('BV6'))
    s.node('reset',bg('guest_dark'),state(room_lamp=False,room_open=False));s.prose('[我停住','＜公共安全正文')
    s.node(None,jump('safe'));s.node('safe',bg('guest_dark'));s.prose('＜公共安全正文：＞','＜06:00');s.end('V15')
    s = Scene('V15','aquarium_dawn','romance')
    s.prose(end='＜若goat_eaten')
    s.node(None,fn('check',**{'if':{'goat_eaten':True},'yes':'food_bad','no':'exit','kind':'jump'}))
    s.node('food_bad',state(return_variant='dawn'),go('BV4'))
    s.node('exit',bg('zoo_exit_dawn'));s.prose('[路径按眼前','＜lin_relation')
    s.node(None,fn('finish'));s.end()

def employee():
    s = Scene('E01','employee','day',folder='covers')
    s.node(None,state(route='employee'),bg('staff_room'))
    s.prose(end='＜完整显示第二节')
    s.node(None,book('blue'),give('handbook'),give('water'),action('popup','完整员工守则已更新，含隐藏附文。手册已放进背包。'))
    s.prose('（上了几周班','[转场：09:20')
    s.node(None,bg('drink_back'));s.prose('[转场：09:20','＜操作窗口')
    s.choice('stock','异常货物处理。',[('收起、标记并妥善保存。','store'),('先去巡查，回来再说。','defer')])
    s.node('store',state(blood_stored=True));s.prose('＜完成时：＞','＜未完成时')
    s.node(None,go('E02'));s.node('defer');s.prose('＜未完成时：＞','＜进入E02');s.end('E02')
    s = Scene('E02','rabbit_day','unease')
    s.prose(end='＜操作窗口')
    s.node(None,sound('laugh'))
    s.choice('handbook_window','笑声并非来自游客。现在可以使用背包里的手册。',[
        ('带着准备好的纸页，去大象园区。','check'),('忽略笑声，继续普通巡查。','ignore')])
    s.node('ignore',go('BE1'))
    s.node('check',fn('check',**{'if':{'staff_page':True},'yes':'deliver','no':'failed','kind':'jump'}))
    s.node('failed',go('BE1'))
    s.node('deliver',bg('elephant_gate'));s.prose('[她沿虚线撕开纸页','＜固定执行')
    s.node(None,state(page_delivered=True),ach('page_delivery','把纸留在草坪','完成员工手册末页的处理。'))
    s.prose('[纸落进草里','＜进入E03');s.end('E03')
    s = Scene('E03','ape_closed','unease');s.prose();s.end('E04')
    s = Scene('E04','elephant_abnormal','danger')
    s.node(None,sound('breath'));s.prose(end='[杜衡在入口')
    s.node(None,bg('elephant_gate'));s.prose('[杜衡在入口','[到安保室附近')
    s.node(None,sound('cry'),bg('security'));s.prose('[到安保室附近','＜进入E05');s.end('E05')
    s = Scene('E05','drink_back','unease');s.prose(end='＜操作窗口')
    s.choice('equipment','救援前的物资检查。',[('核对储物处，领取兔子血。','carry'),('先把游客带去。','walk')])
    s.node('carry',fn('collect_blood'));s.say('[我核对瓶子和记录，把它放到随手可取的位置。]');s.node(None,jump('walk'))
    s.node('walk');s.prose('[走向工作通道途中','[背景：狮子园区工作通道')
    s.node(None,bg('lion_work'),sound('lion'));s.prose('[背景：狮子园区工作通道','＜若blood_carried')
    s.node(None,fn('check',**{'if':{'blood_carried':True},'yes':'ready','no':'empty','kind':'jump'}))
    s.node('empty');s.prose('[苏晚晴的手碰到空口袋','＜选择：“退回')
    s.choice('empty_choice','手里没有兔子血。',[('退回指定位置，等何川取来。','ready',[fn('collect_blood')]),('我先把那头引开。','unarmed')])
    s.node('unarmed',go('BE2'))
    s.node('ready');s.prose('＜公共处理：＞','＜选择＞')
    s.choice('lion','第一头白狮跑过来了。',[('泼向第一头跑来的，马上离开近处。','withdraw'),('泼出后留下，盯清多出来的那头。','watch')])
    s.node('watch',go('BE4'))
    s.node('withdraw',action('item','work_blood',options='remove'),state(blood_carried=False),sound('lion'))
    s.prose('[液体离开瓶口','[之后由原本')
    s.node(None,bg('lion_public'));s.prose('[之后由原本','＜进入E06');s.end('E06')
    s = Scene('E06','staff_room','unease')
    s.node(None,sound('tinnitus'));s.prose(end='＜选择＞')
    s.choice('symptoms','症状已经持续超过五分钟。',[('立刻停工去狮子园区，请何川接替。','stop',[state(symptom_action='stop')]),
        ('把剩下的交接做完再说。','delay',[state(symptom_action='delay')]),
        ('先找镜子仔细看，再决定。','delay',[state(symptom_action='check_mirror')])])
    s.node('delay',go('BE3'));s.node('stop',bg('lion_four'));s.prose('何川：我接。','＜进入E07');s.end('E07')
    s = Scene('E07','path_afternoon','day')
    s.prose(end='＜选择＞')
    s.choice('shift','先休息，再决定是否接班。',[('今天到这里，交清物品回去。','off',[state(return_variant='blue')]),('休息够了，接下这段加班。','overtime',[state(rested=True)])])
    s.node('off',go('NE1'));s.node('overtime',bg('staff_room'));s.prose('苏晚晴：我接。','[时间：00:25')
    s.node(None,bg('blue_night'),action('music','audio/night.mp3'));s.prose('[时间：00:25','＜时间：00:35');s.end('E08')
    s = Scene('E08','aquarium_night','night')
    s.node(None,book('outer'));s.prose(end='＜完整显示第六节')
    s.node(None,book('red'),give('red_manual'),action('popup','完整海洋馆员工守则已更新。接班选择会违背蓝衣员工守则，换衣并不是已知的安全保证。'))
    s.prose('[苏晚晴翻到最后一条','＜选择＞')
    s.choice('red_offer','先看完整本手册，再回答。',[('我不能接，请您另作安排。','refuse',[state(return_variant='refuse')]),('我试着做，请先告诉我负责哪一段。','accept')])
    s.node('refuse',go('NE1'));s.node('accept');s.prose('许岚：左边三间','[进入后完整显示')
    s.node(None,bg('jelly_night'),book('inner'),state(world='inside'))
    s.say('[我扣好红色工作服的袖口。许岚指向工作台上的器械，演示了使用前需要确认的几处位置。]')
    s.prose('许岚：别想着打赢谁','＜进入E09');s.end('E09')
    s = Scene('E09','hall_night','night')
    s.prose(end='＜本场操作')
    s.choice('rooms_menu','左侧工作表。读规则和看背包不推进时钟。',[
        ('检查左一：陈女士。','room1',{'when':{'room1':False}}),
        ('检查左二：已经睡着的人。','room2',{'when':{'room2':False}}),
        ('检查左三：门内有人应声。','room3',{'when':{'room3':False}}),
        ('核对三间记录，交回检查表。','verify'),
        ('先搁置检查，休息到 01:15 以后。','neglect',{'when':{'rooms_complete':False}})])
    for index, start, end in ((1,'### 左一','### 左二'),(2,'### 左二','### 左三'),(3,'### 左三','### 检查表')):
        s.node(f'room{index}',bg('guest_lit'),sound('knock'))
        s.prose(start,end)
        s.node(None,bg('hall_night'),fn('mark_room',room=f'room{index}'),sound('switch'),jump('rooms_menu'))
    s.node('verify',fn('complete_rooms'))
    s.choice('neglect','还未确认的夜灯不会因为等待自动变成已完成。',[
        ('返回检查表。','rooms_menu'),('仍搁置，等到 01:15 之后。','late')])
    s.node('late',fn('check',**{'if':{'room1':True,'room2':True,'room3':True},'yes':'rooms_done','no':'lamp_failure','kind':'jump'}))
    s.node('lamp_failure',go('BE5'))
    s.node('rooms_done',ach('three_doors','三扇门都关好了','完成所有客房夜灯检查。'))
    s.prose('[00:59。','[一声金属撞击');s.node(None,sound('metal'));s.prose('[一声金属撞击','＜进入E10');s.end('E10')
    s = Scene('E10','aquarium_night','danger')
    s.node(None,sound('cry'));s.prose(end='＜选择＞')
    s.choice('intruder','门框又响了一声。',[
        ('保持距离，与许岚配合制止闯入。','hold'),
        ('放下器械，走近把他劝出去。','approach',[state(return_variant='comfort')]),
        ('独自冲上去，徒手把他拖走。','approach',[state(return_variant='fight')]),
        ('离开岗位，出去看他指的地方。','outside')])
    s.node('approach',go('BE6'));s.node('outside',go('BE7'))
    s.node('hold',sound('electric'));s.prose('[苏晚晴没有追着手去抓','＜进入E11');s.end('E11')
    s = Scene('E11','food_shelf','night')
    s.prose(end='＜操作：食品')
    s.choice('food_work','食品需要单独收存。',[('放进工作推车，带往指定收纳箱。','food_done',[state(food_cleared=True)])])
    s.node('food_done');s.prose('[她回左二房间','＜操作：周边')
    s.choice('toy_work','床边露出白色玩具的一角。',[('按红衣职责收起兔子周边。','toy_done',[state(toy_removed=True)])])
    s.node('toy_done',bg('whale_dead'),sound('submerged'))
    s.prose('[背景：鲸鱼区','[食品与玩具放入')
    s.node(None,bg('storage'));s.prose('[食品与玩具放入','＜可选调查')
    s.choice('room_note','旁边的资料板夹着一张旧纸。',[('取下纸张，完整读一遍。','read_note'),('不查看，继续工作。','outage')])
    s.node('read_note',book('room_note'),give('room_note'),state(read_roomnote=True),ach('room_note','柜边的旧纸','找到客房的纸张。'))
    s.prose('＜已读时：＞','＜公共正文');s.node(None,jump('outage'))
    s.node('outage',sound('switch'),bg('whale_dead'),action('effect',{'type':'fade','duration':1.2,'blocking':False}))
    s.prose('＜公共正文：＞','＜选择＞')
    s.choice('darkness','远处水母区的光仍稳定。',[('不找开关，沿已知路线退回水母区。','return'),('先躲进刚才的收纳箱。','box')])
    s.node('box',go('BE8'));s.node('return',go('E12'));s.end()
    s = Scene('E12','jelly_night','night')
    s.prose(end='[02:35')
    s.node(None,bg('controlroom'));s.prose('[02:35','[03:35')
    s.node(None,bg('hall_night'),sound('steps'));s.prose('[03:35','苏晚晴：下一段')
    s.node(None,bg('jelly_night'));s.prose('苏晚晴：下一段','＜进入E13');s.end('E13')
    s = Scene('E13','aquarium_lobby','night')
    s.prose(end='＜操作窗口')
    s.node(None,bg('jelly_night'))
    s.choice('charge_menu','星期日的工作台。充电项尚需核对。',[
        ('连接小夜灯充电设备，检查指示状态。','charge',[state(charge_done=True)]),
        ('先核对最后交接。','pre_review')])
    s.say('[我逐一接好已经不用的小夜灯，确认充电指示正常，再去核对其他交接项。]','charge')
    s.node(None,sound('switch'),jump('review'))
    s.node('pre_review',fn('check',**{'if':{'charge_done':True},'yes':'review','no':'missing','kind':'jump'}))
    s.node('review');s.prose('[许岚开始最后交接','[05:55。')
    s.node(None,bg('whale_dead'));s.prose('[05:55。','＜选择＞')
    s.choice('handover','05:55。深处的轮廓依然静止。',[
        ('核对清单，准备按时交班。','verify'),('再留一轮，把那个投影看明白。','extra')])
    s.node('extra',go('BE9'))
    s.node('verify',fn('check',**{'if':{'charge_done':True},'yes':'finish_work','no':'missing','kind':'jump'}))
    s.say('许岚：充电那格还是空的。还来得及，现在去补。','missing');s.node(None,jump('charge_menu'))
    s.node('finish_work',bg('aquarium_dawn'),ach('handover','到点交班','完成夜班清单并按时离岗。'))
    s.prose('[苏晚晴把笔夹回记录板','＜duty_finished');s.end('E14')
    s = Scene('E14','security','romance')
    s.prose(end='＜可选调查')
    s.choice('guard_note','安保室开着门，墙上便签的一角卷起。',[('走近，查看墙面便签。','read_guard'),('直接去办公室。','office')])
    s.node('read_guard',book('guard'),give('guard_note'),state(read_guardnote=True),ach('guard_note','守在门口的人','读过保安的便签条。'))
    s.prose('＜已读时：＞','＜公共正文');s.node(None,jump('office'))
    s.node('office',bg('office'));s.prose('＜公共正文：＞','＜选择＞')
    s.choice('offer','园长等着你的回答。',[('我愿意，请把需要知道的交给我。','yes'),('现在还不能接，我想先做好自己能负责的工作。','no')])
    s.node('yes',go('TE'));s.node('no',go('NE2'));s.end()

def endings():
    for key in ('TV','TE','NV1','NV2','NV3','NE1','NE2','BV1','BV2','BV3','BV4','BV5','BV6','BE1','BE2','BE3','BE4','BE5','BE6','BE7','BE8','BE9'):
        bad = key.startswith('B')
        s = Scene(key,key,'danger' if bad else 'romance',folder='endings',ending='death' if bad else 'normal')
        s.node(None,state(ending=key))
        if key == 'NV1':
            s.node(None,fn('check',**{'if':{'return_variant':'report'},'yes':'report','no':'early','kind':'jump'}))
            s.node('early',fn('check',**{'if':{'photo':True},'yes':'photo','no':'simple','kind':'jump'}))
            s.node('simple');s.prose('＜V07直接离开','＜V07出口合照');s.node(None,jump('common'))
            s.node('photo');s.prose('＜V07出口合照','＜V08门前');s.node(None,jump('common'))
            s.node('report');s.prose('＜V08门前','＜公共结尾');s.node(None,jump('common'))
            s.node('common');s.prose('＜公共结尾：＞')
        elif key == 'NV3':
            s.prose(end='＜lin_relation=pending')
            s.node(None,fn('check',**{'if':{'lin_relation':'pending'},'yes':'pending','no':'friends','kind':'jump'}))
            s.node('pending');s.prose('＜lin_relation=pending','＜lin_relation=friends');s.node(None,jump('common'))
            s.node('friends');s.prose('＜lin_relation=friends','＜公共镜头');s.node(None,jump('common'))
            s.node('common');s.prose('＜公共镜头：＞')
        elif key == 'NE1':
            s.node(None,fn('check',**{'if':{'return_variant':'refuse'},'yes':'refuse','no':'blue','kind':'jump'}))
            s.node('blue');s.prose('＜E07蓝衣','＜E08拒绝');s.node(None,jump('common'))
            s.node('refuse');s.prose('＜E08拒绝','＜公共结尾');s.node(None,jump('common'))
            s.node('common');s.prose('＜公共结尾：＞')
        elif key == 'BV6':
            s.node(None,fn('check',**{'if':{'return_variant':'door'},'yes':'door','no':'lamp','kind':'jump'}))
            s.node('lamp');s.prose('＜开灯版本','＜开门版本');s.node(None,jump('common'))
            s.node('door');s.prose('＜开门版本','＜公共正文');s.node(None,jump('common'))
            s.node('common');s.prose('＜公共正文：＞')
        elif key == 'TE':
            s.prose(end='＜接任完成')
            s.node(None,book('director'),action('popup','规则已更新：办公室文件。十五条完整收录。'))
            s.prose('[规则界面关闭。')
        elif key == 'TV':
            s.prose(end='我：包里。')
            s.node(None,fn('check',**{'if':{'ticket_intact':True},'yes':'ticket_whole','no':'ticket_torn','kind':'jump'}))
            s.say('我：包里。','ticket_whole');s.say('林夏：先收着。以后……也不用拿出来给别人看。');s.node(None,jump('morning'))
            s.say('我：包里。两半。','ticket_torn');s.say('林夏：那也先收着。');s.node(None,jump('morning'))
            s.node('morning');s.prose('[她看向马路','＜photo=true')
            s.node(None,fn('check',**{'if':{'photo':True},'yes':'photo','no':'common','kind':'jump'}))
            s.node('photo');s.prose('[她打开昨天下午','[最后切第三人称');s.node(None,jump('common'))
            s.node('common');s.prose('[最后切第三人称')
        else:
            s.prose()
        s.node(None,ach('end_'+key,TITLES[key].split('·',1)[-1],'抵达一个故事结局。'))
        s.say('＜'+TITLES[key]+'＞')  # Explicit final page below, not a production tag.
        s.node(None,action('dialogue',TITLES[key]+'\n\n这段故事结束了。可以在设定中查看成就，或回到已走过的章节。'))
        s.end()
    s = Scene('BX1','BX1','danger',folder='endings',title='坏结局·带回家的纪念品',ending='death')
    s.node(None,state(ending='BX1'))
    for line in [
        '[出口的门就在前面。我想把包背得高一点，指尖碰到一只柔软的耳朵。]',
        '（只是一件玩具。）',
        '林夏：你的包……',
        '[玩具的珠眼仍很普通。真正让我停下的是自己的手：我知道该把它放开，手指却一根接一根收紧。]',
        '[林夏先拉住包带，想替我卸下来。我却下意识躲开，连自己也不知道为什么。]',
        '我：别碰。',
        '[那句话出来的时候，喉咙里还夹着另一种很轻的声音。林夏看着我，脸上的表情慢慢变了。]',
        '（我不是在对你说。）',
        '[后来他们离出口越来越远。女孩仍叫着同一个名字，抱着白色东西的人却只往树荫里退；再后来，包落在步道上，两个柔软的轮廓紧紧挤在一起，已经看不出哪个先被装进包里。]']:
        s.say(line)
    s.node(None,ach('end_BX1','带回家的纪念品','抵达一个故事结局。'),action('dialogue','坏结局 · 带回家的纪念品'))
    s.end()

def items():
    def item(key,name,desc,icon,callback=None,**args):
        return dict(id=key,name=name,description=desc,icon=f'art/items/{icon}.png',
                    on_use=[fn(callback,**args)] if callback else [])
    return [
        item('wallet','零钱包','出门时准备了 60 元零钱。使用：数一数剩余的钱。','coins','wallet'),
        item('ticket','动物园门票','背面印有完整游客守则。查看只会读票，不会撕坏门票。','ticket','use_ticket'),
        item('map','游园地图','印有游园路线和虚线。使用：沿虚线撕下并握住；剩余地图仍会保留。','map','use_map'),
        item('map_piece','虚线纸片','手心已经被纸边压出印痕。保持握持，直到彻底离园。','map_piece'),
        item('handbook','员工手册','完整守则见守则册。在兔子园区的笑声操作窗口使用：撕下末页并握住。','handbook','use_handbook'),
        item('red_manual','海洋馆员工手册','完整手册已收录在守则册。红色封面并不许诺安全。','red_manual'),
        item('water','瓶装水','普通的密封饮用水。使用：喝水或与同行的人分享。','water','water'),
        item('rabbit_blood','兔子血','黑衣摊主出售的瓶子。游客守则明确说不要购买。使用会饮用，无法撤回。','blood','strange_food',item='rabbit_blood'),
        item('goat_meat','山羊肉','冷藏盒里的异常食品。内部告示明确说不要吃。使用会食用，无法撤回。','meat','strange_food',item='goat_meat'),
        item('work_blood','工作用兔子血','按蓝衣职责妥善保存，供异常白狮处理之用。交给现场工作步骤使用。','blood'),
        item('rabbit_toy','兔子玩偶','给自己买的白色玩偶。使用只检查。游客守则禁止成年人购买。','rabbit_toy','rabbit_toy'),
        item('firstaid','创可贴','用在鞋子磨红的脚跟上。没有对异常的治疗作用。','firstaid','firstaid'),
        item('visitor_note','长椅旁的纸条','完整文字已收入守则册。纸角软了，字迹仍很急。','note'),
        item('room_note','客房的纸张','鲸鱼区资料柜里的旧纸，完整收录在守则册。','note'),
        item('guard_note','保安便签记录','抄下墙面便签的内容。完整文字可在守则册查看。','note')]

def main():
    s=Scene('prologue','opening','day',folder='covers',title='动物园 · 留园须知')
    s.say('[一个再普通不过的周末。有人约好了见面，有人准备开始值班。]')
    s.choice('route','选择今天的视角。建议先游玩约会，再来看另一面的夜晚。',[
        ('今天的约会 · 游客线','visitor'),('今天的值班 · 员工线','employee')])
    s.node('visitor',go('V01'));s.node('employee',go('E01'));s.end()
    visitor();employee();endings()
    # Setup-only nodes execute into their next page, so changing background,
    # granting an item or entering a branch does not require an empty click.
    for chapter in CHAPTERS:
        nodes=chapter['contents']
        for index,node in enumerate(nodes[:-1]):
            if node['id']=='END':
                continue
            if not any(a.get('property') in ('dialogue','decision','popup','jump','chapter') for a in node['actions']):
                node['actions'].append(jump(nodes[index+1]['id']))
    for key,title,desc in [('paper_ready','掌心的一小片','主动处理地图虚线部分。'),('small_care','先歇一下手','使用普通饮用水。'),
                           ('changed_item','包里不是原来的东西','注意到异常物品发生变化。'),('small_patch','新鞋与创可贴','使用普通用品照顾同行的人。')]:
        ach(key,title,desc)
    payload=dict(StoryName='动物园 · 留园须知',script='logic.py',
        title=dict(subtitle='今天的约会，和今晚的值班。\n请保管好你的地图。',background='art/covers/opening.png'),
        chapters=CHAPTERS,items=items(),achievements=ACHIEVEMENTS)
    path=ROOT/'data/story.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(CHAPTERS)} chapters / {sum(len(c["contents"]) for c in CHAPTERS)} pages / {len(ACHIEVEMENTS)} achievements / {len(BOOKS)} whole documents')

if __name__=='__main__':
    main()
