# Custom Presets Architecture

## Overview
The custom preset system allows users to save their current processing settings (Image, Video, Loop) as persistent YAML configurations. These presets can be executed directly via drag-and-drop or restored to "Lab Mode" (the manual settings panel) for further editing.

## Core Components

The system is built on four main components:

1.  **Orchestrator (`PresetOrchestrator`)**: The central plugin manager. It handles:
    *   Loading/Saving presets via `PresetManager`.
    *   Managing the `PresetGallery` UI (visual grid of cards).
    *   Executing presets (delegating complex logic).
2.  **Generator (`CustomPresetGenerator`)**: A utility class responsible for capturing the current state of the application's tabs (`BaseTab.get_params()`) and serializing it into a YAML-compatible dictionary.
3.  **Conductor Integration (`ConversionConductor`)**: Handles the actual execution of the conversion job. The orchestrator delegates to this class to run the job, ensuring consistent behavior with manual conversions.
4.  **Data Model (`PresetDefinition`)**: Represents a single preset, holding metadata (name, icon, type) and the configuration payload.

## Architecture (Mediator-Shell Pattern)

The custom preset system strictly follows the Mediator-Shell pattern to maintain clean separation of concerns and avoid tight coupling.

### 1. Plugin Encapsulation
The entire preset system is encapsulated as a "plugin" initialized within the `DragDropArea` (the "Shell"). This keeps the main application logic clean.

### 2. Dependency Injection
The `PresetOrchestrator` receives critical dependencies—specifically the `ConversionConductor`—via its constructor (injected by `MainWindow`). This avoids global state access and allows the orchestrator to delegate execution cleanly.

### 3. Signal-Based Communication
The plugin never modifies the main window or other components directly. All actions that affect the wider application bubble up via signals:
*   **Execution**: Delegated downward to `ConversionConductor`.
*   **Restoration**: Emitted upward via `go_to_lab_requested` signal, which the `MainWindow` connects to its restoration logic.

## Key Workflows

### 1. Preset Creation
Triggered by the `CustomPresetButton` (standardized in `BaseTab`):

1.  **Trigger**: User clicks "Save as Preset" in any tab (Image, Video, Loop).
2.  **Capture**: The `CommandPanel` collects parameters from the active tab using `get_params()`.
3.  **Generate**: `CustomPresetGenerator` creates a "Lab Mode Reference" payload containing:
    *   `lab_mode_settings`: The full parameter dictionary from the tab.
    *   `target_type`: The active tab type (image, video, loop).
    *   Metadata: Timestamp, generated name.
4.  **Save**: `PresetManager` writes the YAML file to `user_custom_presets/`.
5.  **Reload**: The orchestrator detects the new file and updates the gallery instantly.

### 2. Preset Execution (Lab Mode Logic)
When a user drops files onto a custom preset card:

1.  **Detection**: `PresetOrchestrator` identifies the preset as a "Lab Mode" preset (by checking for the `lab_mode_settings` key).
2.  **Delegation (Key Architecural Feature)**: Instead of trying to reconstruct the conversion engine itself (which leads to duplicate logic), it calls:
    ```python
    self._conversion_conductor.start_preset_conversion_with_settings(
        files, lab_settings, output_mode, organized_name, custom_path
    )
    ```
3.  **Execution**: The `ConversionConductor`:
    *   Merges the preset's settings with the current global output settings.
    *   Selects the appropriate engine (e.g., `TargetSizeConversionEngine` or `ManualModeConversionEngine`).
    *   Runs the conversion, treating it exactly like a manual job but with pre-filled parameters.

### 3. Restoration ("Go to Lab")
When a user clicks the "Go to Lab" button on a preset card to edit the settings:

1.  **Signal Emission**: `PresetCard` emits `go_to_lab`.
2.  **Propagation**: The signal bubbles up the hierarchy:
    *   `PresetGallery` → `PresetOrchestrator` → `DragDropArea`
3.  **Hand-off**: `DragDropArea` emits `go_to_lab_requested(settings)`.
4.  **Restoration**: `MainWindow` catches this signal and calls `command_panel.restore_lab_mode_settings(settings)`, which:
    *   Switches to the correct tab (Image/Video/Loop).
    *   Populates the UI fields with the saved values.
    *   Opens the Lab panel if it is closed.

## Recent Architectural Improvements (Feb 2026)

Recent refactoring has solidified this architecture:

*   **Centralized Execution**: Engine selection logic was moved from `orchestrator.py` to `ConversionConductor`, eliminating ~75 lines of dangerous code duplication.
*   **Removed Brittle Links**: Replaced `hasattr` checks (where `DragDropArea` guessed methods on `MainWindow`) with defined signals.
*   **Unified UI Logic**: Extracted the repetitive `CustomPresetButton` creation logic into a shared helper in `BaseTab`, ensuring consistency across all tabs.
