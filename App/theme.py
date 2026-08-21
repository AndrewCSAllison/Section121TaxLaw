import platform

# ──────────────────────────────────────────────
#  SYSTEM DETECTION
# ──────────────────────────────────────────────

IS_MAC = platform.system() == "Darwin"

# ──────────────────────────────────────────────
#  THEME — Colors
# ──────────────────────────────────────────────

BG          = "#1C1E26"  # Main window background
PANEL       = "#242633"  # Secondary containers (Editor/Output)
BORDER      = "#2E3147"  # Borders and separators
ACCENT      = "#5B8AF5"  # Primary blue (Buttons/Active states)
ACCENT2     = "#A78BFA"  # Purple (Hover states/Secondary actions)
SUCCESS     = "#4ADE80"  # Green
WARNING     = "#FACC15"  # Yellow
ERROR_COL   = "#F87171"  # Red
TEXT        = "#E8EAF0"  # Primary white text
SUBTEXT     = "#8B90A8"  # Muted grey text

# Interaction Derivatives
ACCENT_HOVER = "#4876D6"
PANEL_HOVER  = "#2E3147"

# ──────────────────────────────────────────────
#  THEME — Fonts
# ──────────────────────────────────────────────

FONT_FAMILY = "Helvetica Neue" if IS_MAC else "Segoe UI"
MONO_FAMILY = "Menlo" if IS_MAC else "Consolas"

FONT_UI    = (FONT_FAMILY, 10)
FONT_HEAD  = (FONT_FAMILY, 11, "bold") 
FONT_MONO  = (MONO_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 8, "bold")

# ──────────────────────────────────────────────
#  GLOBAL WIDGET CONFIGURATION
# ──────────────────────────────────────────────

# A dictionary to unpack into widgets using **WIDGET_CONFIG
WIDGET_CONFIG = {
    "bg": BG,
    "fg": TEXT,
    "insertbackground": TEXT,      # Fixes invisible cursor in dark mode
    "selectbackground": ACCENT,    # Text highlight color
    "selectforeground": "#FFFFFF", 
    "highlightthickness": 0,       # Removes native system focus ring
    "relief": "flat",              # Removes 3D sunken borders
    "padx": 10,
    "pady": 10
}