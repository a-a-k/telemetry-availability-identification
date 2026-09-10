"""Read small GNU-time records; absent measurements stay unknown."""
from pathlib import Path


def summarize(root):
    records = []
    for path in sorted(Path(root).rglob('*resource-usage.txt')):
        values = dict(wall_seconds=None, user_seconds=None, system_seconds=None, maximum_rss_bytes=None)
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw.strip()
            if line.startswith('Elapsed (wall clock) time (h:mm:ss or m:ss):'):
                value = line.split('):', 1)[1].strip(); seconds = 0.0
                for part in value.split(':'):
                    seconds = 60*seconds+float(part)
                values['wall_seconds'] = seconds
            for label, field, multiplier in (
                    ('User time (seconds):', 'user_seconds', 1),
                    ('System time (seconds):', 'system_seconds', 1),
                    ('Maximum resident set size (kbytes):', 'maximum_rss_bytes', 1024)):
                if line.startswith(label):
                    values[field] = float(line[len(label):].strip())*multiplier
        records.append(dict(path=path.relative_to(root).as_posix(), **values))
    return dict(records=records, wall_intervals_can_overlap=True,
        rss_scope='per timed process/children GNU-time high-water report, not summed across concurrent processes',
        unknown_values_are_not_zero=True)
