# Command Panel Architecture & Naming Conventions

## Overview

The **Command Panel** is the right-side sliding panel that appears when Lab Mode is activated.
It contains conversion settings organized into tabs (Image, Video, Loop).

---

## Command Panel Side Buttons

All side buttons are vertical buttons positioned on the LEFT edge of the Command Panel.
They "peek" out from behind folder containers and slide out on hover/selection.

### 1. Command Panel Main Folder Buttons (`mode_buttons`)

Located at the TOP of the Command Panel. Controls the global conversion mode.

| Button | ID | Description |
|--------|-----|-------------|
| **Max Size** | `max_size` | Automatic sizing based on optimal parameters |
| **Lab Presets** | `presets` | Use predefined conversion presets |
| **Manual Options** | `manual` | Full manual control over all parameters |

**Variable Reference:** `self.command_panel.mode_buttons` (ModeButtonsWidget)

### 2. Command Panel Transform Folder Buttons (`image_side_buttons`, `video_side_buttons`, `loop_side_buttons`)

Located BELOW the Main Folder. Controls which transform options are visible.
Different buttons appear based on the active tab.

| Button | ID | Tabs | Description |
|--------|-----|------|-------------|
| **Resize Options** | `resize` | All | Scale/resize settings |
| **Rotate Options** | `rotate` | All | Rotation angle settings |
| **Time Options** | `time` | Video, Loop | Trim, speed, frame rate |

**Variable References:**
- `self.command_panel.image_side_buttons` (SideButtonGroup) - Image tab
- `self.command_panel.video_side_buttons` (SideButtonGroup) - Video tab  
- `self.command_panel.loop_side_buttons` (SideButtonGroup) - Loop tab

---

## Animation System

### Panel Slide Animation

Located in: `client/gui/main_window.py` → `toggle_command_panel()`

Configuration constants:
```python
PANEL_TARGET_RATIO = 0.4           # Panel width as % of total
PANEL_SHOW_DURATION_MS = 450       # Slide-in duration
PANEL_HIDE_DURATION_MS = 300       # Slide-out duration
PANEL_SHOW_EASING = "OutBack"      # Entrance easing
PANEL_HIDE_EASING = "OutQuad"      # Exit easing
PANEL_SPRING_OVERSHOOT = 0.7       # Spring intensity
```

### Side Buttons Stagger Animation

All Command Panel Side Buttons appear in a staggered sequence (top to bottom)
during the panel slide animation. On hide, all buttons hide simultaneously,
then the panel slides out.

**SHOW Configuration:**
```python
BUTTONS_REVEAL_THRESHOLD = 0.9     # When buttons start appearing (0-1 progress)
BUTTONS_SHOW_STAGGER_MS = 60       # Delay between each button (staggered)
BUTTONS_SHOW_DURATION_MS = 200     # Individual button animation
BUTTONS_SHOW_EASING = "OutCubic"   # Button reveal easing
```

**HIDE Configuration:**
```python
BUTTONS_HIDE_DURATION_MS = 150     # Faster hide for snappy feel
BUTTONS_HIDE_EASING = "InQuad"     # Accelerate into hide
BUTTONS_HIDE_HEAD_START_MS = 100   # Delay before panel starts hiding
```

**Animation Sequence:**

*On SHOW:*
1. Panel slides in from right (450ms, OutBack spring)
2. At 90% progress, buttons start revealing (top to bottom, 60ms stagger)

*On HIDE:*
1. All buttons hide simultaneously (150ms, InQuad)
2. After 100ms delay, panel slides out (300ms, OutQuad)

---

## Class References

| Class | File | Purpose |
|-------|------|---------|
| `CommandPanel` | `client/gui/command_panel.py` | Main panel widget |
| `ModeButtonsWidget` | `client/gui/custom_widgets.py` | Main Folder buttons |
| `SideButtonGroup` | `client/gui/custom_widgets.py` | Transform Folder buttons |
| `AnimatedSideModeButton` | `client/gui/custom_widgets.py` | Individual animated button |

---

## Key Methods

### Visibility Control

- `set_lab_mode_active(active)` - Enable/disable Lab mode
- `set_top_bar_preset_mode(active)` - Enable/disable Preset mode
- `set_hidden_mode(hidden, colored)` - Show/hide button groups
- `set_force_hidden(hidden)` - Individual button visibility

### Animation Triggers

- `toggle_command_panel(show)` - Main panel slide animation
- `_trigger_side_buttons_animation(hide)` - Stagger all side buttons
- `_reveal_button(btn)` - Reveal individual button with easing

---

## File Locations

- Panel Animation: `client/gui/main_window.py` (lines ~618-870)
- Button Widgets: `client/gui/custom_widgets.py`
- Panel Logic: `client/gui/command_panel.py`
- This Doc: `.agent/command_panel_architecture.md`
