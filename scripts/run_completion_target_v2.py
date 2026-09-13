"""Technical path adaptation; unchanged v1 experiment and target algorithms."""
from pathlib import Path
import run_completion_target_v1 as fixed


def main():
    original_read = fixed.read
    fixed.read = lambda path: original_read(Path(path))
    fixed.CONFIG = Path('configs/v5_completion_target_v2.json')
    fixed.main()


if __name__ == '__main__': main()
