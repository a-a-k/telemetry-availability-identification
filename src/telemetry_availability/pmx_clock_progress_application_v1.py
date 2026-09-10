"""Explicit SHA-pinned launcher for the independently qualified PMX clock guard.

The frozen application launcher body is preserved except the explicit qualified
binary hash; command, startup, resource recording and1800second bound match v2.
"""
from datetime import datetime, timezone
import shutil
import subprocess
import time
from .pmx_composition_control import _hash, _write, _remote


def run_application_pmx(jar, root, out, *, expected_jar_sha256, limit=1800):
    _remote()
    if _hash(jar) != expected_jar_sha256:
        raise ValueError('qualified clock-progress PMX binary differs')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'results').mkdir()
    shutil.copyfile(root / 'Options.txt', out / 'Options.txt')
    shutil.copytree(root / 'traces', out / 'traces')
    commands = 'main:main -of Options.txt\nexit 0\n'
    (out / 'stdin.txt').write_text(commands)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    with (out / 'stdout.log').open('wb') as stream:
        process = subprocess.Popen(['/usr/bin/time', '-v', '-o', 'resource-usage.txt', 'timeout',
            '--signal=TERM', '--kill-after=10s', str(limit)+'s', 'java',
            '-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector',
            '-jar', str(jar.resolve())], cwd=out, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT)
        time.sleep(20)
        process.communicate(commands.encode(), timeout=limit+30)
    result = {'elapsed_seconds': time.perf_counter()-started, 'started_at': started_at,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': process.returncode,
        'startup_seconds': 20, 'internal_watchdog_seconds': limit, 'jar_sha256': expected_jar_sha256}
    _write(out / 'execution.json', result)
    return result
