@echo off
REM Shared MSVC + Windows SDK setup for Rust/Tauri on this machine.
REM Windows SDK is installed on D:\Windows Kits (not the default C: location).

set PF86=%ProgramFiles(x86)%
set PF64=%ProgramFiles%

set VCVARS=%PF86%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VCVARS%" set VCVARS=%PF64%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VCVARS%" set VCVARS=%PF64%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat
if exist "%VCVARS%" call "%VCVARS%" >nul 2>nul

set VS_ROOT=%PF86%\Microsoft Visual Studio\2022\BuildTools
if not exist "%VS_ROOT%" set VS_ROOT=%PF64%\Microsoft Visual Studio\2022\Community
if not exist "%VS_ROOT%" set VS_ROOT=%PF64%\Microsoft Visual Studio\2022\Professional

set MSVC_VER=
for /f "delims=" %%i in ('dir /b /ad /o-n "%VS_ROOT%\VC\Tools\MSVC" 2^>nul') do set MSVC_VER=%%i& goto msvc_found
:msvc_found
if not defined MSVC_VER goto msvc_missing

set MSVC_ROOT=%VS_ROOT%\VC\Tools\MSVC\%MSVC_VER%

set SDK_VER=
set SDK_ROOT=D:\Windows Kits\10
if exist "%SDK_ROOT%\Lib" for /f "delims=" %%v in ('dir /b /ad /o-n "%SDK_ROOT%\Lib" 2^>nul') do set SDK_VER=%%v& goto sdk_found
set SDK_ROOT=%PF86%\Windows Kits\10
if exist "%SDK_ROOT%\Lib" for /f "delims=" %%v in ('dir /b /ad /o-n "%SDK_ROOT%\Lib" 2^>nul') do set SDK_VER=%%v& goto sdk_found
:sdk_found
if not defined SDK_VER goto sdk_missing

if not exist "%SDK_ROOT%\Lib\%SDK_VER%\um\x64" goto sdk_missing

set LIB=%MSVC_ROOT%\lib\x64;%SDK_ROOT%\Lib\%SDK_VER%\um\x64;%SDK_ROOT%\Lib\%SDK_VER%\ucrt\x64
set INCLUDE=%MSVC_ROOT%\include;%SDK_ROOT%\Include\%SDK_VER%\ucrt;%SDK_ROOT%\Include\%SDK_VER%\um;%SDK_ROOT%\Include\%SDK_VER%\shared
exit /b 0

:msvc_missing
echo [WARN] MSVC toolchain folder not found under %VS_ROOT%
exit /b 1

:sdk_missing
echo [WARN] Windows SDK libraries not found under %SDK_ROOT%
exit /b 1
