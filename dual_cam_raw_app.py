#!/usr/bin/env python3
from time import sleep
import time
from PIL import Image
import numpy as np
from datetime import datetime
from picamera2 import Picamera2
import RPi.GPIO as GPIO
from camera_apps_base import CameraAppBase

class CameraAppRaw(CameraAppBase):
    """Dual camera RAW capture app"""
    
    def __init__(self, board, shared_state=None):
        super().__init__(board, shared_state=shared_state)
        self.cam0 = None
        self.cam1 = None
        self.preview_config0 = None
        self.preview_config1 = None
        self.still_config0 = None
        self.still_config1 = None
        
    def start(self):
        """Initialize cameras and start preview"""
        print("Starting RAW camera app...")
        
        # Initialize both cameras
        self.cam0 = Picamera2(0)
        self.cam1 = Picamera2(1)
        
        # Configure cameras - preview config for display, still config for capture
        self.preview_config0 = self.cam0.create_preview_configuration(
            main={"size": (self.board.LCD_WIDTH, self.board.LCD_HEIGHT//2)}
        )
        self.preview_config1 = self.cam1.create_preview_configuration(
            main={"size": (self.board.LCD_WIDTH, self.board.LCD_HEIGHT//2)}
        )
        
        self.still_config0 = self.cam0.create_still_configuration(
            raw={"size": self.cam0.sensor_resolution}
        )
        self.still_config1 = self.cam1.create_still_configuration(
            raw={"size": self.cam1.sensor_resolution}
        )
        
        # Start with preview configuration
        self.cam0.configure(self.preview_config0)
        self.cam1.configure(self.preview_config1)
        
        self.cam0.start()
        self.cam1.start()
        
        # Give cameras time to warm up
        sleep(2)
        
        self.running = True
        self.exit_requested = False
        
        print("Dual camera ready. Press button to capture.")
        print(f"Screen: {self.board.LCD_WIDTH}x{self.board.LCD_HEIGHT}")
    
    def stop(self):
        """Stop cameras and cleanup"""
        print("Stopping RAW camera app...")
        if self.cam0:
            self.cam0.stop()
            self.cam0.close()
            self.cam0 = None
        if self.cam1:
            self.cam1.stop()
            self.cam1.close()
            self.cam1 = None
        self.running = False
    
    def pil_to_rgb565(self, img):
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
    
    def capture_images(self):
        """Capture full-resolution images from both cameras"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create subfolder for raw captures in the script's directory
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "raw_captures")
        os.makedirs(output_dir, exist_ok=True)
        
        # Visual feedback - flash green
        self.board.set_rgb(0, 255, 0)
        
        # Stop preview
        self.cam0.stop()
        self.cam1.stop()
        
        # Switch to still configuration for full-res capture
        self.cam0.configure(self.still_config0)
        self.cam1.configure(self.still_config1)
        
        self.cam0.start()
        self.cam1.start()
        sleep(1)  # Let camera adjust
        
        # Combined capture for both cameras to ensure better sync and efficiency
        req0 = self.cam0.capture_request()
        req1 = self.cam1.capture_request()
        
        # Save cam0 JPG and DNG
        req0.save("main", f"{output_dir}/{timestamp}_cam0.jpg")
        req0.save_dng(f"{output_dir}/{timestamp}_cam0.dng")
        
        # Rotate cam1 by 180 degrees before saving (physically rotated camera)
        arr1 = req1.make_array("main")
        img1 = Image.fromarray(arr1)
        img1 = img1.rotate(180)
        img1.save(f"{output_dir}/{timestamp}_cam1.jpg", quality=95)
        
        # Save cam1 DNG (note: DNG orientation may need EXIF adjustment)
        req1.save_dng(f"{output_dir}/{timestamp}_cam1.dng")
        
        print(f"  Cam0: saved jpg + dng to {output_dir}/")
        print(f"  Cam1: saved jpg (rotated) + dng to {output_dir}/")

        # Release requests
        req0.release()
        req1.release()
        
        # Switch back to preview
        self.cam0.stop()
        self.cam1.stop()
        
        self.cam0.configure(self.preview_config0)
        self.cam1.configure(self.preview_config1)
        
        self.cam0.start()
        self.cam1.start()
        
        self.board.set_rgb(0, 0, 0)
        
        print(f"✓ Captured: {timestamp}")
    
    def on_button_press(self):
        """Handle button press - short=capture, long=exit"""
        try:
            # Wait to debounce/check duration
            start_time = time.time()
            BUTTON_PIN = 11
            
            # Poll while pressed (Active High)
            while GPIO.input(BUTTON_PIN) == 1:
                if time.time() - start_time > 0.25:
                    # Long Press Detected - Exit
                    print("Long Press: Exiting to Index")
                    self.exit_requested = True
                    return False  # Signal exit
                sleep(0.05)
            
            # Short Press - Capture
            print("Short Press: Capture")
            self.capture_images()
            return True  # Continue running
            
        except Exception as e:
            print(f"Button handler error: {e}")
            return True
    
    def update(self):
        """Update display with camera preview"""
        if self.exit_requested:
            return False  # Signal to exit
        
        try:
            # Grab frames from both cameras
            frame0 = self.cam0.capture_array()
            frame1 = self.cam1.capture_array()
            
            # Convert to PIL Images and ensure RGB
            img0 = Image.fromarray(frame0).convert('RGB')
            img1 = Image.fromarray(frame1).convert('RGB')
            
            # Rotate cam1 by 180 degrees (physically rotated camera)
            img1 = img1.rotate(180)
            
            # Resize to fit vertically stacked
            img0 = img0.resize((self.board.LCD_WIDTH, self.board.LCD_HEIGHT//2))
            img1 = img1.resize((self.board.LCD_WIDTH, self.board.LCD_HEIGHT//2))
            
            # Create top-bottom composite
            composite = Image.new('RGB', (self.board.LCD_WIDTH, self.board.LCD_HEIGHT))
            composite.paste(img0, (0, 0))
            composite.paste(img1, (0, self.board.LCD_HEIGHT//2))
            
            # Convert to RGB565 byte list
            rgb565_data = self.pil_to_rgb565(composite)
            
            # Display on screen
            self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, rgb565_data)

            # Publish JPEG to shared state for web streaming
            if self.shared_state is not None:
                from io import BytesIO
                buf = BytesIO()
                composite.save(buf, format="JPEG", quality=70)
                self.shared_state.set_latest_frame(buf.getvalue())

            sleep(0.033)  # ~30fps
            return True  # Continue running
            
        except Exception as e:
            print(f"Update error: {e}")
            return False  # Exit on error
