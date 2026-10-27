import os
import subprocess
import sys

# Entrypoint for Hugging Face Gradio Space
# This file is automatically executed by Hugging Face on port 7860
if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start.sh")
    if os.path.exists(script_path):
        os.chmod(script_path, 0o755)
        sys.stdout.flush()
        subprocess.run(["/bin/bash", script_path], check=True)
    else:
        print("Error: start.sh not found!")
