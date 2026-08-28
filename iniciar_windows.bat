@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set PYTHON=py
) else (
  set PYTHON=python
)

if not exist .venv (
  echo Criando ambiente virtual...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :erro
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :erro

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo Arquivo .env criado. O programa iniciara em modo demonstracao.
  echo Para conectar os QuickBooks reais, preencha as credenciais nesse arquivo.
  echo.
)

python app.py
exit /b 0

:erro
echo.
echo Ocorreu um erro durante a instalacao ou inicializacao.
pause
exit /b 1
