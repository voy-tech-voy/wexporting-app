import os

classes = [
    "HoverIconButton", "FileListItemWidget", "DynamicFontButton", "ThemedCheckBox",
    "SegmentedButton", "GenericSegmentedControl", "OutputDestinationSelector", "GPUIndicator",
    "AnimatedSideModeButton", "ModeButtonsWidget", "SideButtonGroup", "CustomComboBox",
    "SpinBoxLineEdit", "DragOverlay", "CustomTargetSizeSpinBox", "TimeRangeSlider",
    "ResizeFolder", "RotationOptions", "QSvgIconWidget", "SquareButtonRow",
    "PresetButton", "FormatButtonRow", "RotationButtonRow", "AppTooltip",
    "TooltipEventFilter", "LoopFormatSelector", "HardwareAwareCodecButton",
    "VideoCodecSelector", "MorphingButton", "PresetStatusButton"
]

project_root = r"V:\_MY_APPS\ImgApp_1\client"
ignore_files = ["custom_widgets.py", "__pycache__", ".git", ".idea"]

usage_counts = {cls: 0 for cls in classes}

for root, dirs, files in os.walk(project_root):
    for file in files:
        if file in ignore_files:
            continue
        if not file.endswith(".py"):
            continue
            
        path = os.path.join(root, file)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                for cls in classes:
                    if cls in content:
                        usage_counts[cls] += 1
                        # print(f"Found {cls} in {file}")
        except Exception as e:
            print(f"Error reading {path}: {e}")

print("Unused classes:")
for cls, count in usage_counts.items():
    if count == 0:
        print(f"- {cls}")
