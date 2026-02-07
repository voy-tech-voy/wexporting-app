"""
Style Factory - QSS Generation Engine
Decouples presentation (QSS) from logic (Python).

This factory is responsible for generating all QSS stylesheets
using the Theme class as the single source of truth.
"""

from client.gui.theme import Theme


class StyleFactory:
    """
    Factory class for generating QSS stylesheets.
    
    All methods are static and use the Theme class for token resolution.
    This ensures consistent styling across the application.
    """
    
    @staticmethod
    def get_drag_drop_styles() -> dict:
        """
        Get drag and drop area styles for current theme.
        
        Returns:
            dict: Dictionary with 'normal' and 'drag_over' QSS strings
        """
        return {
            'normal': f"""
                QListWidget {{
                    border: 3px dashed {Theme.border()};
                    border-radius: {Theme.RADIUS_LG}px;
                    background-color: {Theme.surface_drop_area()};
                    color: {Theme.text_muted()};
                    font-size: {Theme.FONT_SIZE_BASE}px;
                    padding: 10px;
                    font-family: '{Theme.FONT_MONO}';
                }}
                QListWidget:hover {{
                    border-color: {Theme.success()};
                    background-color: {Theme.color('surface_hover')};
                }}
                QListWidget::item {{
                    padding: 8px;
                    margin: 2px;
                    border: 1px solid {Theme.border()};
                    border-radius: 5px;
                    background-color: {Theme.surface_drop_area()};
                    color: {Theme.text()};
                }}
                QListWidget::item:selected {{
                    background-color: {Theme.color('info')};
                    border-color: {Theme.color('info')};
                }}
                QListWidget::item:hover {{
                    background-color: {Theme.color('surface_hover')};
                }}
            """,
            'drag_over': f"""
                QListWidget {{
                    border: 4px dashed rgba(255, 128, 0, 0.8);        /* ORANGE - Drag Border */
                    border-radius: {Theme.RADIUS_LG}px;
                    background-color: rgba(0, 255, 255, 0.3);         /* CYAN - Drag BG */
                    color: {Theme.success()};
                    font-size: {Theme.FONT_SIZE_BASE}px;
                    padding: 10px;
                    font-family: '{Theme.FONT_MONO}';
                }}
                QListWidget::item {{
                    padding: 8px;
                    margin: 2px;
                    border: 1px solid {Theme.border()};
                    border-radius: 5px;
                    background-color: {Theme.surface_drop_area()};
                    color: {Theme.text()};
                }}
                QListWidget::item:selected {{
                    background-color: {Theme.color('info')};
                    border-color: {Theme.color('info')};
                }}
                QListWidget::item:hover {{
                    background-color: {Theme.color('surface_hover')};
                }}
            """
        }
    
    @staticmethod
    def get_main_window_style() -> str:
        """
        Get main window stylesheet for current theme.
        
        Uses Theme class for all colors, fonts, and metrics.
        
        Returns:
            str: Complete QSS stylesheet for main window
        """
        return f"""
            QMainWindow {{
                background-color: transparent;
                color: {Theme.text()};
                font-family: '{Theme.FONT_BODY}';
            }}
            QFrame#RootFrame {{
                background-color: {Theme.bg()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QFrame#ContentFrame {{
                background-color: {Theme.bg()};
                border-radius: 0px;
                border-bottom-left-radius: {Theme.RADIUS_LG}px;
                border-bottom-right-radius: {Theme.RADIUS_LG}px;
            }}
            QMenuBar {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border-bottom: 1px solid {Theme.border()};
                font-family: '{Theme.FONT_BODY}';
                padding: 4px;
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 4px 8px;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QMenuBar::item:selected {{
                background-color: {Theme.success()};
                color: white;
            }}
            QMenuBar::item:pressed {{
                background-color: {Theme.success()};
            }}
            QMenu {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                margin: 1px;
            }}
            QMenu::item:selected {{
                background-color: {Theme.success()};
            }}
            QToolBar {{
                background-color: {Theme.surface_element()};
                border: none;
                border-bottom: 1px solid {Theme.border()};
                spacing: 3px;
                padding: 4px;
            }}
            QToolBar::separator {{
                background-color: {Theme.border()};
                width: 1px;
                margin: 0 4px;
            }}
            QPushButton {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-family: '{Theme.FONT_BODY}';
                font-size: {Theme.FONT_SIZE_BASE - 1}px;
            }}
            QPushButton:hover {{
                background-color: {Theme.color('surface_hover')};
                border-color: {Theme.success()};
            }}
            QPushButton:pressed {{
                background-color: {Theme.color('surface_pressed')};
                border-color: {Theme.success()};
            }}
            QPushButton:disabled {{
                background-color: {Theme.bg()};
                color: {Theme.text_muted()};
                border-color: {Theme.border()};
            }}
            QGroupBox {{
                background-color: {Theme.surface()};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
                margin: 0px;
                padding: 0px;
                color: {Theme.text()};
                font-weight: bold;
            }}
            QGroupBox::title {{
                padding: 0px;
                margin: 0px;
            }}
            QTabWidget::pane {{
                border: 1px solid {Theme.border()};
                background-color: {Theme.surface_element()};
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: {Theme.surface()};
                color: {Theme.text_muted()};
                padding: 8px 16px;
                border: 1px solid {Theme.border()};
                border-bottom: none;
                border-radius: 5px 5px 0 0;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border-color: {Theme.success()};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {Theme.color('surface_hover')};
            }}
            QComboBox {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 5px 10px;
                font-family: '{Theme.FONT_BODY}';
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {Theme.success()};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                selection-background-color: {Theme.success()};
            }}
            QSpinBox, QDoubleSpinBox {{
                background-color: {Theme.color('input_bg')};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 4px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QSpinBox:hover, QDoubleSpinBox:hover {{
                border-color: {Theme.success()};
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {Theme.accent()};
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                border: none;
                background-color: {Theme.surface_element()};
                width: 16px;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                border: none;
                background-color: {Theme.surface_element()};
                width: 16px;
            }}
            QSlider::groove:horizontal {{
                background-color: {Theme.border()};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background-color: {Theme.success()};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {Theme.accent()};
            }}
            QProgressBar {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                text-align: center;
                font-family: '{Theme.FONT_BODY}';
            }}
            QProgressBar::chunk {{
                background-color: {Theme.success()};
                border-radius: {Theme.RADIUS_XS}px;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {Theme.color('scrollbar_bg')};
                width: 8px;
                border: none;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.color('scrollbar_thumb')};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Theme.border_focus()};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background: {Theme.color('scrollbar_bg')};
                height: 8px;
                border: none;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {Theme.color('scrollbar_thumb')};
                border-radius: 4px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {Theme.border_focus()};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            QCheckBox {{
                color: {Theme.text()};
                spacing: 5px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                background-color: {Theme.surface_element()};
                border: 1px solid {Theme.border()};
                border-radius: 3px;
            }}
            QCheckBox::indicator:hover {{
                border-color: {Theme.success()};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Theme.success()};
                border-color: {Theme.success()};
            }}
            QLabel {{
                color: {Theme.text()};
                font-family: '{Theme.FONT_BODY}';
            }}
            QSplitter::handle {{
                background-color: {Theme.border()};
                border: 1px solid {Theme.border_focus()};
                width: 4px;
                height: 4px;
                border-radius: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {Theme.border_focus()};
            }}
        """
    
    @staticmethod
    def get_dialog_styles() -> str:
        """
        Generate dialog-specific styling based on current theme.
        
        Returns:
            str: Complete QSS stylesheet for dialogs
        """
        return f"""
            QDialog {{
                background-color: {Theme.surface()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                font-family: '{Theme.FONT_BODY}';
            }}
            QLabel {{
                color: {Theme.text()};
                background-color: transparent;
                font-size: {Theme.FONT_SIZE_SM}pt;
                font-family: '{Theme.FONT_BODY}';
            }}
            QCheckBox {{
                color: {Theme.text()};
                background-color: transparent;
                spacing: 8px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QCheckBox::indicator {{
                width: 32px;
                height: 18px;
                border-radius: 9px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {Theme.border()};
                border: 1px solid {Theme.border()};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Theme.success()};
                border: 1px solid {Theme.success()};
            }}
            QCheckBox::indicator:unchecked:hover {{
                border: 1px solid {Theme.border_focus()};
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {Theme.color_with_alpha('accent_success', 0.8)};
            }}
            QRadioButton {{
                color: {Theme.text()};
                background-color: transparent;
                spacing: 8px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QRadioButton::indicator {{
                width: 32px;
                height: 18px;
                border-radius: 9px;
            }}
            QRadioButton::indicator:unchecked {{
                background-color: {Theme.border()};
                border: 1px solid {Theme.border()};
            }}
            QRadioButton::indicator:checked {{
                background-color: {Theme.success()};
                border: 1px solid {Theme.success()};
            }}
            QRadioButton::indicator:unchecked:hover {{
                border: 1px solid {Theme.border_focus()};
            }}
            QRadioButton::indicator:checked:hover {{
                background-color: {Theme.color_with_alpha('accent_success', 0.8)};
            }}
            QDialogButtonBox {{
                background-color: transparent;
            }}
            QPushButton {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 6px 16px;
                font-size: 10pt;
                min-width: 80px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QPushButton:hover {{
                background-color: {Theme.color('surface_hover')};
                border: 1px solid {Theme.border_focus()};
            }}
            QPushButton:pressed {{
                background-color: {Theme.color('surface_pressed')};
            }}
        """

