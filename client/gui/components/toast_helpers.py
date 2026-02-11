"""
Toast Notification Helpers

Factory functions for creating common toast notifications in the drag-drop area.
"""

from typing import Optional
from PyQt6.QtWidgets import QWidget
from client.gui.components.toast_notification import ToastNotification
from client.gui.theme import Theme


def dismiss_active_toast(parent: QWidget) -> None:
    """
    Dismiss the currently active toast if it exists.
    
    Args:
        parent: Parent widget that has _active_toast attribute
    """
    if hasattr(parent, '_active_toast') and parent._active_toast:
        try:
            parent._active_toast.deleteLater()
        except RuntimeError:
            pass


def show_insufficient_energy_toast(parent: QWidget) -> ToastNotification:
    """
    Show a large, centered toast for insufficient energy.
    
    Args:
        parent: Parent widget
        
    Returns:
        The created ToastNotification instance
    """
    dismiss_active_toast(parent)
    
    message = """<b>Not enough energy</b><br>Please wait until your energy is restored.
    <br> Your energy will be restored the next day (after midnight)."""
    
    toast = ToastNotification(
        message=message,
        icon_type="warning",
        duration=4000,
        parent=parent,
        position="center",
        size="large"
    )
    toast.dismissed.connect(lambda: setattr(parent, '_active_toast', None))
    toast.show_toast()
    
    parent._active_toast = toast
    return toast


def show_unsupported_files_toast(parent: QWidget, count: int) -> ToastNotification:
    """
    Show a toast notification for unsupported files.
    
    Args:
        parent: Parent widget
        count: Number of unsupported files
        
    Returns:
        The created ToastNotification instance
    """
    dismiss_active_toast(parent)
    
    message = f"{count} unsupported file(s) skipped"
    
    toast = ToastNotification(
        message=message,
        icon_type="warning",
        duration=4000,
        parent=parent
    )
    toast.dismissed.connect(lambda: setattr(parent, '_active_toast', None))
    toast.show_toast()
    
    parent._active_toast = toast
    return toast


def show_conversion_toast(
    parent: QWidget,
    successful: int,
    failed: int,
    skipped: int,
    stopped: int
) -> ToastNotification:
    """
    Show conversion results in a toast notification with color-coded details.
    
    Args:
        parent: Parent widget
        successful: Number of successful conversions
        failed: Number of failed conversions
        skipped: Number of skipped files
        stopped: Number of stopped conversions
        
    Returns:
        The created ToastNotification instance
    """
    dismiss_active_toast(parent)
    
    # Colors matching the app theme
    app_green = Theme.success()
    app_yellow = Theme.warning()
    app_red = Theme.error()
    
    parts = []
    if successful > 0:
        parts.append(f"<span style='color: {app_green};'><b>{successful}</b> exported</span>")
    
    if skipped > 0:
        parts.append(f"<span style='color: {app_yellow};'><b>{skipped}</b> skipped</span>")
        
    if failed > 0:
        parts.append(f"<span style='color: {app_red};'><b>{failed}</b> failed</span>")
        
    if stopped > 0:
        parts.append(f"<span style='color: {app_yellow};'><b>{stopped}</b> stopped</span>")
        
    if not parts:
        parts.append("No files processed")
        
    message = "<br>".join(parts)
    
    # Determine icon type
    if failed > 0:
        icon = "error"
    elif stopped > 0 or skipped > 0:
        icon = "warning"
    else:
        icon = "info"
    
    toast = ToastNotification(
        message=message,
        icon_type=icon,
        duration=5000,
        parent=parent,
        position="bottom-right"
    )
    toast.dismissed.connect(lambda: setattr(parent, '_active_toast', None))
    toast.show_toast()
    
    parent._active_toast = toast
    return toast
