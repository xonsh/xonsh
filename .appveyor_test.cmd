@ECHO OFF

IF "%XONSH_TEST_ENV%" == "MSYS2" (
    echo "MSYS2 Environment"
    REM We monkey path `py._path.local.PosixPath` here such that it does not
    REM allow to create symlinks which are not supported by MSYS2 anyway. As a
    REM result the other pytest code uses a workaround.
    call %MSYS2_PATH%\usr\bin\bash.exe -c "/usr/bin/python -u -c 'import py._path.local; del py._path.local.PosixPath.mksymlinkto; import pytest; raise SystemExit(pytest.main())'" || EXIT 1
) ELSE (
    echo "Windows Environment"
    call %PYTHON%\Scripts\py.test || EXIT 1
)
