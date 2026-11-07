"""Download an explicitly public example NAV file, with a pinned content checksum."""
from pathlib import Path
import hashlib
import json
import urllib.request

URL='https://raw.githubusercontent.com/osqzss/gps-sdr-sim/master/brdc0010.22n'
EXPECTED='7db04513dd2d0e13c0ee20cb4eaa8f71e5a28ab58b65c9b5b789f86eeab436cd'

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    target=root/'data/raw/brdc0010.22n'
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest()!=EXPECTED:
            raise SystemExit('Existing input differs from pinned checksum; preserving file without changes.')
        print(f'Already verified: {target}')
    else:
        raw=urllib.request.urlopen(URL,timeout=60).read()
        actual=hashlib.sha256(raw).hexdigest()
        if actual!=EXPECTED: raise SystemExit(f'Checksum mismatch {actual}; download not saved')
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f: f.write(raw)
        print(f'Saved {len(raw)} bytes to {target}')
    meta=target.with_suffix(target.suffix+'.source.json')
    if not meta.exists():
        with meta.open('x',encoding='utf-8') as f:
            json.dump({'url':URL,'sha256':EXPECTED,'description':'GPS RINEX2 broadcast ephemeris, 2022-01-01, public gps-sdr-sim example; not indoor observations.'},f,indent=2)
