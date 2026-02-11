"""
Drag and Drop Area Styling Utilities

Provides stylesheet generation functions for the DragDropArea widget.
Centralizes all Qt stylesheet logic for scrollbars, list items, and drag states.
"""

from client.gui.theme import Theme


def get_scrollbar_style(is_dark: bool) -> str:
    """
    Get modern minimalistic scrollbar styling with grey item selection.
    
    Args:
        is_dark: Whether dark mode is active
        
    Returns:
        Qt stylesheet string for scrollbars and list items
    """
    Theme.set_dark_mode(is_dark)
    
    # Common colors from Theme
    item_selected_bg = Theme.color("surface_hover")
    item_hover_bg = Theme.color("surface_pressed") if is_dark else Theme.color("surface_hover")
    text_color = Theme.text()
    scrollbar_bg = Theme.color("scrollbar_bg")
    scrollbar_thumb = Theme.color("scrollbar_thumb")
    scrollbar_thumb_hover = Theme.border_focus()
    
    return f"""
        QListWidget::item {{
            outline: none;
            border: none;
        }}
        QListWidget::item:selected {{
            background-color: {item_selected_bg};
            color: {text_color};
            outline: none;
            border: none;
        }}
        QListWidget::item:focus {{
            outline: none;
            border: none;
        }}
        QListWidget::item:selected:focus {{
            background-color: {item_selected_bg};
            outline: none;
            border: none;
        }}
        QListWidget::item:hover:!selected {{
            background-color: transparent;
            border-radius: {Theme.RADIUS_MD}px;
        }}
        QScrollBar:vertical {{
            background: {scrollbar_bg};
            width: 10px;
            border: none;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {scrollbar_thumb};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {scrollbar_thumb_hover};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            background: {scrollbar_bg};
            height: 10px;
            border: none;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {scrollbar_thumb};
            border-radius: 5px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {scrollbar_thumb_hover};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """


def get_list_style(is_dark: bool, bg_color: str) -> str:
    """
    Get base list widget style with dashed border.
    
    Args:
        is_dark: Whether dark mode is active
        bg_color: Background color (can be "transparent" or Theme color)
        
    Returns:
        Qt stylesheet string for the list widget
    """
    Theme.set_dark_mode(is_dark)
    
    return f"""
        QListWidget#DropZone {{
            background-color: {bg_color};
            border: 6px dashed {Theme.border()};
            border-radius: {Theme.RADIUS_LG}px;
            color: {Theme.text()};
            font-size: {Theme.FONT_SIZE_BASE}px;
            padding: 0px;
            outline: none;
        }}
        QListWidget#DropZone:hover {{
            border-color: {Theme.border_focus()};
            background-color: {bg_color};
        }}
    """


def get_placeholder_style(is_dark: bool, base_style: str) -> str:
    """
    Get placeholder-specific style overrides.
    
    Modifies base style to make placeholder transparent with dashed border.
    
    Args:
        is_dark: Whether dark mode is active
        base_style: Base stylesheet to modify
        
    Returns:
        Modified Qt stylesheet string
    """
    Theme.set_dark_mode(is_dark)
    
    # Replace ALL item styling to be transparent with no borders/padding
    modified_style = base_style.replace(
        'background-color: #3c3c3c;', 
        'background-color: transparent;'
    ).replace(
        'background-color: white;',
        'background-color: transparent;'
    ).replace(
        'border: 1px solid #444;',
        'border: none;'
    ).replace(
        'border: 1px solid #ddd;',
        'border: none;'
    ).replace(
        'margin: 2px;',
        'margin: 0px;'
    ).replace(
        'padding: 8px;',
        'padding: 0px;'
    )
    
    # Add scrollbar styling
    modified_style += get_scrollbar_style(is_dark)
    
    # Override padding and hover state to strip Theme Factory defaults
    modified_style += f"""
        QListWidget {{
            border: 6px dashed {Theme.border()};
            border-radius: {Theme.RADIUS_LG}px;
            padding: 0px;
            background-color: transparent;
        }}
        QListWidget:hover {{
            border-color: {Theme.border_focus()};
            background-color: transparent;
        }}
    """
    
    return modified_style
