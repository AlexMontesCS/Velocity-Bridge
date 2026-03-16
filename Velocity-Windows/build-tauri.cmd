@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 exit /b %errorlevel%
set "PATH=C:\Users\Arsh\.cargo\bin;%PATH%"
"C:\Program Files\nodejs\node.exe" "C:\Velocity-Windows\node_modules\@tauri-apps\cli\tauri.js" build --runner "C:\Users\Arsh\.cargo\bin\cargo.exe" --no-sign -v
