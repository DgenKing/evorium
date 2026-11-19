"""Copy to config.py and fill in the key locally. Never commit config.py."""

DEEPSEEK_API_KEY = "sk-..."
DEEPSEEK_MODEL = "deepseek-flash"
# Verified 2026-11-19: https://api-docs.deepseek.com/quick_start/pricing/
# Peak rates, USD per million tokens. Off-peak (outside 01-04 and 06-10 UTC Mon-Fri) is half.
INPUT_USD_PER_MILLION = 0.30          # input, cache miss
CACHED_INPUT_USD_PER_MILLION = 0.006  # input, cache hit (repeated prompt start)
OUTPUT_USD_PER_MILLION = 1.20

# Local hard stop on new requests once estimated spend reaches this (USD).
MAX_SPEND_USD = 4.00

# Optional HTTP Basic password for every page, static asset and API route.
# Leave empty for local development. Restart after changing your local config.
DASHBOARD_PASSWORD = ""
