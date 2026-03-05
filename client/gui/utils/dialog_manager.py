"""
Dialog Manager for unified dialog handling.

Centralizes all QMessageBox operations with consistent styling and behavior.
This removes boilerplate from MainWindow and ensures all dialogs follow
the app's theming guidelines.
"""

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


class DialogManager:
    """
    Manages application dialogs with consistent styling and behavior.
    
    Usage:
        dialogs = DialogManager(parent_widget, theme_manager)
        dialogs.show_info("Title", "Message text")
        if dialogs.confirm_action("Logout", "Are you sure?"):
            # User confirmed
            pass
    """
    
    def __init__(self, parent, theme_manager):
        """
        Initialize the DialogManager.
        
        Args:
            parent: Parent widget for dialogs (typically MainWindow)
            theme_manager: ThemeManager instance for styling
        """
        self.parent = parent
        self.theme_manager = theme_manager
    
    def _create_dialog(
        self, 
        icon: QMessageBox.Icon, 
        title: str, 
        text: str, 
        buttons=QMessageBox.StandardButton.Ok,
        default_button=None
    ) -> QMessageBox:
        """
        Create a styled QMessageBox.
        
        Args:
            icon: QMessageBox.Icon type (Information, Warning, Critical, Question)
            title: Dialog window title
            text: Dialog message text
            buttons: Standard buttons to show
            default_button: Which button should be default (focused)
            
        Returns:
            Configured QMessageBox ready for .exec()
        """
        msg = QMessageBox(icon, title, text, buttons, parent=self.parent)
        
        # Enable rich text to support HTML formatting
        msg.setTextFormat(Qt.TextFormat.RichText)
        
        # Remove title bar and make frameless for custom look
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.FramelessWindowHint)
        
        # Apply theme styling with beveled corners
        styles = self.theme_manager.get_dialog_styles()
        
        # Add QMessageBox-specific styling with border-radius
        messagebox_style = """
            QMessageBox {
                background-color: """ + ("rgb(43, 43, 43)" if self.theme_manager.get_current_theme() == 'dark' else "rgb(255, 255, 255)") + """;
                border-radius: 8px;
            }
        """
        
        if styles:
            msg.setStyleSheet(styles + messagebox_style)
        else:
            msg.setStyleSheet(messagebox_style)
        
        # Set default button if specified
        if default_button:
            msg.setDefaultButton(default_button)
        else:
            # Default: focus on the first/Ok button
            ok_button = msg.button(QMessageBox.StandardButton.Ok)
            if ok_button:
                ok_button.setDefault(True)
                ok_button.setFocus()
        
        return msg
    
    def show_info(self, title: str, text: str) -> int:
        """
        Show an information dialog.
        
        Args:
            title: Dialog title
            text: Information message
            
        Returns:
            QMessageBox result code
        """
        dlg = self._create_dialog(QMessageBox.Icon.Information, title, text)
        return dlg.exec()
    
    def show_warning(self, title: str, text: str) -> int:
        """
        Show a warning dialog.
        
        Args:
            title: Dialog title
            text: Warning message
            
        Returns:
            QMessageBox result code
        """
        dlg = self._create_dialog(QMessageBox.Icon.Warning, title, text)
        return dlg.exec()
    
    def show_error(self, title: str, text: str) -> int:
        """
        Show an error/critical dialog.
        
        Args:
            title: Dialog title
            text: Error message
            
        Returns:
            QMessageBox result code
        """
        dlg = self._create_dialog(QMessageBox.Icon.Critical, title, text)
        return dlg.exec()
    
    def confirm_action(self, title: str, text: str, default_no: bool = True) -> bool:
        """
        Show a confirmation dialog with Yes/No buttons.
        
        Args:
            title: Dialog title
            text: Confirmation question
            default_no: If True, No button is default; if False, Yes is default
            
        Returns:
            True if user clicked Yes, False otherwise
        """
        default = (
            QMessageBox.StandardButton.No if default_no 
            else QMessageBox.StandardButton.Yes
        )
        dlg = self._create_dialog(
            QMessageBox.Icon.Question,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            default_button=default
        )
        return dlg.exec() == QMessageBox.StandardButton.Yes
    
    def show_conversion_summary(self, successful: int, failed: int, skipped: int, stopped: int) -> int:
        """
        Show conversion completion dialog with color-coded breakdown (unified method).
        
        This is the app-wide standard for conversion completion dialogs.
        Displays success/failed/skipped/stopped counts with appropriate color coding.
        
        Args:
            successful: Number of files converted successfully
            failed: Number of files that failed to convert
            skipped: Number of files skipped (incompatible format, etc.)
            stopped: Number of files stopped (user cancelled)
            
        Returns:
            QMessageBox result code
        """
        # App color palette
        app_green = "#4CAF50"   # Success green
        app_yellow = "#FFC107"  # Warning yellow
        app_red = "#F44336"     # Error red
        
        # Build color-coded message parts
        parts = []
        
        # Show successful (green) - always show if any
        if successful > 0:
            if successful == 1:
                parts.append(f"<span style='color: {app_green};'>1 file exported successfully</span>")
            else:
                parts.append(f"<span style='color: {app_green};'>{successful} files exported successfully</span>")
        
        # Show skipped (yellow) - only if any
        if skipped > 0:
            if skipped == 1:
                parts.append(f"<span style='color: {app_yellow};'>1 skipped</span>")
            else:
                parts.append(f"<span style='color: {app_yellow};'>{skipped} skipped</span>")
        
        # Show failed (red) - only if any
        if failed > 0:
            if failed == 1:
                parts.append(f"<span style='color: {app_red};'>1 failed</span>")
            else:
                parts.append(f"<span style='color: {app_red};'>{failed} failed</span>")
        
        # Show stopped (yellow) - only if any
        if stopped > 0:
            if stopped == 1:
                parts.append(f"<span style='color: {app_yellow};'>1 file stopped</span>")
            else:
                parts.append(f"<span style='color: {app_yellow};'>{stopped} files stopped</span>")
        
        # Join with line breaks for vertical layout
        formatted_message = "<br>".join(parts) if parts else "<span>No files processed</span>"
        
        # Determine success status and dialog title
        success = successful > 0 or (successful == 0 and failed == 0 and stopped == 0)
        icon = QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical
        title = "Conversion Complete" if success else "Conversion Error"
        
        # Create dialog without buttons
        dlg = self._create_dialog(
            icon,
            title,
            formatted_message,
            buttons=QMessageBox.StandardButton.NoButton  # No buttons
        )
        
        # Install event filter to close on click or keypress
        from PySide6.QtCore import QEvent, QObject
        
        class ClickOrKeyCloseFilter(QObject):
            def __init__(self, dialog):
                super().__init__()
                self.dialog = dialog
            
            def eventFilter(self, obj, event):
                # Close on mouse click or key press
                if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
                    self.dialog.accept()
                    return True
                return False
        
        close_filter = ClickOrKeyCloseFilter(dlg)
        dlg.installEventFilter(close_filter)
        
        return dlg.exec()
    
    def show_tool_status(self, message: str) -> int:
        """
        Show tool status check dialog.
        
        Args:
            message: Tool status message
            
        Returns:
            QMessageBox result code
        """
        return self.show_info("Tool Status", message)
    
    def show_av1_warning(self) -> None:
        """
        Show AV1 slow export warning that auto-dismisses after 15 seconds.
        
        This is a non-blocking warning that appears when the user starts
        an AV1 conversion, informing them that the export will be slow
        due to lack of GPU acceleration.
        """
        from PySide6.QtCore import QTimer
        
        dlg = self._create_dialog(
            QMessageBox.Icon.Warning,
            "Slow Export Detected",
            "Your GPU doesn't support AV1 acceleration.\nThis export will be much slower than other codecs.",
            buttons=QMessageBox.StandardButton.Ok
        )
        
        # Auto-close after 15 seconds
        auto_close_timer = QTimer()
        auto_close_timer.setSingleShot(True)
        auto_close_timer.timeout.connect(dlg.accept)
        auto_close_timer.start(15000)  # 15 seconds
        
        # Show dialog (blocks until dismissed or timer expires)
        dlg.exec()
        
        # Clean up timer
        auto_close_timer.stop()

