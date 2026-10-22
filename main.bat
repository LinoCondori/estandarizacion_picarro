@echo off
REM Activar el entorno virtual y ejecutar el script

call .venv\Scripts\activate.bat
python "main.py"
deactivate
pause