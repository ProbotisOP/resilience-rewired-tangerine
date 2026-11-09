"""
Application Settings and Configuration for Resilience Rewired
Sheridan Datathon 2026 - Tangerine Track
"""

import os
from pathlib import Path

# Paths
CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent
DATA_DIR = PROJECT_ROOT / "tangerine" / "data"

if not DATA_DIR.exists():
    DATA_DIR = PROJECT_ROOT / "data"

# Application Metadata
APP_TITLE = "Resilience Rewired"
APP_SUBTITLE = "Financial Resilience Intelligence Platform · Tangerine Track (Sheridan Datathon 2026)"
TEAM_NAME = "CTRL + ALT + WIN"
VERSION = "3.0.0 (Snowflake Native)"

# Design & Branding Theme (Tangerine High-Contrast Orange, White & Charcoal)
THEME = {
    "primary_orange": "#FF5B00",
    "secondary_orange": "#FF7A29",
    "dark_charcoal": "#1A1D20",
    "card_bg": "#25292D",
    "card_border": "#3A4149",
    "accent_blue": "#00B4D8",
    "alert_red": "#E63946",
    "success_green": "#2A9D8F",
    "text_main": "#FFFFFF",
    "text_muted": "#A0AAB5",
    "border_color": "#3A4149"
}

# Default Business Parameters
DEFAULT_EMERGENCY_MONTHS = 3
MAX_RUNWAY_CAP = 120.0

# Snowflake Connection Defaults
SNOWFLAKE_DATABASE = "RESILIENCE_REWIRED_DB"
SNOWFLAKE_WAREHOUSE = "RR_WH"
