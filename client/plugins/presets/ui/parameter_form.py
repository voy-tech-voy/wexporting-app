"""
Presets Plugin - Parameter Form

Dynamically generates UI widgets from preset parameter definitions.
Supports visibility rules evaluated via Jinja2.
"""
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QComboBox, QPushButton,
    QButtonGroup, QFrame, QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from client.gui.custom_widgets import ThemedCheckBox

from jinja2 import Environment, StrictUndefined

from client.plugins.presets.logic.models import ParameterDefinition, ParameterType
from client.gui.theme import Theme


class SegmentedPill(QWidget):
    """Segmented button group for multi-option selection"""
    
    value_changed = Signal(str)
    
    def __init__(self, options: List[str], default: str = None, parent=None):
        super().__init__(parent)
        self._options = options
        self._current_value = default or (options[0] if options else "")
        self._is_dark = True  # Default to dark mode
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)  # Small gap between buttons
        
        self._buttons: Dict[str, QPushButton] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        
        for i, opt in enumerate(options):
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setChecked(opt == self._current_value)
            btn.clicked.connect(lambda checked, o=opt: self._on_button_clicked(o))
            
            # Styling - ensure buttons are not cut off
            btn.setMinimumWidth(70)
            btn.setMinimumHeight(36)
            btn.setSizePolicy(btn.sizePolicy().horizontalPolicy(), btn.sizePolicy().verticalPolicy())
            
            self._buttons[opt] = btn
            self._button_group.addButton(btn, i)
            layout.addWidget(btn)
        
        self._apply_styles()
    
    def _on_button_clicked(self, option: str):
        self._current_value = option
        self.value_changed.emit(option)
        self._apply_styles()
    
    def _apply_styles(self):
        """Apply theme-aware styles to buttons."""
        for opt, btn in self._buttons.items():
            if opt == self._current_value:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Theme.success()};
                        color: white;
                        border: none;
                        font-weight: bold;
                        font-size: {Theme.FONT_SIZE_LG}px;
                        border-radius: {Theme.RADIUS_MD}px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Theme.param_bg()};
                        color: {Theme.text_muted()};
                        border: 1px solid {Theme.border()};
                        font-size: {Theme.FONT_SIZE_LG}px;
                        border-radius: {Theme.RADIUS_MD}px;
                    }}
                    QPushButton:hover {{
                        background-color: {Theme.color('surface_hover')};
                        color: {Theme.text()};
                        border: 1px solid {Theme.border_focus()};
                    }}
                """)
    
    def update_theme(self, is_dark: bool):
        """Update styles when theme changes."""
        self._is_dark = is_dark
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
    
    def value(self) -> str:
        return self._current_value
    
    def setValue(self, val: str):
        if val in self._buttons:
            self._current_value = val
            self._buttons[val].setChecked(True)
            self._apply_styles()


class ParameterForm(QWidget):
    """
    Dynamic form that renders preset parameters as Qt widgets.
    
    Supports:
    - toggle → QCheckBox
    - slider → QSlider + QLabel
    - segmented_pill → SegmentedPill
    - dropdown → QComboBox
    
    Visibility rules are evaluated via Jinja2 expressions.
    """
    
    values_changed = Signal(dict)  # Emits current param values
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parameters: List[ParameterDefinition] = []
        self._meta: Dict[str, Any] = {}
        self._widgets: Dict[str, QWidget] = {}
        self._containers: Dict[str, QWidget] = {}  # For visibility control
        self._jinja_env = Environment(undefined=StrictUndefined)
        self._is_dark = True  # Default to dark mode
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 20)  # Bottom padding prevents last param being clipped in scroll area
        self._layout.setSpacing(12)  # Consistent spacing between parameters
        
        self._apply_styles()
    
    def _apply_styles(self):
        """Apply theme-aware styles."""
        self.setStyleSheet(f"""
            QLabel {{ 
                color: {Theme.text()}; 
                font-size: {Theme.FONT_SIZE_LG}px;
                font-family: '{Theme.FONT_BODY}';
            }}
        """)
    
    def set_parameters(self, params: List[ParameterDefinition], meta: Dict[str, Any] = None):
        """
        Build the form from parameter definitions.
        
        Args:
            params: List of ParameterDefinition from preset
            meta: Media metadata for visibility rule evaluation
        """
        self._parameters = params
        self._meta = meta or {}
        self._clear_form()
        
        for param in params:
            container = self._create_parameter_widget(param)
            self._containers[param.id] = container
            self._layout.addWidget(container)
        
        # Spacer
        self._layout.addStretch()
        
        # Initial visibility evaluation
        self._update_visibility()
    
    def _clear_form(self):
        """Remove all widgets from the form."""
        self._widgets.clear()
        self._containers.clear()
        
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _create_parameter_widget(self, param: ParameterDefinition) -> QWidget:
        """Create a widget container for a parameter with horizontal layout."""
        container = QFrame()
        container.setObjectName(f"param_{param.id}")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 6, 0, 6)  # Consistent vertical padding per row
        layout.setSpacing(12)
        
        # Create label (always shown, positioned first)
        label = QLabel(param.label)
        label.setStyleSheet("font-weight: bold;")
        label.setMinimumWidth(140)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if param.tooltip:
            label.setToolTip(param.tooltip)
        
        layout.addWidget(label)
        
        # Widget based on type
        widget = None
        
        if param.type == ParameterType.TOGGLE:
            # For toggles: swap order - checkbox first, then label
            # Remove the label from the main layout and add toggle first
            layout.removeWidget(label)
            
            # Update label for toggle (left-aligned relative to checkbox)
            # Reset min width since it's now a suffix
            label.setMinimumWidth(0)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.setContentsMargins(8, 0, 0, 0)  # Add left padding
            
            # Use ThemedCheckBox without text (label is separate)
            widget = ThemedCheckBox("")
            widget.setChecked(bool(param.default))
            if param.tooltip:
                widget.setToolTip(param.tooltip)
            widget.toggled.connect(lambda: self._on_value_changed())
            
            # Make label clickable to toggle checkbox
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.mousePressEvent = lambda event: widget.toggle()
            
            # Add toggle first, then label, then stretch to push left
            layout.insertWidget(0, widget)
            layout.addWidget(label)
            layout.addStretch()
            # Don't add widget again at the end
            
        elif param.type == ParameterType.MULTI_TOGGLE:
            # Multiple checkboxes for multi-select (e.g., icon sizes: 16, 32, 48, 256)
            multi_container = QWidget()
            multi_layout = QHBoxLayout(multi_container)
            multi_layout.setContentsMargins(0, 0, 0, 0)
            multi_layout.setSpacing(12)
            
            # Store checkboxes for value retrieval
            checkboxes = {}
            default_values = param.default if isinstance(param.default, list) else []
            
            for option in param.options:
                cb = ThemedCheckBox(option)
                cb.setChecked(option in default_values)
                cb.toggled.connect(lambda: self._on_value_changed())
                checkboxes[option] = cb
                multi_layout.addWidget(cb)
            
            multi_layout.addStretch()
            widget = multi_container
            widget._checkboxes = checkboxes  # Store for value retrieval
            
        elif param.type == ParameterType.SLIDER:
            # Create horizontal slider with value label
            slider_container = QWidget()
            slider_layout = QHBoxLayout(slider_container)
            slider_layout.setContentsMargins(0, 0, 0, 0)
            slider_layout.setSpacing(8)
            
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(int(param.min_value or 0))
            slider.setMaximum(int(param.max_value or 100))
            slider.setValue(int(param.default or 50))
            
            value_label = QLabel(str(slider.value()))
            value_label.setMinimumWidth(40)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
            slider.valueChanged.connect(lambda: self._on_value_changed())
            
            slider_layout.addWidget(slider, 1)
            slider_layout.addWidget(value_label)
            
            widget = slider_container
            # Store slider for value retrieval
            widget._slider = slider
            
        elif param.type == ParameterType.SEGMENTED_PILL:
            widget = SegmentedPill(param.options, str(param.default))
            widget.setMinimumHeight(40)  # Ensure buttons aren't cut off
            widget.value_changed.connect(lambda: self._on_value_changed())
            
        elif param.type == ParameterType.TEXT:
            widget = QLineEdit()
            widget.setPlaceholderText(param.tooltip or "Enter text...")
            if param.default:
                widget.setText(str(param.default))
            widget.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Theme.param_bg()};
                    color: {Theme.text()};
                    border: 1px solid {Theme.color('border_dim')};
                    border-radius: {Theme.RADIUS_MD}px;
                    padding: 8px 12px;
                    font-size: {Theme.FONT_SIZE_LG}px;
                }}
                QLineEdit:focus {{
                    border: 1px solid {Theme.border_focus()};
                }}
            """)
            widget.textChanged.connect(lambda: self._on_value_changed())

        elif param.type == ParameterType.DROPDOWN:
            widget = QComboBox()
            widget.addItems(param.options)
            if param.default in param.options:
                widget.setCurrentText(str(param.default))

            # Apply theme-aware styling
            widget.setStyleSheet(f"""
                QComboBox {{
                    background-color: {Theme.param_bg()};
                    color: {Theme.text()};
                    border: 1px solid {Theme.color('border_dim')};
                    border-radius: {Theme.RADIUS_MD}px;
                    padding: 8px 12px;
                    font-size: {Theme.FONT_SIZE_LG}px;
                }}
                QComboBox:hover {{
                    border: 1px solid {Theme.color('border_focus')};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 24px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 2px solid {Theme.color('text_secondary')};
                    border-bottom: 2px solid {Theme.color('text_secondary')};
                    width: 8px;
                    height: 8px;
                    margin-right: 8px;
                    transform: rotate(-45deg);
                }}
                QComboBox QAbstractItemView {{
                    background-color: {Theme.param_bg()};
                    selection-background-color: {Theme.color('accent_primary')};
                    selection-color: {Theme.bg()};
                    border: 1px solid {Theme.color('border_dim')};
                    outline: none;
                }}
            """)
            widget.currentTextChanged.connect(lambda: self._on_value_changed())

        elif param.type == ParameterType.FILE_INPUT:
            file_container = QWidget()
            file_layout = QHBoxLayout(file_container)
            file_layout.setContentsMargins(0, 0, 0, 0)
            file_layout.setSpacing(8)

            line_edit = QLineEdit()
            line_edit.setReadOnly(True)
            line_edit.setPlaceholderText("No file selected...")
            if param.default:
                line_edit.setText(str(param.default))
            line_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Theme.param_bg()};
                    color: {Theme.text()};
                    border: 1px solid {Theme.color('border_dim')};
                    border-radius: {Theme.RADIUS_MD}px;
                    padding: 8px 12px;
                    font-size: {Theme.FONT_SIZE_LG}px;
                }}
            """)

            browse_btn = QPushButton("Browse")
            browse_btn.setMinimumWidth(80)
            browse_btn.setMinimumHeight(36)
            browse_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.success()};
                    color: white;
                    border: none;
                    font-weight: bold;
                    font-size: {Theme.FONT_SIZE_LG}px;
                    border-radius: {Theme.RADIUS_MD}px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.color('surface_hover')};
                    color: {Theme.text()};
                }}
            """)

            # Build file filter from options (extensions list)
            if param.options:
                ext_list = " ".join(f"*{ext}" for ext in param.options)
                file_filter = f"Images ({ext_list});;All Files (*)"
            else:
                file_filter = "All Files (*)"

            def on_browse(checked=False, le=line_edit, ff=file_filter):
                path, _ = QFileDialog.getOpenFileName(self, "Select File", "", ff)
                if path:
                    le.setText(path)
                    self._on_value_changed()

            browse_btn.clicked.connect(on_browse)

            file_layout.addWidget(line_edit, 1)
            file_layout.addWidget(browse_btn)

            widget = file_container
            widget._line_edit = line_edit

        if widget:
            # For toggles, widget is already added in special order
            if param.type != ParameterType.TOGGLE:
                layout.addWidget(widget, 1)  # Stretch factor 1 for input
            self._widgets[param.id] = widget
        
        return container
    
    def _on_value_changed(self):
        """Handle any parameter value change."""
        self._update_visibility()
        self.values_changed.emit(self.get_values())
    
    def _update_visibility(self):
        """Evaluate visibility rules for all parameters."""
        current_values = self.get_values()
        context = {**current_values, 'meta': self._meta}
        
        for param in self._parameters:
            if param.visibility_rule and param.id in self._containers:
                visible = self._evaluate_visibility_rule(param.visibility_rule, context)
                self._containers[param.id].setVisible(visible)
    
    def _evaluate_visibility_rule(self, rule: str, context: Dict) -> bool:
        """
        Evaluate a visibility rule using Jinja2.
        
        Args:
            rule: Jinja2 boolean expression (e.g., "not (allow_rotate and meta.is_landscape)")
            context: Variables for evaluation
        """
        try:
            template_str = f"{{% if {rule} %}}1{{% else %}}0{{% endif %}}"
            template = self._jinja_env.from_string(template_str)
            result = template.render(context)
            return result.strip() == "1"
        except Exception as e:
            print(f"[ParameterForm] Visibility rule error: {e}")
            return True  # Default to visible on error
    
    def get_values(self) -> Dict[str, Any]:
        """Get current values of all parameters."""
        values = {}
        
        for param in self._parameters:
            widget = self._widgets.get(param.id)
            if not widget:
                values[param.id] = param.default
                continue
            
            if param.type == ParameterType.TOGGLE:
                values[param.id] = widget.isChecked()
            elif param.type == ParameterType.MULTI_TOGGLE:
                # Return comma-separated list of selected options
                if hasattr(widget, '_checkboxes'):
                    selected = [opt for opt, cb in widget._checkboxes.items() if cb.isChecked()]
                    values[param.id] = ','.join(selected)
                else:
                    values[param.id] = param.default
            elif param.type == ParameterType.SLIDER:
                values[param.id] = widget._slider.value() if hasattr(widget, '_slider') else param.default
            elif param.type == ParameterType.SEGMENTED_PILL:
                values[param.id] = widget.value()
            elif param.type == ParameterType.DROPDOWN:
                values[param.id] = widget.currentText()
            elif param.type == ParameterType.TEXT:
                values[param.id] = widget.text() if isinstance(widget, QLineEdit) else param.default
            elif param.type == ParameterType.FILE_INPUT:
                values[param.id] = widget._line_edit.text() if hasattr(widget, '_line_edit') else param.default
            else:
                values[param.id] = param.default
        
        return values
    
    def set_values(self, values: Dict[str, Any]):
        """Restore parameter values into existing widgets (used to persist values across form rebuilds)."""
        for param in self._parameters:
            widget = self._widgets.get(param.id)
            if not widget or param.id not in values:
                continue
            val = values[param.id]
            if param.type == ParameterType.TOGGLE:
                widget.setChecked(bool(val))
            elif param.type == ParameterType.MULTI_TOGGLE:
                if hasattr(widget, '_checkboxes'):
                    selected = val.split(',') if isinstance(val, str) else (val or [])
                    for opt, cb in widget._checkboxes.items():
                        cb.setChecked(opt in selected)
            elif param.type == ParameterType.SLIDER:
                if hasattr(widget, '_slider'):
                    widget._slider.setValue(int(val))
            elif param.type == ParameterType.SEGMENTED_PILL:
                widget.setValue(str(val))
            elif param.type == ParameterType.DROPDOWN:
                widget.setCurrentText(str(val))
            elif param.type == ParameterType.TEXT:
                if isinstance(widget, QLineEdit):
                    widget.setText(str(val))
            elif param.type == ParameterType.FILE_INPUT:
                if hasattr(widget, '_line_edit'):
                    widget._line_edit.setText(str(val))

    def set_meta(self, meta: Dict[str, Any]):
        """Update meta context and re-evaluate visibility."""
        self._meta = meta
        self._update_visibility()
    
    def update_theme(self, is_dark: bool):
        """Update theme for all widgets."""
        self._is_dark = is_dark
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
        
        # Update all child widgets
        for widget in self._widgets.values():
            if hasattr(widget, 'update_theme'):
                widget.update_theme(is_dark)
            elif isinstance(widget, QComboBox):
                # Re-apply theme-aware styling for dropdowns
                widget.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {Theme.param_bg()};
                        color: {Theme.text()};
                        border: 1px solid {Theme.color('border_dim')};
                        border-radius: {Theme.RADIUS_MD}px;
                        padding: 8px 12px;
                        font-size: {Theme.FONT_SIZE_LG}px;
                    }}
                    QComboBox:hover {{
                        border: 1px solid {Theme.color('border_focus')};
                    }}
                    QComboBox::drop-down {{
                        border: none;
                        width: 24px;
                    }}
                    QComboBox::down-arrow {{
                        image: none;
                        border-left: 2px solid {Theme.color('text_secondary')};
                        border-bottom: 2px solid {Theme.color('text_secondary')};
                        width: 8px;
                        height: 8px;
                        margin-right: 8px;
                        transform: rotate(-45deg);
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {Theme.param_bg()};
                        selection-background-color: {Theme.color('accent_primary')};
                        selection-color: {Theme.bg()};
                        border: 1px solid {Theme.color('border_dim')};
                        outline: none;
                    }}
                """)
