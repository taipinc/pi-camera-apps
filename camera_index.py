#!/usr/bin/env python3
import sys
import os
import time
import threading
from PIL import Image, ImageDraw, ImageFont
import cairosvg
from io import BytesIO

# Add WhisPlay driver to path
sys.path.append("/home/pinchevs/Whisplay/Driver")
try:
    from WhisPlay import WhisPlayBoard
except ImportError:
    print("Error: Could not import WhisPlayBoard. Check path in /home/pinchevs/Whisplay/Driver")
    sys.exit(1)

# Import camera app modules
from dual_cam_raw_app import CameraAppRaw
from dual_cam_pixmix_app import CameraAppPixmix
from slit_scan_app import CameraAppSlitScan

# Web UI imports
from shared_state import SharedState
from web_server import start_server

# Module-level shared state singleton
shared_state = SharedState()

# Map script names to app classes and their icon paths
APP_CLASSES = {
    "dual-cam-raw": {
        "class": CameraAppRaw,
        "icon": "/home/pinchevs/Desktop/camera-apps/icons/swipe-two-fingers-up-gesture.svg"
    },
    "dual-cam-pixmix": {
        "class": CameraAppPixmix,
        "icon": "/home/pinchevs/Desktop/camera-apps/icons/split-square-dashed.svg"
    },
    "slit-scan-1": {
        "class": CameraAppSlitScan,
        "icon": "/home/pinchevs/Desktop/camera-apps/icons/scanning.svg"
    },
}

class CameraIndexApp:
    def __init__(self, shared_state):
        self.shared_state = shared_state
        self.board = None
        self.active_app = None
        self.scripts = []
        self.selection_index = 0
        self.launch_requested = False

        self.load_scripts()
        self.init_board()

    def load_scripts(self):
        """Load available camera apps"""
        self.scripts = []
        for name, app_info in APP_CLASSES.items():
            self.scripts.append({
                "name": name,
                "app_class": app_info["class"],
                "icon_path": app_info["icon"]
            })
            
    def init_board(self):
        """Initialize the WhisPlay board"""
        if self.board:
            self.board.cleanup()
        
        self.board = WhisPlayBoard()
        # Set backlight
        self.board.set_backlight(100)
        # Register button callback
        self.board.on_button_press(self.on_whisplay_button)
        
        self.draw_grid()

    def on_whisplay_button(self):
        """Handle button press - delegate to active app or handle grid navigation"""
        try:
            import RPi.GPIO as GPIO
            start_time = time.time()
            BUTTON_PIN = 11
            
            # If an app is active, let it handle the button press
            if self.active_app:
                # Poll while pressed
                while GPIO.input(BUTTON_PIN) == 1:
                    if time.time() - start_time > 0.25:
                    # Long Press - Exit app
                        print("Long Press: Exiting app")
                        # Call the app's button handler which will set exit_requested
                        self.active_app.on_button_press()
                        return
                    time.sleep(0.05)
                
                # Short Press - Let app handle it (capture)
                print("Short Press: App handling")
                self.active_app.on_button_press()
                return
            
            # Grid mode - handle navigation and launch
            # Poll while pressed
            while GPIO.input(BUTTON_PIN) == 1:
                if time.time() - start_time > 0.25:
                    # Long Press - Launch app
                    print("Long Press: Launching")
                    self.launch_requested = True
                    return
                time.sleep(0.05)
            
            # Short Press - Next item
            print("Short Press: Next Item")
            self.selection_index = (self.selection_index + 1) % len(self.scripts)
            self.draw_grid()
            
        except Exception as e:
            print(f"Button callback error: {e}")

    def pil_to_rgb565(self, img):
        """Convert PIL Image to RGB565 byte list"""
        width, height = img.size
        pixel_data = []
        for y in range(height):
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.append((rgb565 >> 8) & 0xFF)
                pixel_data.append(rgb565 & 0xFF)
        return pixel_data

    def draw_grid(self):
        """Draw the app selection grid"""
        if not self.board:
            return

        w = self.board.LCD_WIDTH
        h = self.board.LCD_HEIGHT
        
        # Create image
        img = Image.new('RGB', (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Grid settings
        cols = 3
        rows = 3
        cell_w = w // cols
        cell_h = h // rows
        
        # Draw items (limit to 9)
        visible_items = self.scripts[:9]
        
        for i, item in enumerate(visible_items):
            row = i // cols
            col = i % cols
            
            x = col * cell_w
            y = row * cell_h
            
            # All cells have black background
            draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], fill=(0, 0, 0))
            margin = 2
            
            # Render SVG icon
            icon_path = item.get('icon_path')
            if icon_path and os.path.exists(icon_path):
                try:
                    # Calculate icon size (fit within cell with margin)
                    icon_size = min(cell_w - 2 * margin, cell_h - 2 * margin)
                    
                    # Read SVG content and replace stroke color
                    with open(icon_path, 'r') as f:
                        svg_content = f.read()
                    
                    # Determine icon color: red if selected, white otherwise
                    icon_color = '#FF0000' if i == self.selection_index else '#FFFFFF'
                    
                    # Replace all stroke colors with the desired color
                    svg_content = svg_content.replace('stroke="#000000"', f'stroke="{icon_color}"')
                    svg_content = svg_content.replace("stroke='#000000'", f"stroke='{icon_color}'")
                    svg_content = svg_content.replace('color="#000000"', f'color="{icon_color}"')
                    svg_content = svg_content.replace("color='#000000'", f"color='{icon_color}'")
                    
                    # Convert modified SVG to PNG in memory
                    png_data = cairosvg.svg2png(
                        bytestring=svg_content.encode('utf-8'),
                        output_width=icon_size,
                        output_height=icon_size
                    )
                    
                    # Load PNG as PIL Image
                    icon_img = Image.open(BytesIO(png_data)).convert('RGBA')
                    
                    # Create black background for icon
                    icon_bg = Image.new('RGB', (icon_size, icon_size), (0, 0, 0))
                    
                    # Composite icon onto background
                    icon_bg.paste(icon_img, (0, 0), icon_img)
                    
                    # Calculate position to center icon in cell
                    icon_x = x + margin + (cell_w - 2 * margin - icon_size) // 2
                    icon_y = y + margin + (cell_h - 2 * margin - icon_size) // 2
                    
                    # Paste icon onto grid
                    img.paste(icon_bg, (icon_x, icon_y))
                    
                except Exception as e:
                    print(f"Error rendering icon {icon_path}: {e}")
                    # Fallback: draw a colored rectangle
                    draw.rectangle([x + margin, y + margin, x + cell_w - margin - 1, y + cell_h - margin - 1], fill=(128, 128, 128))
            
        # Push to display
        rgb_data = self.pil_to_rgb565(img)
        self.board.draw_image(0, 0, w, h, rgb_data)

    def launch_app(self):
        """Launch the selected camera app"""
        if self.selection_index >= len(self.scripts):
            return
            
        script_info = self.scripts[self.selection_index]
        app_class = script_info['app_class']
        
        print(f"Launching {script_info['name']}...")
        
        try:
            # Instantiate the app (pass the board instance and shared state)
            self.active_app = app_class(self.board, shared_state=self.shared_state)
            # Start the app
            self.active_app.start()
            self.shared_state.set_active_app_name(script_info['name'])
        except Exception as e:
            print(f"Failed to launch app: {e}")
            self.active_app = None

    def stop_active_app(self):
        """Stop the currently active app and return to grid"""
        if self.active_app:
            print("Stopping active app...")
            try:
                self.active_app.stop()
            except Exception as e:
                print(f"Error stopping app: {e}")
            self.active_app = None
            self.shared_state.set_active_app_name(None)
            self.shared_state.set_latest_frame(None)
            # Redraw grid
            self.draw_grid()

    def _handle_web_commands(self):
        """Check and act on pending web UI commands."""
        # Check for pending app switch
        switch_to = self.shared_state.get_pending_switch()
        if switch_to is not None:
            self.shared_state.set_pending_switch(None)
            # Stop current app if running
            if self.active_app:
                self.stop_active_app()
            # Find the requested app by name and launch it
            for i, script in enumerate(self.scripts):
                if script["name"] == switch_to:
                    self.selection_index = i
                    self.launch_app()
                    break

        # Check for pending capture
        if self.shared_state.get_pending_capture():
            self.shared_state.set_pending_capture(False)
            if self.active_app and hasattr(self.active_app, "capture_images"):
                self.active_app.capture_images()

    def run(self):
        """Main event loop"""
        print("Camera Index Running...")
        try:
            while True:
                # Check for launch request (from hardware button)
                if self.launch_requested:
                    self.launch_requested = False
                    if not self.active_app:
                        self.launch_app()

                # Check for web UI commands
                self._handle_web_commands()

                # If an app is active, run its update loop
                if self.active_app:
                    should_continue = self.active_app.update()
                    if not should_continue:
                        # App requested exit
                        self.stop_active_app()

                # Small sleep to not burn CPU
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            if self.active_app:
                self.active_app.stop()
            if self.board:
                self.board.cleanup()

if __name__ == "__main__":
    # Start web server in a daemon thread
    web_thread = threading.Thread(
        target=start_server,
        args=(shared_state,),
        daemon=True,
    )
    web_thread.start()
    print("Web server started on http://0.0.0.0:8080")

    app = CameraIndexApp(shared_state)
    app.run()
