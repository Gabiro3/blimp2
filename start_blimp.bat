@echo off
REM Activate the virtual environment
call blimp_venv\Scripts\activate.bat

REM Run the FastAPI app with Uvicorn
call uvicorn main:app --host 0.0.0.0 --port 8000