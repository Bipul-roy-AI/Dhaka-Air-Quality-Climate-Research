"""Reproduce four separated analysis tracks; never overwrite original data/results."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['release','hyaqmet-source-dir','epa','weather','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--mirror',type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for key in ['release','epa','weather','mirror']:
        v=getattr(a,key)
        if v is not None:
            v=v.resolve()
            if not v.is_file():p.error(f'Missing input: {v}')
            setattr(a,key,v)
    a.hyaqmet_source_dir=a.hyaqmet_source_dir.resolve()
    if not a.hyaqmet_source_dir.is_dir():p.error('Missing GitHub native-source directory')
    a.output=a.output.resolve()
    if a.output.exists():p.error('Choose a new output directory')
    a.output.mkdir(parents=True)
    jobs=[('hyaqmet','analyze_hyaqmet.py',['--releaseCSV',str(a.release),'--source-dir',str(a.hyaqmet_source_dir)]),
          ('observed','analyze_observed_reference.py',['--input',str(a.epa),'--weather',str(a.weather)]),
          ('weather','analyze_observed_weather.py',['--epa',str(a.epa),'--weather',str(a.weather)]),
          ('reference','validate_hyaqmet_reference.py',['--release',str(a.release),'--epa',str(a.epa)]+(['--mirror',str(a.mirror)] if a.mirror else []))]
    records=[]
    for name,script,extra in jobs:
        args=[sys.executable,str(repo/'scripts'/script),*extra,'--output',str(a.output/name)]
        print('Running',name,flush=True)
        with (a.output/(name+'_run.log')).open('w') as log:
            subprocess.run(args,cwd=repo,stdout=log,stderr=subprocess.STDOUT,check=True)
        records.append({'track':name,'script':script,'script_sha256':hashlib.sha256((repo/'scripts'/script).read_bytes()).hexdigest(),'output':name,'status':'completed'})
    manifest={'status':'all_four_tracks_completed','analyses':records,'input_sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('release',a.release),('epa',a.epa),('weather',a.weather)]+([('mirror',a.mirror)] if a.mirror else [])},'input_files_modified':False,'all_results':'conditional/retrospective as detailed in per-track methods; not operational/causal certification'}
    (a.output/'RUN_COMPLETE.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(a.output,flush=True)

if __name__=='__main__':main()
