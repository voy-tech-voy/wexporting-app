"""
Dialog Manager for unified dialog handling.

Centralizes all QMessageBox operations with consistent styling and behavior.
This removes boilerplate from MainWindow and ensures all dialogs follow
the app's theming guidelines.
"""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt


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
    
    def show_completion(self, success: bool, message: str) -> int:
        """
        Show a conversion completion dialog.
        
        Args:
            success: True for success (info icon), False for error (critical icon)
            message: Completion message with details (may contain HTML)
            
        Returns:
            QMessageBox result code
        """
        # Parse the HTML message to extract components and reformat
        # Expected format: "<span style='color: #xxx;'>X successful</span>, <span...>Y skipped</span>"
        
        # Extract full HTML spans with their styling
        import re
        spans = re.findall(r"<span[^>]*>.*?</span>", message)
        
        if len(spans) >= 1:
            # Reorganize: success first, skipped second, failed third
            lines = []
            success_span = None
            skipped_span = None
            failed_span = None
            stopped_span = None
            
            for span in spans:
                # Check content inside span
                content = re.search(r">([^<]+)<", span)
                if content:
                    text = content.group(1).lower()
                    if 'success' in text or 'exported' in text:
                        success_span = span
                    elif 'skipped' in text:
                        skipped_span = span
                    elif 'failed' in text:
                        failed_span = span
                    elif 'stopped' in text:
                        stopped_span = span
            
            # Build formatted message with line breaks, preserving HTML
            if success_span:
                lines.append(success_span)
            if skipped_span:
                lines.append(skipped_span)
            if failed_span:
                lines.append(failed_span)
            if stopped_span:
                lines.append(stopped_span)
            
            formatted_message = "<br>".join(lines)
        else:
            # Fallback to original message if parsing fails
            formatted_message = message
        
        # Create dialog without buttons
        icon = QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical
        dlg = self._create_dialog(
            icon,
            "Conversion Complete" if success else "Conversion Error",
            formatted_message,
            buttons=QMessageBox.StandardButton.NoButton  # No buttons
        )
        
        # Install event filter to close on click or keypress
        from PyQt6.QtCore import QEvent, QObject
        
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
