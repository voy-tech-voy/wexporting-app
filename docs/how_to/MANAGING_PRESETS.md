# Managing Presets

This guide explains how to create, test, and deploy new presets to the update server.

## Overview

Presets are **YAML files** that define processing parameters for images and videos. The update system automatically serves any YAML file found in the server's `storage/updates/presets/` directory.

## 1. Preset Structure

Create a YAML file (e.g., `cinematic_teal.yaml`) with the following structure:

```yaml
meta:
  version: 1.0          # Increment this to trigger client updates
  description: "Cinematic Teal & Orange Look"
  author: "ImgApp Team"
  
# Process settings
process:
  type: "video"         # 'video', 'image', or 'loop'
  container: "mp4"
  platform: "instagram" # optional category
  
# FFmpeg/ImageMagick parameters
params:
  vcodec: "libx264"
  crf: 23
  preset: "slow"
  filters:
    - "lut3d=teal_orange.cube"
    - "unsharp=5:5:1.0:5:5:0.0"

# UI Settings (optional)
ui:
  icon: "movie"
  group: "Cinematic"
```

### Key Fields
- **`process.type`**: **CRITICAL**. Determines which tab the preset appears in (`video`, `image`, `loop`). It must be one of these exact values.
- **The Filename**: The preset's ID is derived from its filename (e.g., `cinematic_teal.yaml` -> ID: `cinematic_teal`). This ID must be unique.

## 2. Adding a New Preset

To add a completely new preset that users have never seen before:

1.  **Create the YAML File**:
    Create a new file (e.g., `super_slowmo.yaml`) with `meta.version: 1.0`.

2.  **Upload to Server**:
    Place the file in `server/storage/updates/presets/`.

3.  **That's it!**
    - The server automatically indexes the new file.
    - **No database entry is required.**
    - **No manifest update is required** (it's auto-generated).
    - Clients will see a new ID in the manifest, compare it to their local list (where it's missing), and download it immediately.

## 3. Updating an Existing Preset

1.  **Locate the Server Directory**:
    Go to `server/storage/updates/presets/`.

2.  **Organize (Optional)**:
    You can use subdirectories to organize presets (e.g., `server/storage/updates/presets/social/` or `server/storage/updates/presets/filters/`). The client preserves this structure.

3.  **Upload/Copy File**:
    Place your `.yaml` file in the directory.
    - *New Preset*: Just copy the file.
    - *Update*: Overwrite the existing file AND ensure `meta.version` is higher.

4.  **Verify**:
    The server automatically rescans this directory when the `/api/v1/updates/manifest` endpoint is hit. You don't need to restart the server.

## 4. Client Update Process

1.  Client starts up or user clicks "Check for Updates".
2.  Client fetches manifest from server.
3.  Client compares `meta.version` in the manifest with its local `manifest.json`.
4.  If different, client downloads the new YAML file to its local `presets/` directory.

## Testing

To test a preset locally before deploying:
1.  Place the YAML file in your local client's `presets/` folder.
2.  Restart the app.
3.  Verify it appears in the UI and works as expected.
