class SequenceParams:
    """Parameters for sequence visualization, tunable via dev panel"""
    
    # Defaults based on user feedback
    stack_count = 3         # Number of items behind the main one
    scale_step = 0.05       # Scale reduction per item (0.05 = 5%)
    offset_x = 5            # Horizontal offset in pixels
    offset_y = 0            # Vertical offset in pixels
    
    @classmethod
    def get_config_path(cls):
        """Get path to config file."""
        import os
        # Store in user's APPDATA folder to avoid UAC permissions issues
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(app_data, 'wexporting', 'config')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'sequence_params.json')

    @classmethod
    def save(cls):
        """Save current parameters to JSON file."""
        import json
        data = {
            'stack_count': cls.stack_count,
            'scale_step': cls.scale_step,
            'offset_x': cls.offset_x,
            'offset_y': cls.offset_y
        }
        try:
            with open(cls.get_config_path(), 'w') as f:
                json.dump(data, f, indent=4)
            print(f"[SequenceParams] Saved to {cls.get_config_path()}")
            return True
        except Exception as e:
            print(f"[SequenceParams] Save failed: {e}")
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
                
            cls.stack_count = data.get('stack_count', cls.stack_count)
            cls.scale_step = data.get('scale_step', cls.scale_step)
            cls.offset_x = data.get('offset_x', cls.offset_x)
            cls.offset_y = data.get('offset_y', cls.offset_y)
        except Exception as e:
            print(f"[SequenceParams] Load failed: {e}")

    @classmethod
    def reset(cls):
        """Reset to defaults"""
        cls.stack_count = 3
        cls.scale_step = 0.05
        cls.offset_x = 5
        cls.offset_y = 0
