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

# Optional HTTP Basic access control for every page, static asset and API route.
# Leave empty for local development. Restart after changing your local config.
DASHBOARD_PASSWORD = ""

# M4: reaction calls across the world per sim day (1–12; higher values stay capped at 12).
REACTION_CALLS_PER_DAY = 12
# Catch-up narration is at most once per sim day and once per real ten minutes.
# Increase this to wait longer between calls; values below 600 are capped at 600.
CATCHUP_COOLDOWN_SECONDS = 600
