"""Fetch bounded public source candidates, preserving TLS and original exports.

Usage: python scripts/fetch_public_sources.py --output artifacts/public_sources
No API keys are required. Existing directories must be empty. Files are source
candidates, not an automatic measurement-validation certificate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

POWER_EMBASSY_PARAMS = {'parameters':'T2M,T2MDEW,RH2M,WS10M,PRECTOTCORR,PS','community':'AG','longitude':90.424614,'latitude':23.796374,'start':'20160101','end':'20211231','format':'JSON','time-standard':'UTC'}
POWER_UNITS = {'T2M':'C','T2MDEW':'C','RH2M':'%','WS10M':'m/s','PRECTOTCORR':'mm/day','PS':'kPa'}
MAX_BYTES = 5 * 1024 * 1024


def download(url):
    # Respect the cloud's inherited proxy and CA trust; never disable verification.
    trust = os.environ.get('REQUESTS_CA_BUNDLE') or os.environ.get('SSL_CERT_FILE')
    context = ssl.create_default_context(cafile=trust if trust else None)
    request = Request(url, headers={'User-Agent':'Dhaka-source-audit/0.1'})
    with urlopen(request,timeout=30,context=context) as response:
        payload = response.read(MAX_BYTES+1)
        if len(payload)>MAX_BYTES:raise ValueError('Public source exceeds the bounded download limit')
        return payload,response.geturl()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('artifacts/public_sources'))
    args=parser.parse_args()
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error('Choose a new/empty output directory; existing files are preserved')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    urls=[
        ('Figure_1_data.xlsx','https://pasteur.epa.gov/uploads/10.23719/1528454/Figure_1_data.xlsx','87f2d78c8722c86ec000098819aa90fe19eb75902180a5b2667ea0f5dda0a5db'),
        ('figshare_airnow_12cities.zip','https://ndownloader.figshare.com/files/24024083',None),
        ('nasa_power_embassy_2016_2021.json','https://power.larc.nasa.gov/api/temporal/daily/point?'+urlencode(POWER_EMBASSY_PARAMS),None),
    ]
    log=[]
    with tempfile.TemporaryDirectory(prefix='.public-sources-',dir=args.output.parent) as staging:
        out=Path(staging)
        for name,url,expected in urls:
            payload,final_url=download(url);digest=hashlib.sha256(payload).hexdigest()
            if expected and digest!=expected:raise ValueError(f'Snapshot checksum changed for {name}; inspect before use')
            if name.endswith('.xlsx') and payload[:2]!=b'PK':raise ValueError('Expected XLSX archive')
            if name.startswith('figshare') and hashlib.md5(payload).hexdigest()!='83e5b536ebf0e0e09bb65c9c8f44eff1':
                raise ValueError('Figshare publisher checksum mismatch')
            if name.startswith('nasa'):
                data=json.loads(payload)
                if data['header']['time_standard']!='UTC':raise ValueError('NASA response did not confirm UTC')
                if set(data['properties']['parameter'])!=set(POWER_EMBASSY_PARAMS['parameters'].split(',')):
                    raise ValueError('Unexpected NASA parameter set')
                for field,unit in POWER_UNITS.items():
                    if data['parameters'][field]['units']!=unit:raise ValueError(f'Unexpected NASA units for {field}')
            (out/name).write_bytes(payload)
            log.append({'filename':name,'request_url':url,'resolved_url':final_url,'bytes':len(payload),'sha256':digest})
        (out/'download_manifest.json').write_text(json.dumps(log,indent=2)+'\n')
        if args.output.exists():args.output.rmdir()
        out.rename(args.output)
    print(f'Downloaded {len(log)} source candidates to {args.output}; no original study data replaced.')

if __name__=='__main__':main()
