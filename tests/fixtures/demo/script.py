"""Story-owned callbacks: mutable save state is passed explicitly by the core."""
INITIAL_STATE = {'map_reads': 0, 'route': None, 'escorted': False, 'safe': False}


def read_map(state, args, context):
    state['map_reads'] = 1


def remember_route(state, args, context):
    state['route'] = args['route']


def set_safe(state, args, context):
    state['safe'] = args['value']


def show_sample(state, args, context):
    if context['chapter_id'] == 'meadow':
        state['escorted'] = True
        return [
            {'property': 'achievement', 'options': 'complete', 'value': 'helper'},
            {'property': 'dialogue', 'value': '巡查员接过试管，将它放进冷藏箱：“谢谢。广播今天出了些问题，我可以带你沿蓝色步道离园。”'}]
    # Restore the sample if it cannot be delivered here; consume is settled before callbacks.
    return [
        {'property': 'item', 'options': 'get', 'value': 'goat_blood'},
        {'property': 'dialogue', 'value': '这里没有能接收样本的巡查员。你将密封试管收回背包。'}]
