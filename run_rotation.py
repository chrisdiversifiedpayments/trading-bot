"""Run the weekly top-risers bot once (paper only). Usage: python run_rotation.py [--dry-run]

--dry-run shows what it would sell and buy without sending orders or saving anything."""
import json
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from bot.config import api_keys, load_settings
from bot.rotation import AlpacaBroker, load_rotation_settings, load_state, run_week, save_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
dry = "--dry-run" in sys.argv
s = load_settings()  # refuses anything but paper mode
r = load_rotation_settings()
state = load_state()
today = datetime.now(ZoneInfo("America/New_York")).date()
out = run_week(AlpacaBroker(*api_keys()), r, s.enabled, today, state, dry_run=dry)
if out.get("done") and not dry:
    save_state(state)
print(json.dumps(out, indent=2, default=str))
