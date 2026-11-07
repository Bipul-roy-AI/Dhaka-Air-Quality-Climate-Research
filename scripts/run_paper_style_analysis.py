"""Reproduce observed-PM and weather analyses with optional station-day checks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['epa', 'weather', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mirror', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    inputs = {}
    for name in ['epa', 'weather', 'mirror']:
        path = getattr(args, name)
        if path is not None:
            path = path.resolve()
            if not path.is_file():
                parser.error(f'Missing input: {path}')
            setattr(args, name, path)
            inputs[name] = path
    output = args.output.resolve()
    if output.exists():
        parser.error('Choose a new output directory')
    jobs = [
        ('observed', 'analyze_observed_reference.py',
         ['--input', str(args.epa), '--weather', str(args.weather)]),
        ('weather', 'analyze_observed_weather.py',
         ['--epa', str(args.epa), '--weather', str(args.weather)]),
    ]
    if args.mirror is not None:
        jobs.append(('station_day', 'inspect_station_day.py',
                     ['--epa', str(args.epa), '--mirror', str(args.mirror)]))
    for _, script, _ in jobs:
        if not (repo / 'scripts' / script).is_file():
            parser.error(f'Missing analysis script: {script}')
    input_hashes = {name: digest(path) for name, path in inputs.items()}
    output.mkdir(parents=True)
    records = []
    for name, script, extra in jobs:
        script_path = repo / 'scripts' / script
        command = [sys.executable, str(script_path), *extra, '--output', str(output / name)]
        print('Running', name, flush=True)
        with (output / (name + '_run.log')).open('w') as log:
            subprocess.run(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT, check=True)
        records.append({'track': name, 'script': script, 'script_sha256': digest(script_path),
                        'output': name, 'status': 'completed'})
    if input_hashes != {name: digest(path) for name, path in inputs.items()}:
        raise ValueError('An input changed during analysis; no completion manifest written')
    manifest = {
        'status': 'all_study_tracks_completed', 'analyses': records,
        'input_sha256': input_hashes, 'input_files_modified': False,
        'study_scope': 'Observed Embassy PM2.5 and NASA POWER weather; optional station-day interval sensitivity',
        'all_results': 'Conditional/retrospective as detailed per track; not operational or causal certification',
    }
    (output / 'RUN_COMPLETE.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(output, flush=True)


if __name__ == '__main__':
    main()
