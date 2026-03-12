#!/bin/bash
LOG="/tmp/ups_debug.log"
SOCKET="/tmp/camera_index.sock"
SCRIPT="/home/pinchevs/Desktop/camera-apps/camera_index.py"
DIR="/home/pinchevs/Desktop/camera-apps"

echo "$(date): Button Handler Triggered" >> "$LOG"

# Check if process is running
if pgrep -f "camera_index.py" > /dev/null; then
    echo "$(date): App is running. Sending NEXT." >> "$LOG"
    if [ -S "$SOCKET" ]; then
        echo "NEXT" | nc -U "$SOCKET" -w 1 >> "$LOG" 2>&1
        echo "$(date): Send result: $?" >> "$LOG"
    else
        echo "$(date): Socket not found at $SOCKET" >> "$LOG"
    fi
else
    echo "$(date): App not running. Checking for stuck children." >> "$LOG"
    
    # Kill any lingering camera scripts that might block hardware access
    pkill -f "dual-cam" >> "$LOG" 2>&1
    pkill -f "python.*pixmix" >> "$LOG" 2>&1
    sleep 1

    echo "$(date): Starting Camera Index." >> "$LOG"
    cd "$DIR"
    
    if [ "$(whoami)" == "root" ]; then
         echo "$(date): Running as root, switching to pinchevs" >> "$LOG"
         su pinchevs -c "/usr/bin/python3 -u $SCRIPT" > /tmp/camera_index.log 2>&1 &
    else
         /usr/bin/python3 -u "$SCRIPT" > /tmp/camera_index.log 2>&1 &
    fi
    echo "$(date): Launch command executed" >> "$LOG"
fi
