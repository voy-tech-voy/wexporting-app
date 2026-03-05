"""
Mode Conductor - Mediator-Shell Architecture

Extracted from MainWindow to handle application mode switching logic.
Coordinates UI state changes between Preset and Lab modes.
"""

from PySide6.QtCore import QObject, Signal, QTimer
from enum import Enum


class Mode(Enum):
    """Application mode for MainWindow conductor."""
    PRESET = "preset"  # Preset mode - simple drag & drop with presets
    LAB = "lab"        # Lab mode - full command panel visible


class ModeConductor(QObject):
    """
    Conductor for application mode switching (Preset ↔ Lab).
    
    Responsibilities:
    - Manage current mode state
    - Coordinate UI component visibility and state
    - Handle mode transition animations
    - Emit signals for mode changes
    
    This class follows the Mediator-Shell pattern: it coordinates
    multiple UI components without them needing to know about each other.
    """
    
    # Signals
    mode_changed = Signal(Mode)  # Emitted when mode switches
    
    def __init__(self, 
                 control_bar,
                 command_panel,
                 drag_drop_area,
                 panel_animator,
                 output_footer,
                 lab_btn,
                 preset_status_btn,
                 right_frame):
        """
        Initialize the ModeConductor.
        
        Args:
            control_bar: ControlBar component
            command_panel: CommandPanel component
            drag_drop_area: DragDropArea component
            panel_animator: SidePanelAnimator for panel transitions
            output_footer: OutputFooter component
            lab_btn: MorphingButton for lab mode
            preset_status_btn: PresetStatusButton for preset mode
            right_frame: QWidget containing the command panel
        """
        super().__init__()
        
        # Store component references
        self.control_bar = control_bar
        self.command_panel = command_panel
        self.drag_drop_area = drag_drop_area
        self.panel_animator = panel_animator
        self.output_footer = output_footer
        self.lab_btn = lab_btn
        self.preset_status_btn = preset_status_btn
        self.right_frame = right_frame
        
        # State
        self._current_mode = Mode.PRESET  # Default to preset mode
        self._active_lab_tab = 0          # Track active lab tab (0=Image, 1=Video, 2=Loop)
        self._active_preset = None        # Track active preset (set by MainWindow)
    
    @property
    def current_mode(self) -> Mode:
        """Get the current application mode."""
        return self._current_mode
    
    @property
    def active_lab_tab(self) -> int:
        """Get the currently active lab tab index."""
        return self._active_lab_tab
    
    def set_active_preset(self, preset):
        """Set the active preset (called by MainWindow when preset is applied)."""
        self._active_preset = preset
        self._update_footer_mode_active()
    
    def clear_active_preset(self):
        """Clear the active preset (called when switching to Lab mode)."""
        self._active_preset = None
        self._update_footer_mode_active()
    
    def switch_mode(self, mode: Mode, lab_tab: int = None):
        """
        Centralized mode switching - the heart of the Mediator pattern.
        
        All mode changes should go through this method to ensure:
        1. Consistent state across all components
        2. Proper animation sequencing
        3. UI state synchronization
        
        Args:
            mode: Target mode (Mode.PRESET or Mode.LAB)
            lab_tab: For LAB mode, which tab to activate (0=Image, 1=Video, 2=Loop)
        """
        if mode == Mode.PRESET:
            self._enter_preset_mode()
        elif mode == Mode.LAB:
            self._enter_lab_mode(lab_tab if lab_tab is not None else self._active_lab_tab)
        
        self._current_mode = mode
        self._update_footer_mode_active()
        self.mode_changed.emit(mode)
    
    def _update_footer_mode_active(self):
        """Update output footer mode active state based on current app state."""
        is_lab = (self._current_mode == Mode.LAB)
        has_preset = (self._active_preset is not None)
        self.output_footer.set_mode_active(is_lab or has_preset)
    
    def _enter_preset_mode(self):
        """Internal: Configure UI for Preset mode."""
        # 1. Hide Command Panel
        self.panel_animator.close()
        
        # 2. Deactivate Lab Button (Ghost style) and highlight preset mode
        self.lab_btn.set_style_solid(False)
        self.lab_btn.set_main_icon("client/assets/icons/lab_icon.svg")
        
        # Highlight preset mode in control bar (hides custom preset button)
        self.control_bar.highlight_preset()
        
        # 3. Notify CommandPanel state
        self.command_panel.set_lab_mode_active(False)
        self.command_panel.set_top_bar_preset_mode(True)
        
        # 4. Show Preset Overlay AFTER panel animation completes
        # Delay to allow drop area to expand to full width first
        QTimer.singleShot(350, self._show_preset_gallery_delayed)
    
    def _show_preset_gallery_delayed(self):
        """Show preset gallery after panel animation delay."""
        from client.gui.drag_drop_area import ViewMode
        self.drag_drop_area.set_view_mode(ViewMode.PRESETS)
    
    def toggle_preset_gallery(self):
        """
        Toggle the preset gallery overlay visibility without changing modes.
        
        This is called when the user clicks the preset button while already
        in Preset mode. Closing the gallery doesn't exit Preset mode - only
        selecting a Lab option does that.
        """
        from client.gui.drag_drop_area import ViewMode
        current_view = self.drag_drop_area.current_view_mode
        
        if current_view == ViewMode.PRESETS:
            # Gallery is open - close it (but stay in Preset mode)
            self.drag_drop_area.set_view_mode(ViewMode.FILES)
        else:
            # Gallery is closed - open it
            self.drag_drop_area.set_view_mode(ViewMode.PRESETS)
    
    def _enter_lab_mode(self, lab_tab: int):
        """Internal: Configure UI for Lab mode."""
        # Icon paths matching tab order
        icons = [
            "client/assets/icons/pic_icon2.svg",
            "client/assets/icons/vid_icon.svg",
            "client/assets/icons/loop_icon3.svg"
        ]
        
        # 1. Update lab button appearance and control bar state
        if 0 <= lab_tab < len(icons):
            self.lab_btn.set_main_icon(icons[lab_tab])
            self.lab_btn.set_style_solid(True)
        
        # Highlight lab mode in control bar (shows custom preset button)
        self.control_bar.highlight_lab()
        
        # 2. Reset Preset button to default state
        self.preset_status_btn.set_active(False)
        
        # 3. Notify CommandPanel
        self.command_panel.set_lab_mode_active(True)
        self.command_panel.set_top_bar_preset_mode(False)
        self.command_panel._on_tab_btn_clicked(lab_tab)
        
        # 4. Hide Preset Overlay
        from client.gui.drag_drop_area import ViewMode
        self.drag_drop_area.set_view_mode(ViewMode.FILES)
        
        # 5. Animate panel
        panel_already_visible = self.right_frame.isVisible()
        if not panel_already_visible:
            self.panel_animator.trigger_side_buttons_animation(hide=True)
        self.panel_animator.open()
        
        # 6. Track active tab
        self._active_lab_tab = lab_tab
    
    # =========================================================================
    # BUTTON HANDLERS (Delegate to switch_mode)
    # =========================================================================
    
    def on_preset_btn_clicked(self):
        """
        Handle preset button click.
        
        Behavior:
        - If currently in LAB mode: Switch to PRESET mode (opens gallery)
        - If currently in PRESET mode: Toggle gallery visibility only
          (keeps Preset Mode ON until Lab option is selected)
        """
        if self._current_mode == Mode.LAB:
            # Switch from Lab to Preset mode
            self.switch_mode(Mode.PRESET)
        else:
            # Already in Preset mode - just toggle the gallery visibility
            self.toggle_preset_gallery()
    
    def on_lab_item_clicked(self, item_id):
        """Handle lab button menu item click - delegate to switch_mode()."""
        type_map = {0: "IMAGE", 1: "VIDEO", 2: "LOOP"}
        print(f"[DEBUG_MAIN] Lab item clicked. ID={item_id} ({type_map.get(item_id, 'UNKNOWN')})")
        self.switch_mode(Mode.LAB, lab_tab=item_id)
    
    def on_lab_state_changed(self, icon_path, is_solid):
        """Handle lab button state change from CommandPanel."""
        self.lab_btn.set_main_icon(icon_path)
        self.lab_btn.set_style_solid(is_solid)
