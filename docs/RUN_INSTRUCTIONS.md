# Running the App

To run the application from the terminal, follows these instructions:

### Standard Command
Run this command from the project root (`v:\_MY_APPS\ImgApp_1`):

```powershell
& "v:\_MY_APPS\ImgApp_1\imgapp_venv\Scripts\python.exe" -m client.main
```

### Key Info
*   **Venv**: Uses the local `imgapp_venv`.
*   **Module Mode**: Uses `-m client.main` to correctly resolve internal imports.
*   **Environment**: The app currently defaults to `dev_mode = True` in `main.py` to skip the login screen during development.
