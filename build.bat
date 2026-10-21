@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_RUNTIME=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%PYTHON_RUNTIME%" (
  "%PYTHON_RUNTIME%" tools\build_recovered.py
) else (
  py -3.12 tools\build_recovered.py
)
if errorlevel 1 exit /b %errorlevel%
echo Build finished. Run luaVietsup-ModelFix4.exe.
