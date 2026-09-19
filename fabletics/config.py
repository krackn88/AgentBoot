BASE_URL = "https://app.fabletics.com"
API_KEY = "EdbjQ1gNMv9gkvV9Km8U82Rsxzo2zJ5f9shviDGH"
STORE_DOMAIN = "app.fabletics.com"

APP_NATIVE_VERSION = "2.3.0"
APP_JS_VERSION = "1789761619"
APP_PLATFORM = "ios"

# curl_cffi TLS + HTTP/2 fingerprint (real HTTPS, not plain Python requests).
TLS_IMPERSONATE = "safari17_2_ios"

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    f"FableticsApp/{APP_NATIVE_VERSION}-/{APP_JS_VERSION}"
)

DEFAULT_TIMEOUT = 30

# Cloudflare Turnstile — required for login (sent as reCaptchaResponse in API).
# Set TURNSTILE_SITE_KEY in .env (extract from the mobile app / Charles capture).
TURNSTILE_SITE_KEY = ""
TURNSTILE_PAGE_URL = "https://app.fabletics.com/"
TURNSTILE_ACTION = "login"

# Legacy reCAPTCHA fallback if Turnstile site key is not configured.
RECAPTCHA_SITE_KEY = "6LfUn5IUAAAAAM7ssrSkY6BVkNHIPaweAXxTy-eO"
RECAPTCHA_ACTION = "login"

# Per-check delay jitter (seconds) to avoid hammering the same gateway IP.
CHECK_DELAY_MIN = 0.35
CHECK_DELAY_MAX = 1.1

# Evomi residential proxy (US). Override with FABLETICS_PROXY env or --proxy.
DEFAULT_PROXY = (
    "http://gulley886:tStXC3zZrqpDmVdVQdzF_country-US"
    "@core-residential.evomi.com:1000"
)
