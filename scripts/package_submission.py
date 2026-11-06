"""Create reviewable milestone ZIP exports with allowlisted small artifacts."""
import argparse
from pathlib import Path
import re
import subprocess
import zipfile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--team', default='TeamName')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.team):
        parser.error('team must contain only letters, digits, underscore or hyphen')
    root = Path(__file__).resolve().parent.parent
    output = root / 'submissions'
    output.mkdir(exist_ok=True)
    files = [root / name for name in ['README.md', 'requirements.txt', 'requirements-lock.txt', 'compose.yaml', 'pytest.ini', '.gitignore', 'data/source_manifest.json', 'data/training_sample.csv']]
    for directory in ['collector', 'processor', 'nfl', 'sql', 'tests', 'scripts', 'contracts', 'docs']:
        files.extend(p for p in (root / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.sql', '.md', '.txt', '.json', '.jsonl', '.csv', '.log'})
    # Small saved estimator included for reproducible evaluation/API demonstration.
    model = root / 'artifacts/model.joblib'
    if model.exists() and model.stat().st_size < 5_000_000:
        files.append(model)
        files.append(root / 'artifacts/evaluation.json')
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True).stdout.strip()
    for week in [6, 7, 8]:
        target = output / f'CYB3023_Week{week}_{args.team}.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(set(files)):
                if file.exists():
                    archive.write(file, file.relative_to(root))
            archive.writestr('SUBMISSION-STATUS.txt', f'Week {week} export of the integrated implementation.\nBase commit: {commit}\nChanges remain uncommitted; this is not a submitted commit identifier.\nTeamName, real repository URL, contribution statements and weekly AI interactions require personal completion.\nFull source CSV omitted; retrieve with collector before using cached-schedule commands.\nTechnical evidence is in docs/evidence.\n')
        print(target)

if __name__ == '__main__':
    main()
