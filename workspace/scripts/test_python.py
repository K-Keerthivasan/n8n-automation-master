from pathlib import Path
import platform
import sys


print(f"python={sys.executable}")
print(f"version={platform.python_version()}")
print(f"cwd={Path.cwd()}")
