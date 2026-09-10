"""Explicit derived-JAR launcher for remote diagnostics; no admission authority."""
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import time

from diagnose_v3_pmx_timeout_v1 import write


def run_derived_pmx(jar, root, out, *, expected_jar_sha256, limit=120):
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    assert limit == 120
    if sha256(jar.read_bytes()).hexdigest() != expected_jar_sha256:
        raise ValueError('derived diagnostic JAR differs from generated provenance')
    out.mkdir(parents=True, exist_ok=False)
    (out/'results').mkdir()
    shutil.copyfile(root/'Options.txt', out/'Options.txt')
    shutil.copytree(root/'traces', out/'traces')
    commands='main:main -of Options.txt\nexit 0\n'
    (out/'stdin.txt').write_bytes(commands.encode())
    started=time.perf_counter(); started_at=datetime.now(timezone.utc).isoformat()
    with (out/'stdout.log').open('wb') as stream:
        process=subprocess.Popen(['/usr/bin/time','-v','-o','resource-usage.txt','timeout',
            '--signal=TERM','--kill-after=10s',str(limit)+'s','java',
            '-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector',
            '-jar',str(jar.resolve())],cwd=out,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT)
        time.sleep(20)
        try:
            process.communicate(commands.encode(),timeout=limit+30)
        finally:
            if process.poll() is None:
                process.kill();process.wait(timeout=15)
    result=dict(elapsed_seconds=time.perf_counter()-started,started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),exit_code=process.returncode,
        startup_seconds=20,internal_watchdog_seconds=limit,jar_sha256=expected_jar_sha256,
        derived_diagnostic_jar=True,qualification_or_independent_result=False)
    write(out/'execution.json',result)
    return result
