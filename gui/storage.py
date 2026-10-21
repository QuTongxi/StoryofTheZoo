"""Atomic, versioned local JSON saves."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from core.engine import Engine
from core.story import StoryError


class SaveStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def path(self, slot: int) -> Path:
        if type(slot) is not int or not 1 <= slot <= 3:
            raise StoryError("存档槽必须是 1、2 或 3")
        return self.directory / f"slot-{slot}.json"

    def save(self, engine: Engine, slot=1):
        target = self.path(slot)
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.directory,
                                             prefix=".save-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(engine.export(), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            raise StoryError(f"保存失败：{exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return target

    def load(self, engine: Engine, slot=1):
        path = self.path(slot)
        try:
            if path.stat().st_size > 16 * 1024 * 1024:
                raise StoryError("存档过大，无法读取")
            payload = json.loads(path.read_text(encoding="utf-8"))
            engine.restore(payload)
        except (OSError, ValueError, RecursionError) as exc:
            raise StoryError(f"读取存档失败：{exc}") from exc

    def description(self, slot):
        path = self.path(slot)
        if not path.exists():
            return "空存档"
        try:
            if path.stat().st_size > 16 * 1024 * 1024:
                return "存档过大"
            payload = json.loads(path.read_text(encoding="utf-8"))
            return f"{payload['state']['chapter_id']} · {payload['state']['page_id']}"
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            return "存档损坏"
