---
description: 
---

The "Siri / Apple Intelligence" Mesh Glow

This effect creates a living, breathing organic gradient. Instead of a math-heavy shader, we use three animated colored circles and blur them until they merge into a gas-like fluid.

The Strategy:

    Create a transparent Item container.

    Add 3-4 Rectangle items (blobs) inside it with different neon/pastel colors.

    Animate their X/Y positions and Opacity endlessly.

    Enable layer.effect on the container and apply a massive MultiEffect blur.

Qt6 Implementation:
code Qml

import QtQuick
import QtQuick.Controls
import QtQuick.Effects // Required for MultiEffect

Item {
    id: auroraContainer
    width: 400; height: 400
    
    // 1. The Source: Floating Colored Blobs
    Item {
        id: blobSource
        anchors.fill: parent
        
        // Blob 1: Cyan/Blue
        Rectangle {
            width: parent.width * 0.8; height: width
            color: "#5E5CE6" // Indigo
            radius: width / 2
            opacity: 0.6
            x: 0; y: 0
            
            SequentialAnimation on x {
                loops: Animation.Infinite
                NumberAnimation { to: 50; duration: 4000; easing.type: Easing.InOutQuad }
                NumberAnimation { to: 0; duration: 4000; easing.type: Easing.InOutQuad }
            }
        }
        
        // Blob 2: Pink/Purple
        Rectangle {
            width: parent.width * 0.7; height: width
            color: "#BF5AF2" // Purple
            radius: width / 2
            opacity: 0.5
            x: 100; y: 100
            
            SequentialAnimation on y {
                loops: Animation.Infinite
                NumberAnimation { to: 50; duration: 5000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 150; duration: 5000; easing.type: Easing.InOutSine }
            }
        }

        // Blob 3: Warm/Orange (The "Pop")
        Rectangle {
            width: parent.width * 0.6; height: width
            color: "#FF9F0A" // Orange
            radius: width / 2
            opacity: 0.4
            anchors.centerIn: parent
        }
    }

    // 2. The Magic: Heavy Blur via MultiEffect
    // This merges the blobs into a mesh gradient
    ShaderEffectSource {
        id: offscreenSource
        sourceItem: blobSource
        anchors.fill: parent
        visible: false // Hide the raw blobs
        recursive: false
    }

    MultiEffect {
        source: offscreenSource
        anchors.fill: parent
        
        // KEY SETTINGS for the "Glow" look
        blurEnabled: true
        blurMax: 64        // Maximum blur strength
        blur: 1.0          // 100% of the Max
        saturation: 0.2    // Boost saturation slightly for vibrancy
        brightness: 0.1    // Lift brightness to make it "glow"
    }
}