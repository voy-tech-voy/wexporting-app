"""
Theme Conductor

Manages theme propagation to all UI components in the application.
Follows the Mediator-Shell pattern by centralizing theme update logic.
"""

from PyQt6.QtCore import QObject


class ThemeConductor(QObject):
    """
    Conductor for managing theme changes across the application.
    
    Centralizes theme propagation logic to reduce MainWindow complexity.
    """
    
    def __init__(self, theme_manager, main_window, drag_drop_area, command_panel, 
                 control_bar, output_footer, title_bar_window):
        """
        Initialize the ThemeConductor.
        
        Args:
            theme_manager: ThemeManager instance
            main_window: MainWindow instance (for setStyleSheet)
            drag_drop_area: DragDropArea instance
            command_panel: CommandPanel instance
            control_bar: ControlBar instance
            output_footer: OutputFooter instance
            title_bar_window: TitleBarWindow instance
        """
        super().__init__()
        self.theme_manager = theme_manager
        self.main_window = main_window
        self.drag_drop_area = drag_drop_area
        self.command_panel = command_panel
        self.control_bar = control_bar
        self.output_footer = output_footer
        self.title_bar_window = title_bar_window
        
        # Connect to theme manager signal
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
    def _on_theme_changed(self, is_dark: bool):
        """Handle theme changes via ThemeManager signal"""
        # Apply main window styles (with caching to avoid redundant updates)
        main_style = self.theme_manager.get_main_window_style()
        
        # Only call setStyleSheet if the style actually changed
        if not hasattr(self.main_window, '_cached_main_style') or self.main_window._cached_main_style != main_style:
            self.main_window.setStyleSheet(main_style)
            self.main_window._cached_main_style = main_style
        
        # Update drag drop area theme
        self.drag_drop_area.set_theme_manager(self.theme_manager)
        
        # Update command panel theme
        if hasattr(self.command_panel, 'update_theme'):
            self.command_panel.update_theme(is_dark)
        
        # Update control bar theme
        if self.control_bar:
            self.control_bar.update_theme(is_dark)
        
        # Update title bar theme
        self._update_title_bar_theme(is_dark)
        
        # Apply global QToolTip styling
        from client.gui.custom_widgets import apply_tooltip_style
        apply_tooltip_style(is_dark)
        
        # Update output footer theme
        if self.output_footer:
            self.output_footer.update_theme(is_dark)
        
    def _update_title_bar_theme(self, is_dark):
        """Update title bar colors based on theme"""
        # Delegate to the separate TitleBarWindow
        if self.title_bar_window:
            self.title_bar_window.apply_theme(is_dark)
            
    def toggle_theme(self):
        """Toggle between dark and light theme"""
        current_theme = self.theme_manager.get_current_theme()
        new_theme = 'light' if current_theme == 'dark' else 'dark'
        self.theme_manager.set_theme(new_theme)
        # Note: Widgets auto-update via theme_changed signal
        # MainWindow-specific updates handled in _on_theme_changed()
