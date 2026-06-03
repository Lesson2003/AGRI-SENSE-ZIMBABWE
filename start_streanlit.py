# File: start_streamlit.py
import subprocess
import sys
import os

os.chdir(r'C:\Users\lesson\OneDrive\Desktop\YIELD')
subprocess.run([
    sys.executable, '-m', 'streamlit',
    'run', 'app.py', '--server.port', '8501'
])