"""Run all endings through the real CLI in isolated disposable sessions.

Run tools/check_routes.py first to regenerate the explicit operation lists.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    operations = sorted((ROOT / 'runtime/verification').glob('*-operations.json'))
    if len(operations) != 23:
        raise SystemExit('请先运行 tools/check_routes.py 生成 23 条路线。')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='zoo-cli-') as directory:
        def check(path):
            ending = path.stem.split('-')[0]
            session = Path(directory) / ending
            result = subprocess.run([
                sys.executable, str(ROOT / 'game.py'), '--cli', '--session-dir', str(session),
                '--batch', str(path),
            ], capture_output=True, text=True, cwd=ROOT)
            if result.returncode:
                raise AssertionError((ending, result.stderr, result.stdout[:1000]))
            payload = json.loads(result.stdout)
            assert payload['ok'], (ending, payload)
            saved = json.loads((session / 'session.json').read_text())
            state = saved['current']['state']
            assert state['ended'] and state['chapter_id'] == ending, (ending, state['chapter_id'])
            assert (session / 'view/playback.json').is_file()
            print(f'{ending}: CLI OK ({payload["batch_steps"]} actions)', flush=True)
            return {'ending': ending, 'steps': payload['batch_steps']}

        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(pool.map(check, operations))
    report = {'routes': records, 'seconds': round(time.monotonic()-started, 2)}
    (ROOT / 'runtime/verification/cli-report.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
