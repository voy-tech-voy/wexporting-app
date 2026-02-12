import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any

class SequenceDetector:
    """
    Detects and groups file sequences based on naming patterns.
    Examples:
        file_001.png, file_002.png -> Sequence "file_###.png" (Range 1-2)
        image.jpg -> Single file
    """
    
    @staticmethod
    def detect(files: List[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Group files into sequences using template matching.
        This handles cases where the sequence number is in the middle 
        or there are multiple number blocks.
        """
        # Group by directory
        by_dir = defaultdict(list)
        for f in files:
            p = Path(f)
            by_dir[str(p.parent)].append(str(p))
            
        final_sequences = []
        final_singles = []
        
        for parent_dir, dir_files in by_dir.items():
            # Group by "Template" (static parts of filename)
            # template_groups[static_parts_tuple][num_slots] = [ (numeric_blocks, full_path), ... ]
            template_groups = defaultdict(list)
            
            for f in dir_files:
                name = Path(f).name
                # Split into static and dynamic parts
                # e.g. "img_001_v2.png" -> parts=["img_", "_v", ".png"], nums=["001", "2"]
                nums = re.findall(r'\d+', name)
                parts = tuple(re.split(r'\d+', name))
                
                template_groups[(parts, len(nums))].append((nums, f))
            
            # Process groups to find sequences
            for (parts, num_slots), items in template_groups.items():
                if len(items) < 2:
                    for _, f in items:
                        final_singles.append(f)
                    continue
                
                # We need to find WHICH slot varies.
                # If multiple slots vary, it might be a complex sequence or just noise.
                # Usually only ONE slot varies for a sequence.
                # slot_variation[slot_index] = set of values seen in that slot
                variations = [set() for _ in range(num_slots)]
                for nums, _ in items:
                    for i, val in enumerate(nums):
                        variations[i].add(val)
                
                varying_slots = [i for i, s in enumerate(variations) if len(s) > 1]
                
                if len(varying_slots) == 1:
                    # Classic sequence!
                    slot_idx = varying_slots[0]
                    # Sort items by the numeric value of the varying slot
                    items.sort(key=lambda x: int(x[0][slot_idx]))
                    
                    # Construct display name
                    # parts: [prefix, mid1, mid2, ... suffix]
                    # nums: [n1, n2, ... n_varying, ... nN]
                    first_nums, _ = items[0]
                    last_nums, _ = items[-1]
                    
                    # Template-style name: prefix[start-end]mid...
                    display_parts = []
                    for i in range(num_slots):
                        display_parts.append(parts[i])
                        if i == slot_idx:
                            # The varying slot gets the [range]
                            display_parts.append(f"[{first_nums[i]}-{last_nums[i]}]")
                        else:
                            # Constant slots stay as they are
                            display_parts.append(first_nums[i])
                    display_parts.append(parts[-1]) # Final suffix
                    
                    display_name = "".join(display_parts)
                    seq_files = [x[1] for x in items]
                    
                    final_sequences.append({
                        'name': display_name,
                        'files': seq_files,
                        'count': len(seq_files),
                        'range': (int(first_nums[slot_idx]), int(last_nums[slot_idx])),
                        'preview_file': seq_files[0]
                    })
                else:
                    # No slot varies (identical names? impossible in one dir) 
                    # OR multiple slots vary (e.g. gradient001_q40 and gradient002_q50)
                    # For now, treat as singles or try to sub-group? 
                    # Simple approach: if multiple vary, don't group or pick the LAST one that varies?
                    # User expects "003" in middle to work even if "40" at end is constant.
                    # My logic above handles this: len(varying_slots) will be 1.
                    
                    # If multiple vary, we might have multiple independent sequences 
                    # but usually it means they aren't a simple sequence.
                    for _, f in items:
                        final_singles.append(f)
                        
        return final_sequences, final_singles
