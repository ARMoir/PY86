@echo off
tandypy SMOKE.PY > SMOKE.OUT
if errorlevel 1 goto fail
tandypy METHOD.PY > METHOD.OUT
if errorlevel 1 goto fail
tandypy CORE.PY > CORE.OUT
if errorlevel 1 goto fail
tandypy GC.PY > GC.OUT
if errorlevel 1 goto fail
tandypy INPUT.PY < INPUT.IN > INPUT.OUT
if errorlevel 1 goto fail
tandypy < REPL.IN > REPL.OUT
if errorlevel 1 goto fail
tandypy ERROR.PY > ERROR.OUT
if not errorlevel 1 goto fail
echo PASS > RESULT.TXT
goto end
:fail
echo FAIL > RESULT.TXT
:end
