@ECHO OFF

IF "%XONSH_TEST_ENV%" == "MSYS2" (
    echo "MSYS2 Environment"
    %MSYS2_PATH%\usr\bin\pacman.exe -Syu --noconfirm
    %MSYS2_PATH%\usr\bin\pacman.exe -S --noconfirm python3 python3-pip
    %MSYS2_PATH%\usr\bin\bash.exe -c "/usr/bin/pip install -r requirements-tests.txt"
) ELSE (
    echo "Windows Environment"
    %PYTHON%\Scripts\pip install -r requirements-tests.txt
)
