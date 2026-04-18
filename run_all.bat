@echo off
echo ==========================================
echo   Cold Chain Monitor: Starting Services
echo ==========================================

:: 0. Start InfluxDB
echo [0/5] Starting InfluxDB...
start "InfluxDB Server" "C:\Users\ojass\Downloads\influxd.exe"
timeout /t 3

:: 1. Start the API
echo [1/5] Starting FastAPI...
start "API Server" cmd /k "uvicorn api.main:app --reload"

:: 2. Start the Subscriber
echo [2/5] Starting MQTT Subscriber...
start "Subscriber" cmd /k "python subscriber/subscriber.py"

:: 3. Start the Simulator
echo [3/5] Starting Sensor Simulator...
start "Simulator" cmd /k "python simulator/multi_sensor_sim.py"

:: 4. Start the Dashboard
echo [4/5] Starting Streamlit Dashboard...
start "Dashboard" cmd /k "streamlit run dashboard/app.py"

echo.
echo All services are launching in separate windows.
echo Keep them open to maintain the monitoring system!
pause
