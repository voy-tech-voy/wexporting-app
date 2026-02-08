import os
import sys
import subprocess
import time

def run_server():
    print("Starting Server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    # Use the python executable from the virtual environment if available
    python_exe = sys.executable
    if os.path.exists(os.path.join("imgapp_venv", "Scripts", "python.exe")):
        python_exe = os.path.join("imgapp_venv", "Scripts", "python.exe")
    
    server_process = subprocess.Popen(
        [python_exe, "server/app.py"],
        env=env,
        cwd=os.getcwd()
    )
    return server_process

if __name__ == "__main__":
    server = run_server()
    try:
        print("Server running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            if server.poll() is not None:
                print(f"Server exited with code {server.returncode}")
                break
    except KeyboardInterrupt:
        print("Stopping server...")
        server.terminate()
        server.wait()
