"""Shared constants for Southwest mobile API."""

BASE_URL = "https://mobile.southwest.com"
TOKEN_PATH = "/api/security/v4/security/token"
INIT_PATH = "/sw_check/ios/init"
CLIENT_ID = "26f1ee9f-a921-4735-8f5d-856401d6656a"
API_KEY = "l7xx3386def1284d487ca8cb3aa80729d766"
HEADER_FAMILY = "X-dUblrIiu"

DEFAULT_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Southwest/13.20.2 CFNetwork/3860.700.2 Darwin/25.6.0",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-API-Key": API_KEY,
    "X-Channel-ID": "IOS",
    "x-app-version": "iOS_13.20.2",
}
