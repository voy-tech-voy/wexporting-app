---
description: 
---

# Premium Glow Animation Specification (Qt6)

## 1. Design Philosophy
This specification defines the "Premium Pulse" visual style. It aims for a **clean, elegant, and organic** look, characteristic of high-end interfaces like Apple’s macOS or Tesla’s in-car OS.

**Key Characteristics:**
*   **Subtlety:** The glow should never scream for attention; it should breathe.
*   **Fluidity:** Use `InOutQuad` or `InOutSine` easing for organic motion, avoiding mechanical linear transitions.
*   **Depth:** The glow acts as a backlight, lifting the element off the canvas without harsh outlines.
*   **Performance:** Utilizes `QtQuick.Effects` (MultiEffect) for GPU-accelerated rendering, avoiding expensive software filters.

---

## 2. Technical Constants
Use these values to maintain consistency across buttons, cards, and modal backdrops.

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Cycle Duration** | `3000ms` | Total time for one full breathe-in/breathe-out cycle. |
| **Base Color** | `#007AFF` (Apple Blue) or `#FFFFFF` | Use low alpha (0.0 to 0.6) for the actual rendering. |
| **Blur Range** | `10` to `35` | The spread of the glow. |
| **Opacity Range** | `0.3` to `0.8` | The intensity of the glow. |
| **Easing** | `Easing.InOutQuad` | Simulates natural breathing. |

---

## 3. Reusable QML Component (`PremiumGlow.qml`)
This wrapper component applies the glow to any child item (Button, Rectangle, Image).

**Dependencies:** `QtQuick 2.15+`, `QtQuick.Effects` (Available in Qt 6.5+).

```qml
import QtQuick
import QtQuick.Effects

Item {
    id: root
    
    // --- Configuration Properties ---
    property int cornerRadius: 12
    property color glowColor: Qt.rgba(0.4, 0.7, 1.0, 1.0) // Electric Blue
    property bool active: true // Toggle animation
    
    // Adjust size to fit the child, plus padding for the glow
    // (Glow extends outside bounds, so we don't clip)
    width: contentItem.width
    height: contentItem.height
    
    // The content to be glowing (Button, Card, etc.)
    default property Item contentItem

    // 1. The Source Item (Hidden, used for mask generation)
    // We parent the contentItem here so MultiEffect can capture it.
    Item {
        id: sourceContainer
        anchors.fill: parent
        visible: false // Hidden because MultiEffect renders it
        data: [contentItem]
    }

    // 2. The Renderer
    MultiEffect {
        id: effectRenderer
        anchors.fill: parent
        source: sourceContainer
        
        // Shadow/Glow Configuration
        shadowEnabled: true
        shadowVerticalOffset: 0
        shadowHorizontalOffset: 0
        shadowColor: root.glowColor
        
        // The blur is animated below
        shadowBlur: 1.0 
    }

    // 3. The "Breathing" Animation
    SequentialAnimation {
        running: root.active
        loops: Animation.Infinite
        alwaysRunToEnd: true // Prevents abrupt jumps if stopped

        // Phase 1: Exhale (Expand & Brighten)
        ParallelAnimation {
            NumberAnimation {
                target: effectRenderer
                property: "shadowBlur"
                to: 1.2 // Normalized value (0.0 to 1.0)
                duration: 1500
                easing.type: Easing.InOutQuad
            }
            ColorAnimation {
                target: effectRenderer
                property: "shadowColor"
                to: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, 0.6)
                duration: 1500
                easing.type: Easing.InOutQuad
            }
        }

        // Phase 2: Inhale (Contract & Dim)
        ParallelAnimation {
            NumberAnimation {
                target: effectRenderer
                property: "shadowBlur"
                to: 0.4
                duration: 1500
                easing.type: Easing.InOutQuad
            }
            ColorAnimation {
                target: effectRenderer
                property: "shadowColor"
                to: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, 0.2)
                duration: 1500
                easing.type: Easing.InOutQuad
            }
        }
    }
}