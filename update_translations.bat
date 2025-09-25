@echo off
set VENV_PATH=%~dp0.venv
set LUPDATE=%VENV_PATH%\Scripts\pyside6-lupdate.exe
set LINGUIST=%VENV_PATH%\Scripts\pyside6-linguist.exe
set LRELEASE=%VENV_PATH%\Scripts\pyside6-lrelease.exe
set SOURCES=%~dp0main.py %~dp0app\__init__.py %~dp0app\player.py %~dp0app\tagging.py %~dp0app\ui.py %~dp0app\utils.py %~dp0app\worker.py %~dp0app\youtube_api.py
set TS_KO=%~dp0translations/ko_KR.ts
set QM_KO=%~dp0translations/ko_KR.qm

echo Updating translations...

echo Running lupdate...
"%LUPDATE%" %SOURCES% -ts %TS_KO%
IF %ERRORLEVEL% NEQ 0 (
    echo lupdate failed.
    exit /b %ERRORLEVEL%
)

echo.
echo Launching linguist...
"%LINGUIST%" %TS_KO%
IF %ERRORLEVEL% NEQ 0 (
    echo linguist failed.
    exit /b %ERRORLEVEL%
)

echo.
echo Running lrelease...
"%LRELEASE%" %TS_KO% -qm %QM_KO%
IF %ERRORLEVEL% NEQ 0 (
    echo lrelease failed.
    exit /b %ERRORLEVEL%
)

echo.
echo Translations updated successfully.