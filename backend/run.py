import sys
import os
from pathlib import Path
import uvicorn

# Ensure the root directory of the project is in Python path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

os.environ["PYTHONPATH"] = str(root_dir)

if __name__ == "__main__":
    print("Starting AI-Powered Student Skill Intelligence Platform Backend...")
    print("API Documentation available at: http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
