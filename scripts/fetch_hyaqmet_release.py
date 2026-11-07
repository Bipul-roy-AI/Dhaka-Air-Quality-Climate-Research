"""Fetch the exact inspected HyAQMet Zenodo release; keep source bytes immutable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
from urllib.request import Request,urlopen
from zipfile import ZipFile

URL='https://zenodo.org/api/records/20705735/files/HyAQMet.zip/content'
MD5='449a8f7a530161f9aee2dd5f135f8ea4'
SHA256='60749b0e3815ca09009ce69d5b626070194a54a7d5437409d9e5f0720a254e35'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('artifacts/hyaqmet_release_new'));args=p.parse_args()
    if args.output.exists():p.error('Choose a new output directory')
    trust=os.environ.get('REQUESTS_CA_BUNDLE') or os.environ.get('SSL_CERT_FILE');context=ssl.create_default_context(cafile=trust or None)
    with urlopen(Request(URL,headers={'User-Agent':'Dhaka-study-reproduction/0.1'}),timeout=60,context=context) as response:
        data=response.read(40*1024*1024+1)
    if len(data)>40*1024*1024:raise ValueError('Release exceeded the inspected download limit')
    if hashlib.sha256(data).hexdigest()!=SHA256 or hashlib.md5(data).hexdigest()!=MD5:raise ValueError('Release checksum changed; inspect before using')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.hyaqmet-',dir=args.output.parent) as staging:
        out=Path(staging);archive=out/'HyAQMet.zip';archive.write_bytes(data)
        with ZipFile(archive) as z:
            for name in ['HyAQMet/HyAQMet.csv','HyAQMet/HyAQMet_README.md']:
                if z.getinfo(name).file_size>30*1024*1024:raise ValueError('Unexpected release member size')
                (out/Path(name).name).write_bytes(z.read(name))
        manifest={'doi':'10.5281/zenodo.20705735','source_url':URL,'licence':'CC BY4.0','zip_md5':MD5,'zip_sha256':SHA256,'csv_sha256':hashlib.sha256((out/'HyAQMet.csv').read_bytes()).hexdigest(),'authors':'Barua, A.; Basak Shuvo, M. and associated HyAQMet contributors; cite accompanying paper10.1002/gdj3.70111','purpose':'Exact inspected final release for reproduction; not independently calibrated station data'}
        (out/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');out.rename(args.output)
    print(args.output)

if __name__=='__main__':main()
