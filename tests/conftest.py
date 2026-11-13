import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Keep imports of src.config free of side effects on the real data directory.
os.environ.setdefault("DB_TYPE", "mysql")
