from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton
)
from PySide6.QtCore import Qt

class DevCreditBarPanel(QWidget):
    def __init__(self, credit_bar, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("[DEV] Credit Bar Tuner (Thunderbolt)")
        self.credit_bar = credit_bar
        self.setStyleSheet("background-color: #333; color: white;")
        layout = QVBoxLayout(self)
        
        # New Thunderbolt Props
        self.add_slider(layout, "Filled Alpha", 0, 100, credit_bar.filled_transparency * 100, 
                       lambda v: setattr(credit_bar, 'filled_transparency', v/100.0))
        
        self.add_slider(layout, "Empty Alpha", 0, 100, credit_bar.empty_transparency * 100, 
                       lambda v: setattr(credit_bar, 'empty_transparency', v/100.0))
        
        self.add_slider(layout, "Gain", 0, 200, credit_bar.gain * 100, 
                       lambda v: setattr(credit_bar, 'gain', v/100.0))
        
        # Credits slider - updates both UI and EnergyManager
        def update_credits(value):
            # Update UI
            setattr(credit_bar, 'current_credits', int(value))
            # Update EnergyManager balance
            from client.core.energy_manager import EnergyManager
            energy_mgr = EnergyManager.instance()
            energy_mgr.balance = int(value)
            energy_mgr.save()
            energy_mgr.energy_changed.emit(int(value), energy_mgr.max_daily_energy)
        
        self.add_slider(layout, "Credits", 0, credit_bar.max_credits, credit_bar.current_credits, 
                       update_credits)
        
        # Info label
        lbl_info = QLabel("Credit changes are now persisted to EnergyManager.")
        lbl_info.setStyleSheet("color: #4CAF50; font-style: italic; margin-top: 10px;")
        layout.addWidget(lbl_info)
        
    def create_button(self, text, callback):
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0066DD; }
            QPushButton:pressed { background-color: #0055BB; }
        """)
        btn.clicked.connect(callback)
        return btn
        
    def add_slider(self, layout, name, min_v, max_v, val, callback):
        row = QHBoxLayout()
        lbl = QLabel(f"{name}: {val/100.0 if 'Alpha' in name or 'Gain' in name else val:.2f}")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_v), int(max_v))
        slider.setValue(int(val))
        def on_change(v):
            display_val = v/100.0 if ('Alpha' in name or 'Gain' in name) else v
            lbl.setText(f"{name}: {display_val:.2f}")
            callback(v)
        slider.valueChanged.connect(on_change)
        row.addWidget(lbl)
        row.addWidget(slider)
        layout.addLayout(row)
