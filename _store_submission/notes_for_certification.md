Notes for Certification

Technical Note for the Reviewer:

1. Bundled Binaries & Dependencies
This application functions as a graphical interface and orchestrator for professional media libraries. To ensure consistent performance and out-of-the-box functionality, the application includes bundled binaries of FFmpeg and ImageMagick. These are located within the application’s root directory in the bin folder. All binaries are called internally and are essential for the app's core processing features.

2. Resource Usage Expectations
Please be advised that during the "Process" or "Export" phases, specifically when using AI models (Real-ESRGAN for upscaling or RIFE for interpolation), the application will utilize high levels of CPU and GPU resources. This is expected behavior as the app performs billions of neural network calculations locally to reconstruct media frames. The app is optimized to utilize hardware acceleration where available.

3. Quick Start for Testing
To verify the core functionality of the application:

    Launch the app and drag any media file (e.g., a .jpg,.png,.mp4) into the main window.

    Select any preset from the menu or use lab mode.

    Click the "Start" button.

    The processed output file will be generated in the same or nested directory as the source file.

4. Network Activity (internetClient Capability Justification)

This application requires the internetClient capability for the following specific, user-beneficial purposes. All network communication uses HTTPS exclusively. No user PII or file content is ever transmitted.

    External endpoint: https://wavyvoy.pythonanywhere.com

    The following API calls are made to this server:

    - /api/v1/app-config — Checks whether a mandatory or optional app update is available. Called once at startup.
    - /api/v1/store/validate-receipt — Validates the Microsoft Store purchase receipt to confirm premium entitlement. Called after a Store purchase event.
    - /api/v1/energy/sync — Synchronises the local AI processing energy balance with the server. Called when a user is authenticated and initiates a session.
    - /api/v1/energy/reserve and /api/v1/energy/report — Reserves and reports AI processing units consumed during a job. Called during processing operations where AI upscaling or interpolation is active.

    No analytics, telemetry, crash reports, or user file content is transmitted. All media processing is performed entirely on-device.
