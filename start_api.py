# File: start_api.py
import subprocess
import sys
import os

os.chdir(r'C:\Users\lesson\OneDrive\Desktop\YIELD')
subprocess.run([
    sys.executable, '-m', 'uvicorn',
    'main:app', '--host', '0.0.0.0', '--port', '8000'
])