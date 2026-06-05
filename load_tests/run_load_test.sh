#!/bin/bash
# Script to run Locust load tests against the VPS deployment.

TARGET_URL="http://217.216.73.190"

echo "🧪 Locust Load Tester for GoTouchGrass"
echo "======================================"

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 is required but not installed. Exiting."
    exit 1
fi

# Check if locust is installed in virtual environment
if [ ! -f backend/.venv/bin/locust ]; then
    echo "ℹ️ Locust is not installed in venv. Installing locust using venv pip..."
    backend/.venv/bin/pip install locust || {
        echo "❌ Failed to install locust in venv."
        exit 1
    }
fi

echo "🚀 Starting Locust web interface..."
echo "👉 Open http://localhost:8089 in your browser to start the load test."
echo "👉 Set the Target Host to: $TARGET_URL"
echo ""

backend/.venv/bin/locust -f load_tests/locustfile.py --host "$TARGET_URL"
