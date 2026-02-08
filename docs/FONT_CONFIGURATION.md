# Centralized Font Configuration

## Overview
All fonts in ImgApp are now controlled from a single location: `client/utils/font_manager.py`

## Font Settings (Change these to update the entire app)

```python
# In client/utils/font_manager.py
FONT_FAMILY = "Consolas"      # Windows-native monospace font
FONT_SIZE_BASE = 10           # Base application font
FONT_SIZE_TITLE = 11          # Title bar fonts  
FONT_SIZE_BUTTON = 12         # Button fonts
```

## How to Use

### Get the Base Application Font
```python
from client.utils.font_manager import AppFonts

font = AppFonts.get_base_font()  # Size 10
font = AppFonts.get_base_font(bold=True)  # Size 10, bold
```

### Get Title Bar Font
```python
font = AppFonts.get_title_font()  # Size 11, bold by default
font = AppFonts.get_title_font(bold=False)  # Size 11, not bold
```

### Get Button Font
```python
font = AppFonts.get_button_font()  # Size 12
font = AppFonts.get_button_font(bold=True)  # Size 12, bold
```

### Get Custom Font
```python
font = AppFonts.get_custom_font(size=14, bold=True)  # Any size
```

## Where Fonts Are Used

- **main_window.py**: Title label, minimize/close buttons
- **login_window.py**: Trial dialogs, success/error messages
- **main.py**: Global application font (size 10)

## To Change Fonts Globally

1. Edit `FONT_FAMILY` (e.g., change "Consolas" to "Courier New")
2. Edit any of the `FONT_SIZE_*` constants
3. All UI elements using `AppFonts` methods will automatically update

## Font Family Options

Windows-native fonts that work everywhere:
- **Consolas** (recommended) - Modern monospace
- **Courier New** - Classic monospace
- **Arial** - Sans-serif
- **Segoe UI** - Modern sans-serif (Windows 6+)

**Avoid**: Fonts that may not be installed on user systems
- Roboto Mono (unless bundled in .exe)
- Custom/external fonts (unless bundled)
