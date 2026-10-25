@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    if errorlevel 1 goto erro
)
.venv\Scripts\python.exe -m pip install -r bibliotecapi\requirements.txt
if errorlevel 1 goto erro
.venv\Scripts\python.exe bibliotecapi\manage.py migrate --noinput
if errorlevel 1 goto erro
.venv\Scripts\python.exe bibliotecapi\manage.py preparar_biblioteca --se-vazio
if errorlevel 1 goto erro
echo Abra http://127.0.0.1:8000 no navegador. Para encerrar, pressione Ctrl+C.
.venv\Scripts\python.exe bibliotecapi\manage.py runserver 127.0.0.1:8000 --noreload
goto fim
:erro
echo Nao foi possivel iniciar. Confira o Python 3.12 ou superior e a conexao na primeira instalacao.
pause
:fim
endlocal
