@echo off
call :s_which py.exe
if not "%_path%" == "" (
  py -3 -m xonsh.xoreutils.cat %*
) else (
  python -m xonsh.xoreutils.cat %*
)

goto :eof

:s_which
  setlocal
  endlocal & set _path=%~$PATH:1
  goto :eof
