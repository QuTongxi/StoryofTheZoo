"""Deterministic game callbacks. All persistent choices live in save state."""
INITIAL_STATE = {
    'route': '', 'map_piece': False, 'map_held': False, 'ticket_intact': True,
    'lin_relation': 'undecided', 'photo': False, 'goat_eaten': False,
    'room_lamp': True, 'room_open': False, 'world': 'outside', 'money': 60,
    'water_shared': False, 'rabbit_owned': False, 'blood_stored': False,
    'blood_carried': False, 'staff_page': False, 'page_delivered': False,
    'room1': False, 'room2': False, 'room3': False, 'rooms_complete': False, 'charge_done': False,
    'toy_removed': False, 'food_cleared': False, 'read_vnote': False,
    'read_roomnote': False, 'read_guardnote': False, 'rested': False,
    'return_variant': '', 'symptom_action': '', 'ending': '', 'window': '',
}


def set_state(state, args, context):
    state.update(args)


def check(state, args, context):
    passed = all(state.get(key) == value for key, value in args['if'].items())
    return [{'property': args.get('kind', 'chapter'), 'value': args['yes'] if passed else args['no']}]


def finish(state, args, context):
    target = args.get('target') or ('BV4' if state['goat_eaten'] else ('TV' if state['lin_relation'] == 'accepted' else 'NV3'))
    state['ending'] = target
    return [{'property': 'chapter', 'value': target}]


def use_map(state, args, context):
    if state['map_piece']:
        return [{'property': 'dialogue', 'value': '我确认撕下的地图仍握在手里，没有松开。'}]
    state.update(map_piece=True, map_held=True)
    return [
        {'property': 'item', 'options': 'get', 'value': 'map_piece'},
        {'property': 'sound', 'value': 'audio/paper.wav'},
        {'property': 'achievement', 'options': 'complete', 'value': 'paper_ready'},
        {'property': 'dialogue', 'value': '我沿虚线小心撕下地图的一部分，握在左手。剩余地图折好收进包里。'}]


def use_ticket(state, args, context):
    return [{'property': 'dialogue', 'value': '门票背面是完整的游客守则。可打开守则页面查看；门票和带虚线的地图是两件东西。'}]


def tear_ticket(state, args, context):
    state['ticket_intact'] = False
    return [{'property': 'dialogue', 'value': '门票裂成两半，地图却仍完整。撕错东西了；现在还来得及重新打开背包。'}]


def use_handbook(state, args, context):
    if state['staff_page']:
        return [{'property': 'dialogue', 'value': '沿虚线撕下的那页已经处理过。其余工作要求仍可从守则页查看。'}]
    if context['chapter_id'] != 'E02':
        return [{'property': 'dialogue', 'value': '我核对最后一页的虚线位置，随后合好手册。需要的时候再处理。'}]
    state['staff_page'] = True
    return [{'property': 'sound', 'value': 'audio/paper.wav'},
            {'property': 'dialogue', 'value': '我沿最后一页虚线撕下纸并握住，准备前往大象园区的草坪。'}]


def buy(state, args, context):
    price, item = args['price'], args['item']
    if state['money'] < price:
        return [{'property': 'popup', 'title': '零钱', 'value': '零钱不够。这次先不买了。'}]
    state['money'] -= price
    if item == 'rabbit_toy':
        state['rabbit_owned'] = True
    return [{'property': 'item', 'options': 'get', 'value': item},
            {'property': 'sound', 'value': 'audio/coin.wav'},
            {'property': 'dialogue', 'value': f"[买好的东西已收进背包。零钱还剩 {state['money']} 元。]"}]


def wallet(state, args, context):
    return [{'property':'dialogue','value':f"[零钱包里还有 {state['money']} 元。]"}]


def water(state, args, context):
    state['water_shared'] = True
    return [{'property': 'item', 'options': 'remove', 'value': 'water'},
            {'property': 'achievement', 'options': 'complete', 'value': 'small_care'},
            {'property': 'sound', 'value': 'audio/water.wav'},
            {'property': 'dialogue', 'speaker': '林夏' if state['route'] == 'visitor' else '苏晚晴',
             'value': '瓶盖我来拧。你先歇一下手。' if state['route'] == 'visitor' else '喝一口水，再确认下一项工作。'}]


def enter_aquarium(state, args, context):
    state['world'] = 'inside'
    count = context['inventory'].get('rabbit_blood', 0)
    if not count:
        return []
    return [{'property': 'item', 'options': 'remove', 'value': 'rabbit_blood', 'count': count},
            {'property': 'item', 'options': 'get', 'value': 'goat_meat', 'count': count},
            {'property': 'dialogue', 'value': '包里原本装着瓶子的地方，多了一盒冰冷的东西。标签的模样也变了。林夏没有碰它，只把包重新合好。'},
            {'property': 'achievement', 'options': 'complete', 'value': 'changed_item'}]


def strange_food(state, args, context):
    if state['route'] != 'visitor':
        return [{'property': 'dialogue', 'value': '这是需要按工作要求处理的东西，不能食用。'}]
    state['goat_eaten'] = True
    return [{'property': 'item', 'options': 'remove', 'value': args['item']},
            {'property': 'sound', 'value': 'audio/unease.wav'},
            {'property': 'dialogue', 'value': '冰冷的味道落进喉咙。咽下去以后，才发现那种铁一样的气味不是正常食物。林夏把剩下的东西拿远，递来水。'}]


def rabbit_toy(state, args, context):
    return [{'property': 'dialogue', 'value': '白色兔子玩偶很普通，黑色珠眼正好朝向我。票背写过成年人的购买限制，把它当成普通纪念品也不能让那条要求消失。'}]


def firstaid(state, args, context):
    return [{'property': 'item', 'options': 'remove', 'value': 'firstaid'},
            {'property': 'achievement', 'options': 'complete', 'value': 'small_patch'},
            {'property': 'dialogue', 'speaker': '林夏', 'value': '谢谢。你先别动，我自己贴就好。……你怎么比我还紧张呀。'}]


def dispose_toy(state, args, context):
    count = context['inventory'].get('rabbit_toy', 0)
    state['rabbit_owned'] = False
    return ([{'property': 'item', 'options': 'remove', 'value': 'rabbit_toy', 'count': count}] if count else [])


def visitor_departure(state, args, context):
    if state['goat_eaten']:
        state['return_variant'] = 'night' if args.get('night') else 'day'
        return [{'property': 'chapter', 'value': 'BV4'}]
    if state['rabbit_owned']:
        return [{'property': 'chapter', 'value': 'BX1'}]
    return [{'property': 'chapter', 'value': args.get('target', 'NV1')}]


def inspect(state, args, context):
    return [{'property': 'dialogue', 'value': args['text']}]


def collect_blood(state, args, context):
    state['blood_stored'] = state['blood_carried'] = True
    if not context['inventory'].get('work_blood'):
        return [{'property': 'item', 'options': 'get', 'value': 'work_blood'}]
    return []


def complete_rooms(state, args, context):
    if all(state[k] for k in ('room1', 'room2', 'room3')):
        return [{'property': 'jump', 'value': 'rooms_done'}]
    return [{'property': 'popup', 'value': '记录表还有没有确认关闭的夜灯。可以继续检查。'},
            {'property': 'jump', 'value': 'rooms_menu'}]


def mark_room(state, args, context):
    state[args['room']] = True
    state['rooms_complete'] = all(state[k] for k in ('room1','room2','room3'))


def handover(state, args, context):
    if not state['charge_done']:
        return [{'property': 'popup', 'value': '今天是周日。充电项还没有完成，先回工作台。'},
                {'property': 'jump', 'value': 'charge_menu'}]
    return [{'property': 'chapter', 'value': 'E14'}]
