# Camera Index Auto-Start Setup

This guide will set up the camera index app to start automatically when the Raspberry Pi boots, making it truly mobile without needing a terminal.

## Installation Steps

### 1. Install the systemd service

```bash
# Copy the service file to systemd directory
sudo cp /home/pinchevs/Desktop/camera-apps/camera-index.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start at boot
sudo systemctl enable camera-index.service

# Start the service now (without rebooting)
sudo systemctl start camera-index.service
```

### 2. Check service status

```bash
# View service status
sudo systemctl status camera-index.service

# View logs
journalctl -u camera-index.service -f
```

### 3. Managing the service

```bash
# Stop the service
sudo systemctl stop camera-index.service

# Restart the service
sudo systemctl restart camera-index.service

# Disable auto-start (but keep installed)
sudo systemctl disable camera-index.service

# Remove the service completely
sudo systemctl stop camera-index.service
sudo systemctl disable camera-index.service
sudo rm /etc/systemd/system/camera-index.service
sudo systemctl daemon-reload
```

## How It Works

- The service starts at boot (after `multi-user.target`)
- Runs as user `pinchevs` (so it has access to GPIO)
- Automatically restarts if it crashes
- Working directory is `/home/pinchevs/Desktop/camera-apps`
- Logs are accessible via `journalctl`

## Testing

1. Install the service with the commands above
2. Reboot the Pi: `sudo reboot`
3. The camera index should start automatically
4. Long press the button to launch apps, short press to navigate
5. The device is now fully mobile - no terminal needed!
