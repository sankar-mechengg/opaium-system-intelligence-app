# Window Dragging Feature

## Overview

Both the First Run Setup and Authentication (PIN/Password) screens can now be dragged and repositioned by clicking and holding anywhere on the window.

## Implementation Details

### Files Modified

1. **`src/auth/first_run_setup.py`**
   - Added `QPoint` and `QMouseEvent` imports
   - Added `_drag_position` instance variable to track drag offset
   - Implemented `mousePressEvent()` to capture initial click position
   - Implemented `mouseMoveEvent()` to move window during drag

2. **`src/auth/auth_screen.py`**
   - Added `QMouseEvent` import
   - Added `_drag_position` instance variable to track drag offset
   - Implemented `mousePressEvent()` to capture initial click position
   - Implemented `mouseMoveEvent()` to move window during drag

### How It Works

1. **Mouse Press Event**:
   - When user clicks (left button) anywhere on the window
   - Records the click position relative to the window's top-left corner
   - Stores this offset in `_drag_position`

2. **Mouse Move Event**:
   - When user moves mouse while holding left button
   - Calculates new window position: current mouse position - stored offset
   - Moves window to the new position
   - Creates smooth dragging effect

### User Experience

**First Run Setup Window**:
- Size: 520x680 pixels
- Starts centered on screen
- Can be dragged anywhere on screen
- Useful for multi-monitor setups or when window blocks other content

**Authentication Screen**:
- Size: 480x620 pixels
- Frameless design
- Starts centered on screen
- Can be dragged anywhere
- Maintains "Always On Top" behavior while dragging

### Code Pattern

```python
def __init__(self, ...):
    # Initialize drag position tracker
    self._drag_position = QPoint()

def mousePressEvent(self, event: QMouseEvent) -> None:
    """Record position for window dragging."""
    if event.button() == Qt.MouseButton.LeftButton:
        self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

def mouseMoveEvent(self, event: QMouseEvent) -> None:
    """Move window when dragging."""
    if event.buttons() == Qt.MouseButton.LeftButton:
        self.move(event.globalPosition().toPoint() - self._drag_position)
        event.accept()
```

### Benefits

1. **Flexibility**: Users can position windows where they prefer
2. **Multi-Monitor**: Easily move to different screens
3. **Accessibility**: No need for OS-level window management
4. **Modern UX**: Common pattern in modern applications
5. **Frameless Windows**: Essential for windows without title bar (auth screen)

### Technical Notes

- Uses `globalPosition()` for accurate multi-monitor support
- Only responds to left mouse button
- Smooth dragging with no latency
- No impact on other mouse interactions (buttons, inputs remain functional)
- Window stays within screen bounds (OS enforced)

### Testing

1. **First Run Setup**:
   - Launch app for first time
   - Click and hold anywhere on the setup window
   - Drag to new position
   - Release to drop

2. **Auth Screen**:
   - Launch app after setup
   - Click and hold anywhere on the lock screen
   - Drag to new position
   - Release to drop
   - Test that PIN/password entry still works

### Future Enhancements

Potential improvements:
- Visual feedback (cursor change) to indicate draggable area
- Remember last window position between sessions
- Snap-to-edge behavior
- Double-click title area to maximize/restore
- Prevent dragging partially off-screen

### Compatibility

- Works on all screen resolutions
- Multi-monitor aware
- Windows 10/11 compatible
- No external dependencies
