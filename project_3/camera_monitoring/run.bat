@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM --- Detect if we're already inside a venv ---
if defined VIRTUAL_ENV (
  echo [info] Using already-activated venv: %VIRTUAL_ENV%
  goto RUN
)

REM --- Prefer your existing 'camera-env' if present ---
set "CAMVENV=%CD%\camera-env\Scripts\python.exe"
set "LOCALVENV=%CD%\.venv\Scripts\python.exe"

if exist "%CAMVENV%" (
  echo [setup] Activating camera-env
  call "%CD%\camera-env\Scripts\activate" || (echo [ERROR] Could not activate camera-env & exit /b 1)
) else if exist "%LOCALVENV%" (
  echo [setup] Activating local .venv
  call "%CD%\.venv\Scripts\activate" || (echo [ERROR] Could not activate .venv & exit /b 1)
) else (
  echo [setup] Creating local .venv (first run)
  python -m venv "%CD%\.venv" || (echo [ERROR] Python not found in PATH. Install Python or add it to PATH. & exit /b 1)
  call "%CD%\.venv\Scripts\activate"
  python -m pip install --upgrade pip
  if exist "%CD%\requirements.txt" (
    echo [setup] Installing from requirements.txt
    pip install -r "%CD%\requirements.txt"
  ) else (
    echo [setup] Installing minimal dependencies
    pip install streamlit streamlit-webrtc av opencv-python
  )
)

:RUN
echo [run] Launching Streamlit on port 5000
streamlit run "%CD%\app.py" --server.port 5000
endlocal
