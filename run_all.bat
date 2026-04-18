@echo off
echo ==========================================
echo   Cold Chain Monitor: Starting Services
echo ==========================================

:: 1. Start the API
echo [1/4] Starting FastAPI...
start "API Server" cmd /k "uvicorn api.main:app --reload"

:: 2. Start the Subscriber
echo [2/4] Starting MQTT Subscriber...
start "Subscriber" cmd /k "python subscriber/subscriber.py"

:: 3. Start the Simulator
echo [3/4] Starting Sensor Simulator...
start "Simulator" cmd /k "python simulator/multi_sensor_sim.py"

:: 4. Start the Dashboard
echo [4/4] Starting Streamlit Dashboard...
start "Dashboard" cmd /k "streamlit run dashboard/app.py"

echo.
echo All services are launching in separate windows.
echo Keep them open to maintain the monitoring system!
pause
