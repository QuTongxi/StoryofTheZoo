"""Export observations for AI without creating a window, fonts, or mixer."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from core.story import StoryError

WIDTH, HEIGHT = 1280, 800


def atomic_image(surface, target, pygame):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.image-', suffix='.png', dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        pygame.image.save(surface, str(temporary))
        os.replace(temporary, target)
    except (pygame.error, OSError) as exc:
        raise StoryError(f'无法写入场景图片 {target}：{exc}') from exc
    finally:
        temporary.unlink(missing_ok=True)


class SceneExporter:
    def __init__(self, story, directory):
        self.story = story
        self.directory = Path(directory).resolve()
        os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
        import pygame  # Image/Surface only; no pygame.init(), set_mode(), or font calls.
        self.pygame = pygame
        self.cache = {}

    def scaled(self, asset, box, cover=False):
        key = (asset, box, cover)
        if key not in self.cache:
            try:
                image = self.pygame.image.load(str(self.story.asset(asset)))
                ratios = box[0] / image.get_width(), box[1] / image.get_height()
                ratio = max(ratios) if cover else min(ratios)
                size = tuple(max(1, round(n * ratio)) for n in image.get_size())
                self.cache[key] = self.pygame.transform.smoothscale(image, size)
            except (self.pygame.error, OSError) as exc:
                raise StoryError(f'无法导出图片 {asset}：{exc}') from exc
        return self.cache[key]

    def surfaces(self, visual):
        background = self.pygame.Surface((WIDTH, HEIGHT))
        background.fill((25, 45, 40))
        if visual['background']:
            image = self.scaled(visual['background'], (WIDTH, HEIGHT), cover=True)
            background.blit(image, ((WIDTH - image.get_width()) // 2, (HEIGHT - image.get_height()) // 2))
        scene = background.copy()
        for slot, asset in visual['characters'].items():
            image = self.scaled(asset, (500, 760))
            center = {'left': 270, 'center': 640, 'right': 1010}[slot]
            scene.blit(image, (center - image.get_width() // 2, 840 - image.get_height()))
        return background, scene

    def export(self, segment):
        output = []
        last = None
        for item in segment:
            visual = item['visual']
            # Include source bytes in the key: changing an image invalidates cached observations.
            digest = hashlib.sha256(json.dumps(visual, sort_keys=True).encode())
            for asset in [visual['background'], *visual['characters'].values()]:
                if asset:
                    digest.update(self.story.asset(asset).read_bytes())
            key = digest.hexdigest()[:24]
            directory = self.directory / 'scenes'
            bg_path = directory / f'{key}-background.png'
            scene_path = directory / f'{key}-scene.png'
            background, scene = self.surfaces(visual)
            if not bg_path.exists():
                atomic_image(background, bg_path, self.pygame)
            if not scene_path.exists():
                atomic_image(scene, scene_path, self.pygame)
            audio = item.get('audio', {'music': None, 'voices': [], 'sounds': []})
            output.append({k: v for k, v in item.items() if k not in ('visual', 'audio', 'popup')} | {
                'audio': {'music': str(self.story.asset(audio['music'])) if audio['music'] else None,
                          'voices': [str(self.story.asset(path)) for path in audio['voices']],
                          'sounds': [str(self.story.asset(path)) for path in audio['sounds']]},
                'background_image': str(bg_path), 'scene_image': str(scene_path),
                'has_background': visual['background'] is not None,
            })
            last = background, scene
        if last is None:
            raise StoryError('当前剧情段为空，无法导出场景')
        atomic_image(last[0], self.directory / 'background.png', self.pygame)
        atomic_image(last[1], self.directory / 'scene.png', self.pygame)
        return output
