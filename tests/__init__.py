import os
import sys

os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

sys.path.append(os.path.join(os.path.dirname(__file__), "../cloudfunctions"))