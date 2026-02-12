"""
File Context Menu

Provides context menu functionality for file list items.
"""

import os
import subprocess
from typing import Callable, Optional
from PyQt6.QtWidgets import QWidget, QMenu, QListWidget, QListWidgetItem
from PyQt6.QtCore import QPoint, Qt
from client.gui.theme import Theme


def show_file_context_menu(
    parent: QWidget,
    list_widget: QListWidget,
    position: QPoint,
    theme_manager,
    on_remove: Callable[[QListWidgetItem], None],
    on_show_explorer: Callable[[QListWidgetItem], None],
    sequences_enabled: bool = True,
    on_toggle_sequences: Optional[Callable[[bool], None]] = None
) -> None:
    """
    Show context menu for file operations.
    
    Args:
        parent: Parent widget
        list_widget: The QListWidget containing the file items
        position: Position where the menu should appear
        theme_manager: ThemeManager for styling
        on_remove: Callback when "Remove File" is selected
        on_show_explorer: Callback when "Show in Explorer" is selected
        sequences_enabled: Current state of sequence grouping
        on_toggle_sequences: Callback to toggle sequence grouping
    """
    item = list_widget.itemAt(position)
    
    # Hide if placeholder
    if item and item.data(Qt.ItemDataRole.UserRole) == "PLACEHOLDER":
        return

    menu = QMenu(parent)
    
    # File-specific actions
    remove_action = None
    show_action = None
    if item:
        remove_action = menu.addAction("Remove File")
        show_action = menu.addAction("Show in Explorer")
        menu.addSeparator()
    
    # Global actions
    label = f"✅ Group sequences" if sequences_enabled else f"❌ Group sequences"
    group_action = menu.addAction(label)
    
    # Themed styling
    is_dark = theme_manager and theme_manager.current_theme == 'dark'
    Theme.set_dark_mode(is_dark)
    
    menu.setStyleSheet(f"""
        QMenu {{
            background-color: {Theme.surface_element()};
            color: {Theme.text()};
            border: 1px solid {Theme.border()};
            border-radius: {Theme.RADIUS_SM}px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: {Theme.RADIUS_SM}px;
        }}
        QMenu::item:selected {{
            background-color: #666666;
            color: white;
        }}
    """)
    
    action = menu.exec(list_widget.mapToGlobal(position))
    if action == remove_action:
        on_remove(item)
    elif action == show_action:
        on_show_explorer(item)
    elif action == group_action:
        if on_toggle_sequences:
            on_toggle_sequences(not sequences_enabled)


def show_in_explorer(file_path: str) -> None:
    """
    Open file location in Windows Explorer and select the file.
    
    Args:
        file_path: Path to the file to show
    """
    try:
        # Verify file exists
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return
        
        # Normalize path for Windows
        normalized_path = os.path.normpath(file_path)
        
        # Open Explorer and select the file in a new window
        # The /select, parameter highlights the file
        subprocess.Popen(['explorer', '/select,', normalized_path])
        print(f"Opened Explorer for: {normalized_path}")
        
    except Exception as e:
        print(f"Error opening Explorer: {e}")
        # Fallback: just open the folder
        try:
            folder_path = os.path.dirname(file_path)
            if os.path.exists(folder_path):
                subprocess.Popen(['explorer', os.path.normpath(folder_path)])
        except Exception as e2:
            print(f"Error opening folder: {e2}")
