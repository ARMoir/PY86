"""Compare isolated parser/compiler/GC variants; only verified DOS runs count."""
from pathlib import Path
import json
import statistics

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'
LAB = BUILD / 'runtime-lab'
LAB.mkdir(exist_ok=True)
MODES = ('base', 'all', 'p1k', 'p1ka')
rows = {}
for mode in MODES:
    for gc in ('off','on'):
        file = BUILD / ('compile-profile-runtime-' + mode + '-' + gc + '.json')
        if file.exists():
            item = json.loads(file.read_text())
            assert item['mode'] == 'runtime-' + mode + '-' + gc
            assert item['preexec_gc'] == (gc == 'on')
            rows[(mode,gc)] = item

lines = [
    '# Py86 isolated parser allocation, compiler settings and GC study',
    '',
    'Each verified native 8086 executable passed the complete DOSBox suite.',
    'Separate OFF and ON runs also compiled unchanged DEMO.PY and',
    'PARSST.PY, plus VM-only RUNTST.PY; no bytecode caches.',
    'BIOS timing granularity ~55ms; these are emulator results, not V20.',
    '',
    '| Variant | Pre-GC | Startup ms | DEMO exec ms | VM stress exec ms | GC calls in demo | GC ms | Prep ms | Pre/post free |',
    '|---|---|---:|---:|---:|---:|---:|---:|---:|',
]
for mode in MODES:
    for gc in ('off','on'):
        x=rows.get((mode,gc))
        if x is None:
            lines.append('| %s | %s | NOT VERIFIED | - | - | - | - | - | - |' % (mode, gc))
            continue
        demo=x['demo_median']
        detailed=x['samples']['PDEM1.OUT']['runtime']
        execs=[x['samples'][z]['exec_ms'] for z in ('PDEM1.OUT','PDEM2.OUT')]
        vm=x['samples']['RUNTST.OUT']
        lines.append('| %s | %s | %.0f | %.0f | %d | %d | %d | %d | %d / %d |' % (
            mode, gc, demo['startup_total_ms'], statistics.median(execs), vm['exec_ms'],
            detailed['gc_calls'], detailed['gc_ms'], detailed['prep_ms'],
            detailed['free_pre'], detailed['free_post']))
failure=LAB/'failures.txt'
if failure.is_file():
    lines.extend(('', '## Failed variants', failure.read_text()))
lines.extend(('', 'Profiler instrumentation may add overhead relative to the',
              'previous baseline. Compare builds within this new matrix only.',
              'Do not promote a candidate until physical V20 tests confirm it.', ''))
summary='\n'.join(lines)
(LAB/'summary.md').write_text(summary)
print(summary)
