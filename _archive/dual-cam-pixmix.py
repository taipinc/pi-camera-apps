#!/usr/bin/env python3
from time import sleep
from PIL import Image
import sys
import os
import numpy as np
from datetime import datetime

# Add WhisPlay driver to path
sys.path.append(os.path.abspath("../../Whisplay/Driver"))
from WhisPlay import WhisPlayBoard

# Import camera library
from picamera2 import Picamera2

# Initialize hardware
board = WhisPlayBoard()
board.set_backlight(80)

# Initialize both cameras
cam0 = Picamera2(0)
cam1 = Picamera2(1)

# Configure cameras - preview config for display, still config for capture
preview_config0 = cam0.create_preview_configuration(main={"size": (board.LCD_WIDTH, board.LCD_HEIGHT//2)})
preview_config1 = cam1.create_preview_configuration(main={"size": (board.LCD_WIDTH, board.LCD_HEIGHT//2)})

still_config0 = cam0.create_still_configuration(raw={"size": cam0.sensor_resolution})
still_config1 = cam1.create_still_configuration(raw={"size": cam1.sensor_resolution})

# Start with preview configuration
cam0.configure(preview_config0)
cam1.configure(preview_config1)

cam0.start()
cam1.start()

# Give cameras time to warm up
sleep(2)

def pil_to_rgb565(img):
    """Convert PIL Image to RGB565 byte list"""
    width, height = img.size
    pixel_data = []
    
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))
            # Convert to RGB565
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            # Split into two bytes
            pixel_data.append((rgb565 >> 8) & 0xFF)
            pixel_data.append(rgb565 & 0xFF)
    
    return pixel_data

def capture_images():
    """Capture full-resolution images from both cameras and mix pixels vertically"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Visual feedback - flash green
    board.set_rgb(0, 255, 0)
    
    # Stop preview
    cam0.stop()
    cam1.stop()
    
    # Switch to still configuration for full-res capture
    cam0.configure(still_config0)
    cam1.configure(still_config1)
    
    cam0.start()
    cam1.start()
    sleep(1)  # Let camera adjust
    
    # Combined capture for both cameras to ensure better sync and efficiency
    # Get combined request from both cameras
    req0 = cam0.capture_request()
    req1 = cam1.capture_request()
    
    # Get image data as numpy arrays
    # Note: We use "main" stream which is configured to be full resolution
    arr0 = req0.make_array("main")
    arr1 = req1.make_array("main")
    
    # Check shapes
    h, w, c = arr0.shape
    
    # Create combined array: double height
    mixed = np.zeros((h * 2, w, c), dtype=np.uint8)
    
    # Interleave rows
    # Even rows take from cam0
    mixed[0::2, :, :] = arr0
    # Odd rows take from cam1
    mixed[1::2, :, :] = arr1
    
    # Convert to PIL Image
    img_mixed = Image.fromarray(mixed)
    
    # Save mixed JPG
    filename = f"{timestamp}_pixmix_v.jpg"
    img_mixed.save(filename, quality=95)
    
    print(f"  Saved mixed image: {filename} ({mixed.shape[1]}x{mixed.shape[0]})")

    # Release requests
    req0.release()
    req1.release()
    
    # Switch back to preview
    cam0.stop()
    cam1.stop()
    
    cam0.configure(preview_config0)
    cam1.configure(preview_config1)
    
    cam0.start()
    cam1.start()
    
    board.set_rgb(0, 0, 0)
    
    print(f"✓ Captured: {timestamp}")

# Global control flag
running = True

def on_button_pressed():
    """Button callback - capture images or exit"""
    global running
    try:
        import RPi.GPIO as GPIO
        import time
        # Wait to debounce/check duration
        start_time = time.time()
        BUTTON_PIN = 11
        
        # Poll while pressed (Active High)
        while GPIO.input(BUTTON_PIN) == 1:
            if time.time() - start_time > 0.5:
                # Long Press Detected - Exit
                print("Long Press: Exiting to Index")
                running = False
                return
            sleep(0.05)
        
        # Short Press - Capture
        print("Short Press: Capture")
        capture_images()
        
    except ImportError:
        print("GPIO Error in callback")

# Register button callback
board.on_button_press(on_button_pressed)

print("Dual camera ready. Press button to capture.")
print(f"Screen: {board.LCD_WIDTH}x{board.LCD_HEIGHT}")

try:
    while running:
        # Grab frames from both cameras
        frame0 = cam0.capture_array()
        frame1 = cam1.capture_array()
        
        # Convert to PIL Images and ensure RGB
        img0 = Image.fromarray(frame0).convert('RGB')
        img1 = Image.fromarray(frame1).convert('RGB')
        
        # Resize for preview mixing
        # We squash them vertically so that when interleaved they form the correct height
        target_size = (board.LCD_WIDTH, board.LCD_HEIGHT // 2)
        img0 = img0.resize(target_size)
        img1 = img1.resize(target_size)
        
        # Convert back to numpy for efficient interleaving
        arr0 = np.array(img0)
        arr1 = np.array(img1)
        
        # Create mixed array
        preview_mixed = np.zeros((board.LCD_HEIGHT, board.LCD_WIDTH, 3), dtype=np.uint8)
        
        # Interleave rows
        preview_mixed[0::2, :, :] = arr0
        preview_mixed[1::2, :, :] = arr1
        
        # Convert to PIL for final output
        final_preview = Image.fromarray(preview_mixed)
        
        # Convert to RGB565 byte list
        rgb565_data = pil_to_rgb565(final_preview)
        
        # Display on screen
        board.draw_image(0, 0, board.LCD_WIDTH, board.LCD_HEIGHT, rgb565_data)
        
        sleep(0.033)  # ~30fps
        
except KeyboardInterrupt:
    print("\nStopping...")
    
finally:
    cam0.stop()
    cam1.stop()
    board.cleanup()
    # Exit the process to return to index
    if not running:
        print("Returning to camera index...")
        sys.exit(0)