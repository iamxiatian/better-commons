import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

HOME: Path = Path(os.getenv("MY_HOME", "."))
