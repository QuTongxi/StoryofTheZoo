"""Project core observations into AI-readable content, excluding human UI prompts."""
from copy import deepcopy


def audio_view(observation):
    audio = observation.get('audio', {})
    return {'music': audio.get('music'),
            'voices': [audio['voice']] if audio.get('voice') else [],
            'sounds': [audio['sound']] if audio.get('sound') else []}


def present_segment(observations):
    """Collapse popup-only waits without losing dialogue, rule updates or audio."""
    output = []
    previous = None
    for raw in observations:
        row = deepcopy({key: value for key, value in raw.items() if key != 'popup'})
        row['audio'] = audio_view(raw)
        if (previous is not None and previous.get('popup') and output
                and all(previous[key] == raw[key] for key in ('chapter_id', 'page_id', 'visual'))
                and row['text'].startswith(output[-1]['text'])):
            earlier = output.pop()
            row['rule_updates'] = earlier['rule_updates'] + row['rule_updates']
            row['new_achievements'] = earlier['new_achievements'] + row['new_achievements']
            row['audio']['voices'] = earlier['audio']['voices'] + row['audio']['voices']
            row['audio']['sounds'] = earlier['audio']['sounds'] + row['audio']['sounds']
        output.append(row)
        previous = raw
    return output


def present_inventory(story, inventory):
    """Item pictures are usable file references, independent of the caller's cwd."""
    return [item | {'icon': str(story.asset(item['icon'])) if item['icon'] else None} for item in inventory]
