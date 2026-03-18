DESIGN_SPEC: THE 3:4 PRESET CARD

Component ID: UI_Preset_Card_3x4
Context: Used within the Smart Drop Overlay Grid.
Geometry: Vertical Portrait (AspectRatio 3:4).
Visual Style: "Monolith" – A distinct icon chamber top, text base bottom.
1. GEOMETRY & LAYOUT

Concept: A vertical card divided into two distinct zones.
Dimensions (Reference): Width 120px x Height 160px (3:4 Ratio).
The Layout Map
code Text

+-------------------------------------------------------+
|                                                       |
|   [ ZONE A: ICON CHAMBER ]                            |
|   (Square 1:1 Ratio)                                  |
|   CENTERED GLYPH (e.g., TikTok Logo)                  |
|                                                       |
+-------------------------------------------------------+
|   [ ZONE B: TEXT BASE ]                               |
|   Title: "TIKTOK"                                     |
|   Sub:   "1080x1920"                                  |
+-------------------------------------------------------+

    Zone A (Upper):

        Ratio: 1:1 (Square).

        Content: Centered Icon.

        Padding: 24px (White space around icon).

    Zone B (Lower):

        Ratio: Remaining height (approx 1:3 ratio relative to width).

        Content: Text Label (Title) + Meta Data (Subtitle).

        Alignment: Center-aligned text.

2. STYLE DEFINITIONS (QSS)

Inject this strictly into the stylesheet.
code CSS

/* --- THE CARD CONTAINER --- */
QFrame.PresetCard {
    background-color: #1C1C1C;      /* Surface Main */
    border: 1px solid #333333;      /* Border Dim */
    border-radius: 12px;
    min-width: 120px;
    min-height: 160px;
    max-width: 120px;
    max-height: 160px;
}

/* --- ZONE A: ICON CHAMBER --- */
QLabel#CardIcon {
    background-color: transparent;
    /* Icon styling handled via QPixmap/Python */
    padding: 10px;
    qproperty-alignment: 'AlignCenter';
}

/* --- ZONE B: TEXT BASE --- */
QWidget#TextContainer {
    background-color: transparent;
}

QLabel#CardTitle {
    color: #F5F5F7;                 /* Text Main */
    font-family: "Inter", sans-serif;
    font-size: 13px;
    font-weight: 700;               /* Bold */
    qproperty-alignment: 'AlignCenter';
    margin-bottom: 2px;
}

QLabel#CardSubtitle {
    color: #86868B;                 /* Text Secondary */
    font-family: "JetBrains Mono", monospace;
    font-size: 10px;
    font-weight: 400;
    qproperty-alignment: 'AlignCenter';
}

/* --- INTERACTION STATES --- */

/* 1. HOVER (Mouse Over) */
QFrame.PresetCard:hover {
    background-color: #252525;
    border: 1px solid #666666;
    /* Physical Lift is handled by Python Animation */
}

/* 2. DRAG ACTIVE (File hovering over card) */
QFrame.PresetCard[dragActive="true"] {
    background-color: rgba(0, 224, 255, 0.1); /* Cyan Tint */
    border: 2px solid #00E0FF;                /* Neon Cyan Border */
}
/* Note: Subtitles turn cyan in this state for extra pop */
QFrame.PresetCard[dragActive="true"] QLabel#CardSubtitle {
    color: #00E0FF;
}

3. PYTHON IMPLEMENTATION LOGIC
Class Structure

The Agent should implement PresetCard as a QFrame containing a QVBoxLayout.
code Python

class PresetCard(QFrame):
    def __init__(self, title, subtitle, icon_name):
        super().__init__()
        self.setFixedSize(120, 160) # Enforce 3:4
        self.setProperty("class", "PresetCard")
        
        # Main Layout (No margins to let hover borders hug edge)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12) # Bottom padding for text
        layout.setSpacing(0)

        # 1. Icon Chamber (Stretch Factor 3)
        self.icon_lbl = QLabel()
        self.icon_lbl.setObjectName("CardIcon")
        # Load icon via QIcon/QPixmap here
        layout.addWidget(self.icon_lbl, 3) 

        # 2. Text Base (Stretch Factor 1)
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setObjectName("CardTitle")
        
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setObjectName("CardSubtitle")
        
        layout.addWidget(self.title_lbl, 0)
        layout.addWidget(self.sub_lbl, 0)

3. COMPONENT BEHAVIOR & ANIMATION

    Visual States (Managed via QSS & Properties):

        Hover (Mouse Over):
            Handled purely by QSS (`:hover`).
            Effect: Background lighten, Border lighten. No physical geometry change (No Lift) to ensure grid stability.

        Drag Active (Targeted):
            Property: `setProperty("dragActive", True)` / `style().unpolish(self); style().polish(self);`
            Effect: Cyan Tint + Neon Cyan Border (as defined in QSS).
            Icon Opacity: 1.0 (Full visibility).

        Confirmed (Success):
            Effect: Background flashes Green.
            Duration: ~150ms hold before reset.

    Implementation Note:

        The Agent must implement a method `set_state(state_enum)` to trigger these property changes cleanly.
        Avoid manual geometry animation (`move()`, `setGeometry()`) as it conflicts with layout managers.


4. CHECKLIST FOR THE AGENT

    Dimensions: Ensure strict 120x160 (or scalable 3:4 equivalent) size policy.

    Icon: The icon in the upper square must be centered.

    Hierarchy: The Title is White (Bold), Subtitle is Gray (Monospace).

    Feedback: The card must glow visibly when a file is dragged over it.