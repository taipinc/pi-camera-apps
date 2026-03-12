#!/usr/bin/env python3
from time import sleep
import time
from PIL import Image
import numpy as np
from datetime import datetime
from picamera2 import Picamera2
import RPi.GPIO as GPIO
from camera_apps_base import CameraAppBase
import os

class CameraAppSlitScan(CameraAppBase):
    """Slit scan camera app - captures still frames from camera 1"""
    
    def __init__(self, board, shared_state=None):
        super().__init__(board, shared_state=shared_state)
        self.cam1 = None
        self.video_config = None
        self.capturing = False  # Toggle state for capture
        self.frame_count = 0
        self.output_dir = "slit_scan_test"
        self.last_frame_time = 0
        self.slit_lines = []  # Accumulate slit lines for final image
        
    def start(self):
        """Initialize camera and start video stream at 60fps"""
        print("Starting Slit Scan camera app...")
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize camera 1
        self.cam1 = Picamera2(1)
        
        # Configure camera for 60fps video capture
        # Use a balanced resolution that can handle 60fps
        self.video_config = self.cam1.create_video_configuration(
            main={"size": (1536, 864), "format": "RGB888"},
            controls={"FrameRate": 60}
        )
        
        self.cam1.configure(self.video_config)
        self.cam1.start()
        
        # Give camera initial warmup
        sleep(1)
        
        # Set white balance controls explicitly
        # Try setting AWB mode to auto and enable it
        try:
            self.cam1.set_controls({
                "AwbEnable": 1,  # Use integer instead of boolean
                "AeEnable": 1,   # Auto exposure
            })
            print("AWB controls set")
        except Exception as e:
            print(f"Warning: Could not set AWB controls: {e}")
        
        # Give camera more time to adjust white balance
        print("Waiting for AWB to stabilize...")
        sleep(3)
        
        # Check current metadata to see what WB is being used
        metadata = self.cam1.capture_metadata()
        print(f"Camera metadata: ColourGains={metadata.get('ColourGains', 'N/A')}, ColourTemperature={metadata.get('ColourTemperature', 'N/A')}")
        
        self.running = True
        self.exit_requested = False
        self.capturing = False
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.slit_lines = []
        
        print("Slit Scan ready. Press button to start/stop capturing at 60fps.")
        print(f"Video config: 1536x864 @ 60fps")
        print(f"Slit scan: extracting middle horizontal line (1536x1 pixels)")
        print(f"Final image will stack all lines vertically")
        print(f"Screen: {self.board.LCD_WIDTH}x{self.board.LCD_HEIGHT}")
    
    def stop(self):
        """Stop camera and cleanup"""
        print("Stopping Slit Scan camera app...")
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
    
    def on_button_press(self):
        """Handle button press - short=toggle capture, long=exit"""
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
                    self.capturing = False  # Stop capturing
                    return False  # Signal exit
                sleep(0.05)
            
            # Short Press - Toggle capture
            self.capturing = not self.capturing
            if self.capturing:
                print("Short Press: Started capturing")
                self.frame_count = 0  # Reset frame count
                self.slit_lines = []  # Clear previous slit lines
                # Visual feedback - green LED
                self.board.set_rgb(0, 255, 0)
            else:
                print("Short Press: Stopped capturing")
                # Save final stacked image
                self.save_final_slit_scan()
                # Turn off LED
                self.board.set_rgb(0, 0, 0)
                
            return True  # Continue running
            
        except Exception as e:
            print(f"Button handler error: {e}")
            return True
    
    def save_final_slit_scan(self):
        """Save the final stacked slit scan image"""
        if len(self.slit_lines) == 0:
            print("No slit lines captured")
            return
            
        # Convert list of (1, 1536, 3) arrays to a single (N, 1536, 3) array
        # First squeeze out the extra dimension from each line
        lines_squeezed = [line.squeeze(0) for line in self.slit_lines]  # Each becomes (1536, 3)
        # Stack them vertically
        final_image = np.array(lines_squeezed)  # Shape: (N, 1536, 3)
        
        # Fix color channels: Camera outputs RGB but we need to verify
        # If colors are wrong (purple<->orange swap), it means BGR, so convert
        final_image_rgb = final_image[:, :, ::-1]  # Reverse channel order (BGR -> RGB)
        
        print(f"Final slit scan shape: {final_image_rgb.shape} ({len(self.slit_lines)} lines)")
        
        # Convert to PIL and save
        img = Image.fromarray(final_image_rgb.astype(np.uint8)).convert('RGB')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"{self.output_dir}/{timestamp}_slitscan_final.png"
        img.save(filepath, "PNG")
        
        print(f"✓ Saved final slit scan: {filepath}")
    
    def update(self):
        """Update display with camera preview and capture frames if active"""
        if self.exit_requested:
            return False  # Signal to exit
        
        try:
            # Grab a frame from the video stream
            frame = self.cam1.capture_array()
            
            # If capturing, save the slit line at 60fps
            if self.capturing:
                # Debug: print frame shape on first frame
                if self.frame_count == 0:
                    print(f"Full frame shape: {frame.shape}")
                    self.last_frame_time = time.time()
                
                # Extract middle horizontal line for slit scan
                # Frame is (864, 1536, 3), we want row 432 (middle)
                middle_row = frame.shape[0] // 2
                slit_line = frame[middle_row:middle_row+1, :, :]  # Shape: (1, 1536, 3)
                
                if self.frame_count == 0:
                    print(f"Slit line shape: {slit_line.shape}")
                
                # Append slit line to accumulator (keep as 1x1536x3)
                self.slit_lines.append(slit_line)
                
                self.frame_count += 1
                
                # Print every 60 frames to show actual fps
                if self.frame_count % 60 == 0:
                    elapsed = time.time() - self.last_frame_time
                    actual_fps = 60.0 / elapsed if elapsed > 0 else 0
                    print(f"✓ Captured {self.frame_count} lines (actual fps: {actual_fps:.1f})")
                    self.last_frame_time = time.time()
                
                # No sleep - capture as fast as possible
                # sleep(1.0 / 60.0)
            else:
                # Just show preview when not capturing
                # Convert BGR to RGB for correct colors on display
                frame_rgb = frame[:, :, ::-1]  # Reverse channel order
                img = Image.fromarray(frame_rgb).convert('RGB')
                
                # Resize to fit screen
                img = img.resize((self.board.LCD_WIDTH, self.board.LCD_HEIGHT))
                
                # Convert to RGB565 byte list
                rgb565_data = self.pil_to_rgb565(img)
                
                # Display on screen
                self.board.draw_image(0, 0, self.board.LCD_WIDTH, self.board.LCD_HEIGHT, rgb565_data)

                # Publish JPEG to shared state for web streaming
                if self.shared_state is not None:
                    from io import BytesIO
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    self.shared_state.set_latest_frame(buf.getvalue())

                sleep(0.033)  # ~30fps for preview
            
            return True  # Continue running
            
        except Exception as e:
            print(f"Update error: {e}")
            return False  # Exit on error
