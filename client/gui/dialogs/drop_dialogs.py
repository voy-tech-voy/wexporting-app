"""
Folder Drop Dialogs

Provides dialog functions for handling folder drops and folder selection.
"""

import os
from typing import List, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QLabel, QCheckBox, 
    QDialogButtonBox, QFileDialog, QMessageBox
)
from client.gui.theme import Theme


def apply_dialog_styling(dialog: QDialog, theme_manager) -> None:
    """
    Apply consistent rounded corner styling to dialogs.
    
    Args:
        dialog: The dialog to style
        theme_manager: ThemeManager instance for theme-aware styling
    """
    is_dark = theme_manager and theme_manager.current_theme == 'dark'
    Theme.set_dark_mode(is_dark)
    
    base_styles = theme_manager.get_dialog_styles() if theme_manager else ""
    
    rounded_style = f"""
        QDialog {{
            background-color: {Theme.surface_element()};
            border-radius: {Theme.RADIUS_LG}px;
        }}
    """
    
    dialog.setStyleSheet(base_styles + rounded_style)


def show_folder_drop_dialog(
    parent: QWidget,
    folders: List[str],
    theme_manager,
    count_files_callback: Callable[[str, bool], int],
    get_files_callback: Callable[[str, bool], List[str]]
) -> Optional[List[str]]:
    """
    Show dialog for dropped folder(s) with subfolder options.
    
    Args:
        parent: Parent widget
        folders: List of folder paths that were dropped
        theme_manager: ThemeManager for styling
        count_files_callback: Function to count supported files in a folder
        get_files_callback: Function to get supported files from a folder
        
    Returns:
        List of file paths if user accepted, None if cancelled
    """
    if len(folders) == 1:
        folder_name = os.path.basename(folders[0])
        title = f"Process Folder: {folder_name}"
    else:
        title = f"Process {len(folders)} Folders"
        
    # Create options dialog
    dialog = QDialog(parent)
    dialog.setWindowTitle("Folder Drop Options")
    dialog.setFixedSize(400, 250)
    
    apply_dialog_styling(dialog, theme_manager)
    
    layout = QVBoxLayout(dialog)
    
    if len(folders) == 1:
        layout.addWidget(QLabel(f"Dropped folder: {folder_name}"))
    else:
        layout.addWidget(QLabel(f"Dropped {len(folders)} folder(s):"))
        for folder in folders[:3]:  # Show first 3
            layout.addWidget(QLabel(f"• {os.path.basename(folder)}"))
        if len(folders) > 3:
            layout.addWidget(QLabel(f"• ... and {len(folders) - 3} more"))
            
    layout.addWidget(QLabel("\nChoose processing options:"))
    
    # Include subfolders option
    include_subfolders = QCheckBox("Include subfolders (recursive)")
    include_subfolders.setChecked(False)
    layout.addWidget(include_subfolders)
    
    # Show file count preview
    preview_label = QLabel("")
    layout.addWidget(preview_label)
    
    def update_preview():
        total_count = 0
        for folder in folders:
            total_count += count_files_callback(folder, include_subfolders.isChecked())
        preview_label.setText(f"Found {total_count} supported file(s) total")
    
    include_subfolders.toggled.connect(update_preview)
    update_preview()  # Initial count
    
    # Dialog buttons
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        all_files = []
        for folder in folders:
            folder_files = get_files_callback(folder, include_subfolders.isChecked())
            all_files.extend(folder_files)
        return all_files if all_files else []
    
    return None


def show_add_folder_dialog(
    parent: QWidget,
    theme_manager,
    count_files_callback: Callable[[str, bool], int],
    get_files_callback: Callable[[str, bool], List[str]]
) -> Optional[List[str]]:
    """
    Show folder selection dialog with subfolder options.
    
    Args:
        parent: Parent widget
        theme_manager: ThemeManager for styling
        count_files_callback: Function to count supported files in a folder
        get_files_callback: Function to get supported files from a folder
        
    Returns:
        List of file paths if user accepted, None if cancelled
    """
    folder = QFileDialog.getExistingDirectory(
        parent,
        "Select folder to process all supported files",
        ""
    )
    
    if not folder:
        return None
        
    # Create options dialog
    dialog = QDialog(parent)
    dialog.setWindowTitle("Folder Processing Options")
    dialog.setFixedSize(400, 200)
    
    apply_dialog_styling(dialog, theme_manager)
    
    layout = QVBoxLayout(dialog)
    
    layout.addWidget(QLabel(f"Selected folder: {os.path.basename(folder)}"))
    layout.addWidget(QLabel("Choose processing options:"))
    
    # Include subfolders option
    include_subfolders = QCheckBox("Include subfolders (recursive)")
    include_subfolders.setChecked(False)
    layout.addWidget(include_subfolders)
    
    # Show file count preview
    preview_label = QLabel("")
    layout.addWidget(preview_label)
    
    def update_preview():
        count = count_files_callback(folder, include_subfolders.isChecked())
        preview_label.setText(f"Found {count} supported file(s)")
    
    include_subfolders.toggled.connect(update_preview)
    update_preview()  # Initial count
    
    # Dialog buttons
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        files = get_files_callback(folder, include_subfolders.isChecked())
        return files if files else []
    
    return None
