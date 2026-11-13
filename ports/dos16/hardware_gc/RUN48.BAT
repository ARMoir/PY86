@echo off
rem PY86 Tandy hardware GC comparison. DOS 6.22, 8086/V20.
rem A86 = production GC, D86 = data-aware GC.
rem DO NOT add unqualified incremental binaries to this comparison.
set PY86_HEAP=48000
set PY86_HEAP_MAX=
if not exist A86.EXE goto missing
if not exist D86.EXE goto missing
if not exist GCINCR.PY goto missing
if not exist GCBENCH.PY goto missing
if not exist BENCH1.PY goto missing
if not exist SNAKE.PY goto missing
if exist RESULT.TXT del RESULT.TXT
echo Py86 V20 GC hardware comparison
echo Heap 48000 bytes, alternating A/D order.
A86 -V > AVER.TXT
if errorlevel 1 goto fail
D86 -V > DVER.TXT
if errorlevel 1 goto fail
A86 --heap-info > AHEAP.TXT
if errorlevel 1 goto fail
D86 --heap-info > DHEAP.TXT
if errorlevel 1 goto fail
echo Checking reference mutations...
A86 GCINCR.PY > ACHK.TXT
if errorlevel 1 goto fail
D86 GCINCR.PY > DCHK.TXT
if errorlevel 1 goto fail
echo Running GC trials A,D,D,A...
A86 GCBENCH.PY > A1.TXT
if errorlevel 1 goto fail
D86 GCBENCH.PY > D1.TXT
if errorlevel 1 goto fail
D86 GCBENCH.PY > D2.TXT
if errorlevel 1 goto fail
A86 GCBENCH.PY > A2.TXT
if errorlevel 1 goto fail
echo Measuring ordinary interpreter speed...
A86 BENCH1.PY > ACPU.TXT
if errorlevel 1 goto fail
D86 BENCH1.PY > DCPU.TXT
if errorlevel 1 goto fail
echo Checking Snake rules...
A86 SNAKE.PY --selftest > ASNK.TXT
if errorlevel 1 goto fail
D86 SNAKE.PY --selftest > DSNK.TXT
if errorlevel 1 goto fail
echo PASS > RESULT.TXT
echo PASSED. Check RESULT.TXT, A1/A2, D1/D2 and CPU logs.
echo Run A86 SNAKE.PY or D86 SNAKE.PY to compare gameplay.
goto end
:missing
echo ERROR: Missing test-kit file.
echo MISSING > RESULT.TXT
goto end
:fail
echo ERROR: One command failed. Inspect the newest log.
echo FAIL > RESULT.TXT
:end
set PY86_HEAP=
set PY86_HEAP_MAX=
