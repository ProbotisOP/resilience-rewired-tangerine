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

# Ensure data directory exists
if not DATA_DIR.exists():
    # Fallback to local data/
    DATA_DIR = PROJECT_ROOT / "data"

# Application Metadata
APP_TITLE = "Resilience Rewired"
APP_SUBTITLE = "Financial Resilience Engine · Tangerine Track (Sheridan Datathon 2026)"
TEAM_NAME = "CTRL + ALT + WIN"
VERSION = "2.0.0"

# Design & Branding Theme (Tangerine Navy & Orange)
THEME = {
    "primary_orange": "#FF5B00",
    "secondary_orange": "#FF7A29",
    "dark_navy": "#0B132B",
    "card_bg": "#1C2541",
    "accent_blue": "#48E5C2",
    "alert_red": "#E63946",
    "success_green": "#2A9D8F",
    "text_main": "#F8F9FA",
    "text_muted": "#8D99AE",
    "border_color": "#3A4F7A"
}

# Default Business Parameters
DEFAULT_EMERGENCY_MONTHS = 3
MAX_RUNWAY_CAP = 120.0

# LLM Configuration (Gemini)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
