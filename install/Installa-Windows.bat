@echo off
REM DR-FilmCredits - installazione con doppio clic (Windows)
cd /d "%~dp0\.."
where py >nul 2>nul && (py -3 install\install.py) || (python install\install.py)
echo.
echo Fatto. Riavvia DaVinci Resolve: Workspace ^> Scripts ^> Utility ^> DR-FilmCredits
pause
