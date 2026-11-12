"""Compare successful per-stage profiling variants; never assume a missing build passed."""
from pathlib import Path
import json

BUILD = Path(__file__).resolve().parent / 'build'
MODES = ('baseline','chunk32','chunk64','chunk128','loop','intrinsic','all','direct')
reports = {}
for mode in MODES:
    file = BUILD / ('compile-profile-' + mode + '.json')
    if file.is_file():
        reports[mode] = json.loads(file.read_text())
lines = ['# Py86 .PY startup compilation experiment', '',
         'All passing variants executed unchanged Python source and the full DOSBox regression suite.',
         'Baseline retains production lexer, memory allocation and compiler switches.',
         'Times are measured by the native DOS 8086 executable, not a host Python profiler.',
         'BIOS timer precision is about 55ms; emulator speed is not physical V20 performance.',
         '',
         '| Mode | Read ms | Lexer ms | Parse ms | Compile ms | Total startup ms | Relative throughput | Free GC |',
         '|---|---:|---:|---:|---:|---:|---:|---:|']
baseline = reports.get('baseline', {}).get('demo_median', {}).get('startup_total_ms')
for mode in MODES:
    if mode not in reports:
        lines.append('| %s | NOT VERIFIED | - | - | - | - | - | - |' % mode)
        continue
    vals = reports[mode]['demo_median']
    pct = (baseline / vals['startup_total_ms'] - 1) * 100 if baseline else 0
    lines.append('| %s | %.0f | %.0f | %.0f | %.0f | %.0f | %+.1f%% | %.0f |' % (
        mode, vals['read_ms'], vals['lexer_ms'], vals['parse_ms'], vals['compile_ms'],
        vals['startup_total_ms'], pct, vals['gc_free']))
failures = BUILD / 'compile-lab' / 'failures.txt'
if failures.is_file():
    lines.extend(('', '## Rejected builds or tests', '', failures.read_text()))
lines.extend(('', 'Production PY86.EXE and existing .PY sources are not changed by these experiments.',
              'Recheck gains on the physical NEC V20 before adopting a candidate.', ''))
out = BUILD / 'compile-lab' / 'summary.md'
out.parent.mkdir(exist_ok=True)
out.write_text('\n'.join(lines))
print('\n'.join(lines))
