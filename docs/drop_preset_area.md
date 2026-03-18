LOGIC_SPEC: SMART PRESET OVERLAY SYSTEM
1. DATA ARCHITECTURE (The Preset Registry)

Before the UI is drawn, the system must establish a structured definition of "Presets."

    The Preset Object: Every card represents a data object containing:

        ID: Unique identifier (e.g., TIKTOK_HQ).

        Display Data: Title, Subtitle, Icon Resource Path.

        Category Tag: Used for tab filtering (e.g., SOCIAL, WEB, UTILS).

        Conversion Logic: A dictionary of parameters (Resolution, Format, Bitrate) that will be applied to files dropped on this card.

    The Collection: These objects are stored in a central list or registry, which the UI iterates through to generate the Grid Cards.

2. COMPONENT ARCHITECTURE (The Visual Structure)
A. The Overlay Container

    Z-Order: Must sit on the highest layer (z-index), covering the entire Main Window content.

    Visibility: Hidden by default. Visible only during a Drag operation.

    Background: High-opacity dark matte (not blur) to ensure performance.

    Event Handling: It acts as a "Transparent Proxy." It intercepts mouse events to determine user intent but allows the drag action to continue.

B. The Filter Logic (Tabs)

    Tabs: A segmented control at the top (All | Social | Web).

    Behavior:

        When a tab is selected, the logic iterates through all Grid Cards.

        Match: If a card's Category Tag matches the tab (or tab is "All"), the card is set to Visible.

        No Match: The card is set to Hidden (collapsed).

        Result: The grid dynamically re-flows to fill gaps.

C. The Grid Layout

    Arrangement: Cards are arranged in a responsive grid or flow layout.

    Spacing: Uniform gaps between cards.

    Scrolling: If cards exceed window height, the grid area must scroll independently of the overlay header.

3. THE INTERACTION STATE MACHINE (The Flow)

The logic is driven by four key states of the Drag & Drop event lifecycle.
State 1: WAKE (Drag Enter)

    Trigger: User drags a file from the OS into the Main Window boundaries.

    System Action:

        Block UI: The Overlay is set to Visible, blocking interaction with the underlying file list.

        Animate In: The Overlay opacity transitions from 0% to 100%.

        Staggered Reveal: Cards animate in (scale/fade) sequence with a slight delay between each to create a "wave" effect.

State 2: SEEK (Drag Move)

    Trigger: User moves the mouse while holding the file over the Overlay.

    Hit-Test Logic:

        The system constantly calculates which UI element is directly under the mouse cursor.

        It traverses up the widget hierarchy to find if the cursor is inside a Preset Card.

    Visual Feedback:

        Target Found: Trigger the Card's "Active State" as defined in `preset_card_spec.md` (e.g., Cyan Border, Visual Highlight). Deactivate all other cards.

        Target Lost: If the cursor moves into the void between cards, deactivate all cards.

State 3: COMMIT (Drop)

    Trigger: User releases the mouse button.

    Decision Fork:

        Path A (Valid Target): If released over a Preset Card:

            Trigger Card "Success State" (e.g., Green Flash).

            Extract settings from the Card's data object.

            Apply settings to all dropped files.

            Send files to the processing queue.

        Path B (Void Drop): If released over empty space:

            Apply "Default" or "Last Used" settings.

            Send files to the processing queue.

State 4: RESET (Completion)

    Trigger: Immediately after the Commit logic executes.

    System Action:

        Animate Out: Overlay opacity transitions from 100% to 0%.

        Hide: Once animation finishes, set Overlay visibility to Hidden.

        Clean Up: Reset all cards to their neutral "Idle" state.

4. COMPONENT REFERENCE

    For detailed Visual Styles and Component Behavior, refer to `preset_card_spec.md`.
