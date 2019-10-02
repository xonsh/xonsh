FROM mcr.microsoft.com/windows/servercore:1809 AS builder

RUN powershell -Command \
    $ProgressPreference = 'SilentlyContinue' ; \
    Write-Output 'Downloading msys2' ; \
    curl.exe -o msys2.tar.xy http://repo.msys2.org/distrib/x86_64/msys2-base-x86_64-20181211.tar.xz ; \
    Install-Package -Scope CurrentUser -Force 7Zip4Powershell ; \
    Write-Output 'Extracting tar.xz' ; \
    Expand-7zip msys2.tar.xy . ; \
    Write-Output 'Extracting tar' ; \
    Expand-7zip msys2.tar C:/ ; \
    Write-Output 'Done'

FROM mcr.microsoft.com/windows/nanoserver:1809
COPY --from=builder C:/Windows/system32/netapi32.dll C:/Windows/system32/netapi32.dll
COPY --from=builder C:/msys64 C:/msys64
