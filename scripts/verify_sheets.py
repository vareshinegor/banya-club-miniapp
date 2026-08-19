import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from constants import SHEET_ACHIEVEMENTS, SHEET_EVENTS, SHEET_MATERIALS, SHEET_SIGNUPS, SHEET_USERS
from sheets_client import get_spreadsheet

spreadsheet = get_spreadsheet()
for name in [SHEET_USERS, SHEET_EVENTS, SHEET_SIGNUPS, SHEET_MATERIALS, SHEET_ACHIEVEMENTS]:
    ws = spreadsheet.worksheet(name)
    print(name, "->", ws.row_values(1))
