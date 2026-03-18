---
description: 
---

# Premium Glow Specification (Qt 6)

## 1. Context & Design Philosophy
This specification outlines the implementation of a "Living UI" glow effect. The goal is to replicate the high-end feel of Apple's focus states or Tesla's vehicle visualization UI.

**Visual targets:**
*   **Halo Effect:** The glow emanates from the center, not a directional drop shadow.
*   **Organic Breathing:** The animation follows a physiological rhythm (expand-hold-contract) rather than a robotic sine wave.
*   **High Performance:** Uses `QtQuick.Effects` (Shader-based) to ensure zero impact on main thread logic.

---

## 2. Technical Stack
*   **Framework:** Qt 6.5+ (Requires `QtQuick.Effects` module).
*   **Renderer:** `MultiEffect` (Replaces the obsolete `DropShadow` from Qt5).
*   **Animation Curve:** `Bezier` or `InOutQuad` for non-linear acceleration.

---

## 3. Design Tokens
Use these constants to ensure cohesion across different UI components (Cards, Buttons, Modals).

| Token | Value | Explanation |
| :--- | :--- | :--- |
| **PULSE_DURATION** | `3000ms` | A slow, calm cycle. 1.5s in, 1.5s out. |
| **GLOW_COLOR_IOS** | `#007AFF` | Apple-style system blue. |
| **GLOW_COLOR_TESLA**| `#00F0FF` | Cyberpunk/Tesla cyan. |
| **MIN_OPACITY** | `0.4` | The glow never fully disappears; it rests. |
| **MAX_OPACITY** | `0.8` | Peak intensity. |
| **BLUR_SPREAD** | `0.6` to `1.0` | Normalized MultiEffect blur range. |

---

## 4. Reusable Component (`PremiumGlow.qml`)
This component acts as a wrapper. It renders the child content *and* generates the animated glow behind it using a single render pass.

```qml
import QtQuick
import QtQuick.Effects

Item {
    id: root

    // --- Public API ---
    // The visual content to be wrapped (Button, Image, etc.)
    default property Item contentItem
    
    // Customization
    property color glowColor: "#007AFF"
    property int cornerRadius: 10
    property bool running: true
    
    // Internal size matching
    implicitWidth: contentItem ? contentItem.width : 0
    implicitHeight: contentItem ? contentItem.height : 0

    // 1. Source Container
    // Hides the actual content so the Effect can render it + the shadow
    Item {
        id: source
        anchors.fill: parent
        visible: false // Crucial: The MultiEffect renders this
        data: [root.contentItem]
    }

    // 2. High-Performance Renderer
    MultiEffect {
        id: renderer
        anchors.fill: parent
        source: source
        anchors.margins: 0 // Ensure no clipping occurs

        // Enable Shadow (The Glow)
        shadowEnabled: true
        shadowColor: root.glowColor
        shadowVerticalOffset: 0
        shadowHorizontalOffset: 0
        
        // This creates the "softness"
        blurEnabled: true 
        blur: 0.0 // Applied to content? No, we just want shadow blur.
                  // MultiEffect applies blur to shadow via shadowBlur property implicitly 
                  // but 'blur' property blurs the content. Keep content sharp:
        blurMax: 0 
        
        // Shadow Blur controls the spread
        shadowBlur: 0.6 
        shadowOpacity: 0.5
    }

    // 3. Organic Breathing Animation
    SequentialAnimation {
        running: root.running
        loops: Animation.Infinite
        alwaysRunToEnd: false

        // Inhale (Brighten & Expand)
        ParallelAnimation {
            NumberAnimation {
                target: renderer
                property: "shadowBlur"
                to: 1.0 // Maximum softness
                duration: 1500
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: renderer
                property: "shadowOpacity"
                to: 0.9 // Peak brightness
                duration: 1500
                easing.type: Easing.InOutSine
            }
        }

        // Exhale (Dim & Contract)
        ParallelAnimation {
            NumberAnimation {
                target: renderer
                property: "shadowBlur"
                to: 0.5 // Rest state softness
                duration: 1500
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                target: renderer
                property: "shadowOpacity"
                to: 0.4 // Rest state brightness
                duration: 1500
                easing.type: Easing.InOutSine
            }
        }
    }
}