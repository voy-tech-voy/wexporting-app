"""
Test script to verify Lab Mode cost calculations.

This script tests the EnergyManager._calculate_lab_cost method to ensure
codec and format costs are correctly applied according to credits_lab.json.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from client.core.energy_manager import EnergyManager

def test_video_costs():
    """Test video codec costs in Manual and Target Size modes."""
    print("\n=== VIDEO TAB TESTS ===\n")
    
    em = EnergyManager.instance()
    
    # Manual Mode - H.264
    params_h264_manual = {
        'codec': 'MP4 (H.264)',
        'video_size_mode': 'manual'
    }
    cost = em.calculate_cost('video', params_h264_manual)
    print(f"Video H.264 (Manual): {cost} credits (expected: 3)")
    assert cost == 3, f"Expected 3, got {cost}"
    
    # Manual Mode - H.265/HEVC
    params_h265_manual = {
        'codec': 'MP4 (H.265)',
        'video_size_mode': 'manual'
    }
    cost = em.calculate_cost('video', params_h265_manual)
    print(f"Video H.265 (Manual): {cost} credits (expected: 4)")
    assert cost == 4, f"Expected 4, got {cost}"
    
    # Manual Mode - AV1
    params_av1_manual = {
        'codec': 'MP4 (AV1)',
        'video_size_mode': 'manual'
    }
    cost = em.calculate_cost('video', params_av1_manual)
    print(f"Video AV1 (Manual): {cost} credits (expected: 5)")
    assert cost == 5, f"Expected 5, got {cost}"
    
    # Target Size Mode - H.264
    params_h264_target = {
        'codec': 'MP4 (H.264)',
        'video_size_mode': 'max_size'
    }
    cost = em.calculate_cost('video', params_h264_target)
    print(f"Video H.264 (Target): {cost} credits (expected: 3 + 2 = 5)")
    assert cost == 5, f"Expected 5, got {cost}"
    
    # Target Size Mode - AV1
    params_av1_target = {
        'codec': 'MP4 (AV1)',
        'video_size_mode': 'max_size'
    }
    cost = em.calculate_cost('video', params_av1_target)
    print(f"Video AV1 (Target): {cost} credits (expected: 5 + 2 = 7)")
    assert cost == 7, f"Expected 7, got {cost}"
    
    print("\n✓ All video tests passed!\n")

def test_loop_costs():
    """Test loop format costs in Manual and Target Size modes."""
    print("\n=== LOOP TAB TESTS ===\n")
    
    em = EnergyManager.instance()
    
    # Manual Mode - GIF
    params_gif_manual = {
        'loop_format': 'GIF',
        'gif_size_mode': 'manual'
    }
    cost = em.calculate_cost('loop', params_gif_manual)
    print(f"Loop GIF (Manual): {cost} credits (expected: 5)")
    assert cost == 5, f"Expected 5, got {cost}"
    
    # Manual Mode - WebM VP9
    params_webm_vp9_manual = {
        'loop_format': 'WebM (VP9)',
        'codec': 'WebM (VP9)',
        'gif_size_mode': 'manual'
    }
    cost = em.calculate_cost('loop', params_webm_vp9_manual)
    print(f"Loop WebM VP9 (Manual): {cost} credits (expected: 6)")
    assert cost == 6, f"Expected 6, got {cost}"
    
    # Manual Mode - WebM AV1
    params_webm_av1_manual = {
        'loop_format': 'WebM (AV1)',
        'codec': 'WebM (AV1)',
        'gif_size_mode': 'manual'
    }
    cost = em.calculate_cost('loop', params_webm_av1_manual)
    print(f"Loop WebM AV1 (Manual): {cost} credits (expected: 7)")
    assert cost == 7, f"Expected 7, got {cost}"
    
    # Target Size Mode - GIF
    params_gif_target = {
        'loop_format': 'GIF',
        'gif_size_mode': 'max_size'
    }
    cost = em.calculate_cost('loop', params_gif_target)
    print(f"Loop GIF (Target): {cost} credits (expected: 5 + 3 = 8)")
    assert cost == 8, f"Expected 8, got {cost}"
    
    # Target Size Mode - WebM VP9
    params_webm_vp9_target = {
        'loop_format': 'WebM (VP9)',
        'codec': 'WebM (VP9)',
        'gif_size_mode': 'max_size'
    }
    cost = em.calculate_cost('loop', params_webm_vp9_target)
    print(f"Loop WebM VP9 (Target): {cost} credits (expected: 6 + 3 = 9)")
    assert cost == 9, f"Expected 9, got {cost}"
    
    # Target Size Mode - WebM AV1
    params_webm_av1_target = {
        'loop_format': 'WebM (AV1)',
        'codec': 'WebM (AV1)',
        'gif_size_mode': 'max_size'
    }
    cost = em.calculate_cost('loop', params_webm_av1_target)
    print(f"Loop WebM AV1 (Target): {cost} credits (expected: 7 + 3 = 10)")
    assert cost == 10, f"Expected 10, got {cost}"
    
    print("\n✓ All loop tests passed!\n")

if __name__ == '__main__':
    try:
        test_video_costs()
        test_loop_costs()
        print("\n" + "="*50)
        print("ALL TESTS PASSED! ✓")
        print("="*50 + "\n")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
