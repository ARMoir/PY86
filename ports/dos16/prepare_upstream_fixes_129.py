"""Three upstream correctness backports and JSON serialization optimization, without upgrading the pinned core.

MicroPython upstream commits (MIT license, retained in the source checkout):
1aad4cd7011e64fa4a069935c52a80191bafac83 - eval trailing continuation
cc1d531fb81e20df125959c3a2ba420a6c7b4a39 - bytearray int subclass
3351126249e83e90b21b301dd1abcc6afd511273 - bytes str subclass
8901bf220e0cebd6cda9494b1dc328e79c5c1cec - JSON string run printing
The C/grammar hunks are unchanged from these commits; DOS tests assert results.
"""
import argparse
import json
from pathlib import Path
import subprocess

SHA = '0fd6c573ea815774668bbb16b8e197c8822368b2'
COMMITS = ['1aad4cd7011e64fa4a069935c52a80191bafac83',
           'cc1d531fb81e20df125959c3a2ba420a6c7b4a39',
           '3351126249e83e90b21b301dd1abcc6afd511273',
           '8901bf220e0cebd6cda9494b1dc328e79c5c1cec']


def apply(source):
    source = source.resolve()
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != SHA:
        raise RuntimeError('Backports require pinned MicroPython 1.29.0: ' + SHA)
    patches = [str(Path(__file__).with_name(name).resolve()) for name in
               ('upstream-fixes-129.patch', 'upstream-json-129.patch')]
    command = ['git', '-C', str(source), 'apply', '--whitespace=nowarn']
    subprocess.run(command + ['--check'] + patches, check=True)
    subprocess.run(command + patches, check=True)
    (source / 'py86-upstream-fixes.json').write_text(json.dumps(
        {'core': SHA, 'upstream_commits': COMMITS}, indent=2) + '\n')
    print('Applied three upstream correctness backports and JSON printing optimization to pinned 1.29.0')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    apply(p.parse_args().source)
