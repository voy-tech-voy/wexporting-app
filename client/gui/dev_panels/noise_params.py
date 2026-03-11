"""
Global noise gradient parameters for FileListItemWidget.

This module provides a singleton class to hold adjustable noise parameters
that can be modified at runtime via the dev panel (F11).
"""


class NoiseParams:
    """
    Global parameters for noise gradient rendering in file list items.
    
    These values can be adjusted in real-time via the dev panel (F11).
    """
    
    # Texture generation parameters
    texture_size = 32  # Base size before scaling (32 → 64)
    max_alpha = 12  # Maximum noise opacity (0-255)
    void_cluster_passes = 3  # Number of blue noise refinement passes
    
    # Base gradient parameters (status color fade)
    gradient_start_alpha = 80  # Opacity at left edge
    gradient_mid_alpha = 20  # Opacity at mid-point
    gradient_mid_position = 0.4  # Position of mid-point (0.0-1.0)
    
    # Noise mask parameters (controls where noise appears)
    mask_start_pos = 0.0  # Start position (clean, no noise)
    mask_ramp_pos = 0.2  # Where noise starts to appear
    mask_ramp_alpha = 200  # Noise opacity at ramp position
    mask_peak_pos = 0.6  # Where noise is strongest
    mask_peak_alpha = 255  # Maximum noise opacity
    mask_end_pos = 1.0  # End position (clean, no noise)
    
    # Behavior
    persistence_enabled = False  # If True, clicking items won't clear status gradient
    flat_completed_enabled = True # If True, completed items use flat color instead of noise gradient
    
    @classmethod
    def get_config_path(cls):
        """Get path to config file."""
        import os
        # Store in user's APPDATA folder to avoid UAC permissions issues
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(app_data, 'wexporting', 'config')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'noise_params.json')

    @classmethod
    def save(cls):
        """Save current parameters to JSON file."""
        import json
        data = {
            'texture_size': cls.texture_size,
            'max_alpha': cls.max_alpha,
            'void_cluster_passes': cls.void_cluster_passes,
            'gradient_start_alpha': cls.gradient_start_alpha,
            'gradient_mid_alpha': cls.gradient_mid_alpha,
            'gradient_mid_position': cls.gradient_mid_position,
            'mask_ramp_pos': cls.mask_ramp_pos,
            'mask_ramp_alpha': cls.mask_ramp_alpha,
            'mask_peak_pos': cls.mask_peak_pos,
            'mask_peak_alpha': cls.mask_peak_alpha,
            'persistence_enabled': cls.persistence_enabled,
            'flat_completed_enabled': cls.flat_completed_enabled
        }
        try:
            with open(cls.get_config_path(), 'w') as f:
                json.dump(data, f, indent=4)
            print(f"[NoiseParams] Saved to {cls.get_config_path()}")
            return True
        except Exception as e:
            print(f"[NoiseParams] Save failed: {e}")
            return False

    @classmethod
    def load(cls):
        """Load parameters from JSON file."""
        import json
        import os
        path = cls.get_config_path()
        if not os.path.exists(path):
            return
            
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            cls.texture_size = data.get('texture_size', cls.texture_size)
            cls.max_alpha = data.get('max_alpha', cls.max_alpha)
            cls.void_cluster_passes = data.get('void_cluster_passes', cls.void_cluster_passes)
            cls.gradient_start_alpha = data.get('gradient_start_alpha', cls.gradient_start_alpha)
            cls.gradient_mid_alpha = data.get('gradient_mid_alpha', cls.gradient_mid_alpha)
            cls.gradient_mid_position = data.get('gradient_mid_position', cls.gradient_mid_position)
            cls.mask_ramp_pos = data.get('mask_ramp_pos', cls.mask_ramp_pos)
            cls.mask_ramp_alpha = data.get('mask_ramp_alpha', cls.mask_ramp_alpha)
            cls.mask_peak_pos = data.get('mask_peak_pos', cls.mask_peak_pos)
            cls.mask_peak_alpha = data.get('mask_peak_alpha', cls.mask_peak_alpha)
            cls.persistence_enabled = data.get('persistence_enabled', cls.persistence_enabled)
            cls.flat_completed_enabled = data.get('flat_completed_enabled', cls.flat_completed_enabled)
            
            cls.invalidate_cache()
        except Exception as e:
            print(f"[NoiseParams] Load failed: {e}")
    
    @classmethod
    def invalidate_cache(cls):
        """Clear the cached noise texture to force regeneration."""
        try:
            from client.gui.widgets.file_list_item import FileListItemWidget
            FileListItemWidget._noise_texture = None
        except ImportError:
            # Module not yet loaded, cache will be empty anyway
            pass
    
    @classmethod
    def reset_to_defaults(cls):
        """Reset all parameters to default values."""
        cls.texture_size = 32
        cls.max_alpha = 12
        cls.void_cluster_passes = 3
        
        cls.gradient_start_alpha = 80
        cls.gradient_mid_alpha = 20
        cls.gradient_mid_position = 0.4
        
        cls.mask_start_pos = 0.0
        cls.mask_ramp_pos = 0.2
        cls.mask_ramp_alpha = 200
        cls.mask_peak_pos = 0.6
        cls.mask_peak_alpha = 255
        cls.mask_end_pos = 1.0
        
        cls.persistence_enabled = False
        cls.flat_completed_enabled = True
        
        cls.invalidate_cache()
