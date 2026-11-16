"""Copy to config.py and fill in the key locally. Never commit config.py."""

DEEPSEEK_API_KEY = "sk-..."
DEEPSEEK_MODEL = "deepseek-flash"
# Verified 2026-11-15: https://api-docs.deepseek.com/quick_start/pricing/
# Conservative peak, uncached rates, USD per million tokens.
INPUT_USD_PER_MILLION = 0.30
OUTPUT_USD_PER_MILLION = 1.20

# Local hard stop on new requests once estimated spend reaches this (USD).
MAX_SPEND_USD = 4.00

# Optional HTTP Basic password for every page, static asset and API route.
# Leave empty for local development. Restart after changing your local config.
DASHBOARD_PASSWORD = ""
