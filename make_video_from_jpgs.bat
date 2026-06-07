@echo off
setlocal

rem Build a 30 fps video from all JPG files in this folder, sorted by filename.
rem Original JPG files are only read; they are not renamed or modified.

set "FPS=30"
set "FRAME_DURATION=0.0333333333333333"
set "OUTPUT=output_30fps.mp4"
set "CACHE_DIR=.ffmpeg_cache"
set "COUNT=0"
set "LAST_FILE="

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo Error: ffmpeg was not found in PATH.
    echo Install ffmpeg or add it to PATH, then run this script again.
    pause
    exit /b 1
)

pushd "%~dp0" >nul
if not exist "%CACHE_DIR%\" mkdir "%CACHE_DIR%"
set "LIST=%CACHE_DIR%\ffmpeg_jpg_list_%RANDOM%%RANDOM%.ffconcat"

> "%LIST%" echo ffconcat version 1.0

for /f "delims=" %%F in ('dir /b /a-d /on "*.jpg" 2^>nul') do (
    >> "%LIST%" echo file '../%%F'
    >> "%LIST%" echo duration %FRAME_DURATION%
    set /a COUNT+=1
    set "LAST_FILE=%%F"
)

if "%COUNT%"=="0" (
    del "%LIST%" >nul 2>nul
    popd >nul
    echo Error: no JPG files were found in this folder.
    pause
    exit /b 1
)

rem Repeat the last file so the concat demuxer keeps the final frame duration.
>> "%LIST%" echo file '../%LAST_FILE%'

echo Found %COUNT% JPG files.
echo Creating "%OUTPUT%" at %FPS% fps...

ffmpeg -y -f concat -safe 0 -i "%LIST%" -r %FPS% -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p "%OUTPUT%"
set "FFMPEG_EXIT=%ERRORLEVEL%"

del "%LIST%" >nul 2>nul
popd >nul

if not "%FFMPEG_EXIT%"=="0" (
    echo.
    echo Error: ffmpeg failed with exit code %FFMPEG_EXIT%.
    pause
    exit /b %FFMPEG_EXIT%
)

echo.
echo Done: "%~dp0%OUTPUT%"
pause
