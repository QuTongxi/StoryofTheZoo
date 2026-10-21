"""A visited chapter tree. Page checkpoints remain available separately."""


def is_prefix(before, after):
    return (len(before['actions']) <= len(after['actions'])
            and before['actions'] == after['actions'][:len(before['actions'])]
            and before['calls'] == after['calls'][:len(before['calls'])])


def chapter_tree(story, points, current):
    nodes, entries = [], []

    def ancestor(snapshot, *, strict=False):
        candidates = [(i, entry) for i, entry in enumerate(entries)
                      if (not strict or len(entry['actions']) < len(snapshot['actions']))
                      and is_prefix(entry, snapshot)]
        return max(candidates, key=lambda pair: len(pair[1]['actions']))[0] if candidates else None

    for point in points:
        snapshot = point['snapshot']
        state = snapshot['state']
        index = ancestor(snapshot)
        chapter = story.chapter(state['chapter_id'])
        is_entry = state['chapter_pending']
        # Re-loading or restarting the exact same entry reuses its tree card.
        duplicate = next((i for i, entry in enumerate(entries) if entry == snapshot), None) if is_entry else None
        if duplicate is not None:
            index = duplicate
        elif is_entry or index is None or nodes[index]['chapter_id'] != state['chapter_id']:
            parent = ancestor(snapshot, strict=True)
            node = {'id': point['id'], 'load_point': point['id'], 'chapter_id': chapter['id'],
                    'title': chapter['title'], 'description': chapter.get('description', chapter.get('subtitle', '')),
                    'parent': nodes[parent]['id'] if parent is not None else None,
                    'children': [], 'entry': is_entry, 'completed': False,
                    'ending': chapter.get('ending'), 'current': False}
            index = len(nodes)
            nodes.append(node)
            entries.append(snapshot)
            if parent is not None:
                nodes[parent]['children'].append(node['id'])
        if state['ended']:
            nodes[index]['completed'] = True
            nodes[index]['ending'] = chapter.get('ending', 'normal')
    if current:
        index = ancestor(current)
        if index is not None:
            nodes[index]['current'] = True
    return {'roots': [node['id'] for node in nodes if node['parent'] is None], 'nodes': nodes}


def tree_text(tree):
    """Plain-text companion for CLI clients; never execute story callbacks."""
    by_id = {node['id']: node for node in tree['nodes']}
    lines = []
    pending = [(root, '', i == len(tree['roots']) - 1) for i, root in reversed(list(enumerate(tree['roots'])))]
    while pending:
        node_id, prefix, last = pending.pop()
        node = by_id[node_id]
        ending = {'normal': '结局', 'death': '死亡结局'}.get(node['ending'], '章节')
        lines.append(prefix + ('└─ ' if last else '├─ ') + node['title'] + f' [{ending}]')
        continuation = prefix + ('   ' if last else '│  ')
        if node['description']:
            lines.append(continuation + node['description'].replace('\n', ' '))
        for i in range(len(node['children']) - 1, -1, -1):
            pending.append((node['children'][i], continuation, i == len(node['children']) - 1))
    return '\n'.join(lines)
