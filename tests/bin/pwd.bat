@echo on
call :s_which py.exe
rem note that %~dp0 is dir of this batch script
if not "%_path%" == "" (
  py -3 %~dp0pwd %*
) else (
  python %~dp0pwd %*
)

goto :eof

:s_which
  setlocal
  endlocal & set _path=%~$PATH:1
  goto :eof