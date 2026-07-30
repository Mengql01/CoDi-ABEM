@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python "%~dp0idf_toolkit.py" %*
endlocal
