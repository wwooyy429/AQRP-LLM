from pathlib import Path
import os
Path(os.environ["WR29_MALICIOUS_USED"]).write_text("imported",encoding="utf-8")
raise RuntimeError("malicious factory imported")
