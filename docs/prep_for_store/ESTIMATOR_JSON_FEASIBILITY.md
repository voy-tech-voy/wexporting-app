# Feasibility Analysis: JSON-Driven Estimators

## Executive Summary
**Conclusion**: Converting the current Python-based estimators to a purely JSON-based data model is **NOT FEASIBLE** without rebuilding a Turing-complete interpreter within the app (which may still violate store policies).

The estimators are not simple mathematical formulas (e.g., `bitrate = width * height * 0.1`). They are **active algorithms** that interact with the OS and filesystem.

## Complexity Analysis

### 1. Loop Estimator (`gif_estimator_v23.py`)
**Logic Type**: Adaptive Hybrid Solver with Iterative Probing
- **Complexity**: High
- **Why it fails JSON**:
    - **Live Probing**: It runs actual FFmpeg commands on small sample chunks to measure output size.
    - **Conditional Logic**: "If sample size > target, try next step in quality ladder."
    - **Heuristics**: Analyzes gradients (`signalstats` filter) to decide between `bayer` and `sierra2_4a` dithering.
    - **Binary Search**: Falls back to binary search for resolution scaling if presets fail.

**JSON Requirement**: You would need a JSON structure that defines a flow chart, loop structures, and system call templates.

### 2. Video Estimator (`mp4_h264_estimator_v4.py`)
**Logic Type**: 2-Pass Encoding with Dynamic Bitrate Calculation
- **Complexity**: Medium-High
- **Why it fails JSON**:
    - **Process Management**: Manages FFmpeg subprocesses, pipes, and background threads for progress tracking.
    - **Pass Log Parsing**: Reads and cleans up FFmpeg pass log files.
    - **Safety Nets**: Dynamic fallback logic if audio budget eats into video budget.

### 3. Image Estimator (`avif_estimator_v2.py`)
**Logic Type**: Aggressive Mid-Probe Binary Search
- **Complexity**: Medium
- **Why it fails JSON**:
    - **Algorithm**: Implements a specific binary search strategy (probe middle, then search upper/lower half).
    - **Interruptibility**: Heavily relies on Python's `subprocess` and `threading` to handle user cancellation gracefully.

## The "Interpreter" Trap
To support this via JSON, we would need to invent a syntax like:

```json
{
  "steps": [
    { "type": "run_command", "cmd": "ffmpeg -i ...", "store_output": "size" },
    { "type": "if", "condition": "size > target", "then": { "goto": "step_3" } }
  ]
}
```

**Risk**:
- **Complexity**: Writing estimators in this custom JSON syntax would be painful and error-prone.
- **Store Policy**: Apple/Microsoft might still view this as "downloading executable code" (interpreted script), just in a custom language.

## Recommendation
Since we cannot perform these complex operations with simple coefficients, the **original plan stands**:

1.  **Remove Remote Updates**: Ship estimators as part of the compiled app binary.
2.  **App Updates**: Improvements to estimation logic require a store update (new app version).
3.  **Data-Driven Coefficients (Partial)**: We *could* extract simple constants (e.g., "baseline bitrate factor") into a JSON config, allowing *minor* tuning from the server. But the *logic* (the algorithm) must stay in the binary.
