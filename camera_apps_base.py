#!/usr/bin/env python3
"""
Base class for camera apps.
All camera apps should inherit from this class and implement the required methods.
"""

class CameraAppBase:
    """Base class for camera applications"""
    
    def __init__(self, board, shared_state=None):
        """
        Initialize the camera app

        Args:
            board: WhisPlayBoard instance (shared with index)
            shared_state: Optional SharedState instance for web UI integration
        """
        self.board = board
        self.shared_state = shared_state
        self.running = False
        self.exit_requested = False
    
    def start(self):
        """
        Start the camera app (initialize cameras, set up preview, etc.)
        Called when app is launched from index.
        """
        raise NotImplementedError("Subclass must implement start()")
    
    def stop(self):
        """
        Stop the camera app and cleanup resources (stop cameras, etc.)
        Called when returning to index.
        """
        raise NotImplementedError("Subclass must implement stop()")
    
    def update(self):
        """
        Update loop - grab frames, update display, etc.
        Called repeatedly in main loop while app is active.
        Returns True to continue, False to exit to index.
        """
        raise NotImplementedError("Subclass must implement update()")
    
    def on_button_press(self):
        """
        Handle button press events.
        Should implement short press (capture) and long press (exit) logic.
        Returns True to continue, False to exit to index.
        """
        raise NotImplementedError("Subclass must implement on_button_press()")
