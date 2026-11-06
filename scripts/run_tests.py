"""Run tests with isolated workspace temp files and preserve exact output."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import uuid

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    temporary = root / 'artifacts' / 'test-runs' / uuid.uuid4().hex
    temporary.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, RUN_INTEGRATION='1' if args.integration else '0')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-s', '-p', 'no:cacheprovider', '--basetemp', str(temporary)],
                            cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = root / 'docs/evidence/tests.txt'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.stdout, encoding='utf-8')
    print(result.stdout)
    raise SystemExit(result.returncode)

if __name__ == '__main__':
    main()
