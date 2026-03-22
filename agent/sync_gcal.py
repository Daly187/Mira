"""
Sync Google Calendar events to local cache.
Run periodically or before dashboard refresh.
On Mac: uses MCP Google Calendar connection.
On Windows: will use Google Calendar API directly (Phase 6).

For now, this script is meant to be run manually or via the MCP tools
to populate agent/data/gcal_cache.json
"""

import json
from pathlib import Path
from config import Config

Config.ensure_dirs()

# This file gets populated by the MCP gcal tool or by the PA module
cache_path = Config.DATA_DIR / "gcal_cache.json"

print(f"Google Calendar cache location: {cache_path}")
print("To populate: use the gcal_list_events MCP tool and save events to this file.")
print("The dashboard API reads from this file automatically.")
