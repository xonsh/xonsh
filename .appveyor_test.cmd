@ECHO OFF

IF "%XONSH_TEST_ENV%" == "MSYS2" (
    echo "MSYS2 Environment"
    call %MSYS2_PATH%\usr\bin\bash.exe -c "/usr/bin/py.test" || EXIT 1
) ELSE (
    echo "Windows Environment"
    call %PYTHON%\Scripts\py.test || EXIT 1
)
