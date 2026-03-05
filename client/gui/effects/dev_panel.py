"""
Dev Panel - Live Parameter Tuning UI
=====================================
A floating panel that allows interactive editing of object attributes.
Useful for tuning visual effects without restarting the app.

Usage:
    from client.gui.effects.dev_panel import DevPanel
    
    # Create panel for any object with numeric attributes
    panel = DevPanel(
        target=my_glow_overlay,
        params={
            'BLOB_RADIUS': (10, 100, 1),      # (min, max, step)
            'BLOB_OPACITY_CENTER': (0, 255, 1),
            'GLOW_RADIUS': (10, 150, 5),
        },
        title="Glow Tuning"
    )
    panel.show()
"""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox,
    QScrollArea, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
import re
import os

class DevPanel(QWidget):
    """
    Floating panel for live parameter tuning.
    Supports multiple sections for different targets.
    """
    
    def __init__(self, title: str = "Dev Panel", parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(title)
        self._sections = [] # List of section data
        
        # Dark Theme
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QGroupBox { 
                border: 1px solid #3d3d3d; 
                margin-top: 6px; 
                padding-top: 10px; 
                font-weight: bold; 
                border-radius: 4px;
                background: #252526;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #858585; }
            QSlider::groove:horizontal { height: 4px; background: #3d3d3d; border-radius: 2px; }
            QSlider::handle:horizontal { background: #007acc; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::handle:horizontal:hover { background: #1f8ad2; }
            QSpinBox, QDoubleSpinBox { 
                background: #3c3c3c; 
                border: 1px solid #3d3d3d; 
                padding: 4px; 
                border-radius: 2px;
                color: #cccccc;
                selection-background-color: #264f78;
            }
            QPushButton { 
                background: #3c3c3c; 
                border: 1px solid #3d3d3d; 
                padding: 6px 12px; 
                border-radius: 2px;
                color: #cccccc;
            }
            QPushButton:hover { background: #4d4d4d; }
            QPushButton:pressed { background: #007acc; color: white; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #1e1e1e; width: 12px; }
            QScrollBar::handle:vertical { background: #424242; min-height: 20px; border-radius: 6px; }
        """)
        
        self._setup_ui()
        self.setMinimumWidth(380)
        self.setMaximumHeight(800)
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(15) # Spacing between sections
        
        self._container_layout.addStretch()
        scroll.setWidget(self._container)
        layout.addWidget(scroll)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        
        print_btn = QPushButton("Print Values")
        print_btn.clicked.connect(self._print_values)
        btn_layout.addWidget(print_btn)
        
        save_btn = QPushButton("Save All Changes")
        save_btn.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold;")
        save_btn.clicked.connect(self._save_to_code)
        btn_layout.addWidget(save_btn)
            
        layout.addLayout(btn_layout)
        
        reset_btn = QPushButton("Reset All")
        reset_btn.setStyleSheet("background-color: #3c3c3c; border-color: #d73a49; color: #d73a49;")
        reset_btn.clicked.connect(self._reset_all)
        layout.addWidget(reset_btn)

    def add_section(self, target, params: dict, title: str, source_file=None, on_change=None):
        """Add a new section of parameters to the panel"""
        section = {
            'target': target,
            'params': params,
            'source_file': source_file,
            'on_change': on_change,
            'widgets': {},
            'initial_values': {}
        }
        
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        
        for attr_name, bounds in params.items():
            row = self._create_param_row(section, attr_name, bounds)
            group_layout.addWidget(row)
            
        # Insert before the stretch
        count = self._container_layout.count()
        self._container_layout.insertWidget(count - 1, group)
        
        self._sections.append(section)
        
    def _create_param_row(self, section, attr_name: str, bounds: tuple) -> QWidget:
        target = section['target']
        
        # Check for Options (List/Tuple of strings)
        # Format: (['Option1', 'Option2'],)
        is_options = isinstance(bounds[0], (list, tuple)) and isinstance(bounds[0][0], str)
        
        if is_options:
            options = bounds[0]
            current = getattr(target, attr_name, options[0])
            # Ensure current is string for combo
            current_str = str(current)
            section['initial_values'][attr_name] = current_str
            
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            label = QLabel(attr_name)
            label.setFixedWidth(140)
            
            from PySide6.QtWidgets import QComboBox
            combo = QComboBox()
            combo.addItems(options)
            if current_str in options:
                combo.setCurrentText(current_str)
            
            # Use default args to capture values (avoid closure late-binding issue)
            def on_combo_change(text, sec=section, attr=attr_name):
                self._apply_value(sec, attr, text)
                
            combo.currentTextChanged.connect(on_combo_change)
            
            row_layout.addWidget(label)
            row_layout.addWidget(combo)
            
            section['widgets'][attr_name] = combo
            return row_widget

        # Numeric Slider Logic
        if len(bounds) == 3:
            min_val, max_val, step = bounds
            is_float = isinstance(step, float) or isinstance(min_val, float)
        else:
            min_val, max_val, step, is_float = bounds
        
        current = getattr(target, attr_name, min_val)
        section['initial_values'][attr_name] = current
        
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(attr_name)
        label.setFixedWidth(140)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        if is_float:
            slider.setMinimum(int(min_val * 100))
            slider.setMaximum(int(max_val * 100))
            slider.setValue(int(current * 100))
            slider.setSingleStep(int(step * 100))
        else:
            slider.setMinimum(int(min_val))
            slider.setMaximum(int(max_val))
            slider.setValue(int(current))
            slider.setSingleStep(int(step))
        
        if is_float:
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(2)
            spinbox.setMinimum(min_val)
            spinbox.setMaximum(max_val)
            spinbox.setSingleStep(step)
            spinbox.setValue(current)
        else:
            spinbox = QSpinBox()
            spinbox.setMinimum(int(min_val))
            spinbox.setMaximum(int(max_val))
            spinbox.setSingleStep(int(step))
            spinbox.setValue(int(current))
        spinbox.setFixedWidth(70)
        
        # Use default args to capture values (avoid closure late-binding issue)
        def on_slider_change(val, sec=section, attr=attr_name, flt=is_float, spin=spinbox):
            actual = val / 100.0 if flt else val
            spin.blockSignals(True)
            spin.setValue(actual)
            spin.blockSignals(False)
            self._apply_value(sec, attr, actual)
            
        def on_spinbox_change(val, sec=section, attr=attr_name, flt=is_float, sldr=slider):
            sldr.blockSignals(True)
            sldr.setValue(int(val * 100) if flt else int(val))
            sldr.blockSignals(False)
            self._apply_value(sec, attr, val)
        
        slider.valueChanged.connect(on_slider_change)
        spinbox.valueChanged.connect(on_spinbox_change)
        
        row_layout.addWidget(label)
        row_layout.addWidget(slider)
        row_layout.addWidget(spinbox)
        
        section['widgets'][attr_name] = (slider, spinbox, is_float)
        return row_widget
    
    def _apply_value(self, section, attr_name: str, value):
        setattr(section['target'], attr_name, value)
        if section['on_change']: section['on_change']()
        if hasattr(section['target'], 'update'): section['target'].update()
            
    def _reset_all(self):
        """Reset all widgets to initial values"""
        from PySide6.QtWidgets import QComboBox
        for section in self._sections:
            for attr_name, initial in section['initial_values'].items():
                widget_data = section['widgets'][attr_name]
                # Check if it's a combo box (stored as single widget) or slider/spinbox tuple
                if isinstance(widget_data, QComboBox):
                    widget_data.setCurrentText(str(initial))
                else:
                    # Tuple of (slider, spinbox, is_float)
                    slider, spinbox, is_float = widget_data
                    spinbox.setValue(initial)
            
    def _print_values(self):
        print("\n# Current Dev Panel Values:")
        for section in self._sections:
            print(f"# Target: {section['target']}")
            for attr_name in section['params']:
                val = getattr(section['target'], attr_name)
                print(f"    {attr_name} = {val}")
        print()
        
    def _save_to_code(self):
        """Update source code files"""
        total_updates = 0
        
        for section in self._sections:
            source_file = section['source_file']
            if not source_file or not os.path.exists(source_file):
                continue
                
            try:
                with open(source_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                updates = 0
                for attr_name in section['params']:
                    val = getattr(section['target'], attr_name)
                    
                    # Determine string representation and regex pattern based on type
                    if isinstance(val, str):
                        # For strings, we expect the file to have: var = "Value" or var = 'Value'
                        val_str = f"'{val}'" # Default to single quotes for saving
                        # Regex matches: name = "old_val" or name = 'old_val', supporting self.name = ...
                        pattern = rf"(^\s*(?:self\.)?{attr_name}\s*=\s*)(['\"][\w\.]+['\"])(.*$)"
                    elif isinstance(val, bool):
                        val_str = str(val)
                        pattern = rf"(^\s*(?:self\.)?{attr_name}\s*=\s*)(True|False)(.*$)"
                    else:
                        # Numbers (int/float)
                        is_float = isinstance(val, float)
                        val_str = f"{val:.2f}" if is_float else str(int(val))
                        # Regex matches: name = 123 or name = 12.34
                        pattern = rf"(^\s*(?:self\.)?{attr_name}\s*=\s*)([\d\.]+)(.*$)"
                    
                    def replacer(m): return f"{m.group(1)}{val_str}{m.group(3)}"
                    
                    new_content, count = re.subn(pattern, replacer, content, flags=re.MULTILINE)
                    if count > 0:
                        content = new_content
                        updates += count
                    else:
                         print(f"Warning: Could not find/update variable '{attr_name}' in {source_file}")
                
                if updates > 0:
                    with open(source_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    total_updates += updates
                    
            except Exception as e:
                print(f"Error saving {source_file}: {e}")
                
        QMessageBox.information(self, "Saved", f"Updated {total_updates} parameters across files.")


class GlowDevPanel(DevPanel):
    @staticmethod
    def create_for_glow(glow_overlay, glow_manager=None):
        # Legacy support wrapper
        panel = DevPanel(title="Glow Effect Tuning")
        
        params = {
            'BLOB_RADIUS': (10, 150, 5),
            'BLOB_OPACITY_CENTER': (0, 255, 5),
            'BLOB_OPACITY_MID': (0, 255, 5),
            'ELLIPSE_SCALE_X': (0.1, 1.5, 0.05, True),
            'ELLIPSE_SCALE_Y': (0.1, 1.5, 0.05, True),
            'PULSE_OPACITY_MIN': (0.0, 1.0, 0.05, True),
            'PULSE_OPACITY_MAX': (0.0, 1.0, 0.05, True),
            'MASK_PADDING': (0, 50, 1),
            'MASK_CORNER_RADIUS': (0, 50, 1),
            'MASK_FEATHER': (0, 50, 1),
            'HOVER_MAX_OPACITY': (0.0, 1.0, 0.05, True),
            'HOVER_FADE_IN_MS': (50, 1000, 50),
            'HOVER_FADE_OUT_MS': (50, 1000, 50),
        }
        
        def on_change():
            if glow_overlay: glow_overlay.update()
            
        source_path = r"v:\_MY_APPS\ImgApp_1\client\gui\effects\glow_effect.py"
        
        panel.add_section(glow_overlay, params, "Glow Overlay", source_path, on_change)
        return panel
