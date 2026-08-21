from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import List


class AbandonedCartData(BaseModel):
    """AbandonedCartData contains details of a user's abandoned checkout session.

    Args:
        customer_id: Customer ID or email in the e-commerce platform.
        cart_id: Unique identifier for the checkout session.
        total_value: Total monetary value of the items left in the cart.
        currency: Currency code (e.g: USD, EUR, ARS).
        customer_type: Classification of the user (e.g: new, returning, vip).
        margin_category: Overall margin classification of the cart items.
        items_count: Total quantity of items in the cart.
    """

    customer_id: str = Field(..., description="ID or email of the customer")
    cart_id: str = Field(..., description="Unique ID of the abandoned cart/checkout")
    total_value: float = Field(..., gt=0, description="Total cart value in currency")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="Currency code (e.g: USD, EUR)"
    )
    customer_type: str = Field(
        default="new", 
        pattern="^(new|returning|vip)$",
        description="Customer classification"
    )
    margin_category: str = Field(
        default="standard", 
        pattern="^(low|standard|high)$",
        description="Margin classification based on the cart's items"
    )
    items_count: int = Field(default=1, ge=1, description="Number of items abandoned")


class WebhookIngestPayload(BaseModel):
    """Payload for ingesting webhook events about abandoned carts.

    Attributes:
        event_id: Unique ID to avoid processing the same cart event twice.
        tenant_id: ID of the e-commerce client that owns the event.
        timestamp: Time when the cart was considered abandoned.
        data: AbandonedCartData with details about the checkout session.
    """

    event_id: str = Field(
        ...,
        description="Unique ID to avoid processing the same event twice (idempotency)",
    )
    tenant_id: str = Field(..., description="ID of our B2B customer (e-commerce)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: AbandonedCartData

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class MarginRulesConfig(BaseModel):
    """Configuration for dynamic discount and margin optimization rules.

    Attributes:
        max_discount_pct: Absolute maximum discount allowed to be offered.
        new_customer_discount: Aggressive discount used to acquire first-time buyers.
        low_margin_action: Action to take when the cart has a 'low' margin category.
        whale_threshold: Cart value threshold to trigger manual sales team alerts.
        grace_period_hours: Hours to wait before contacting the customer.
    """

    max_discount_pct: float = Field(
        default=0.15, ge=0.0, le=0.50, description="Max discount allowed (e.g. 0.15 for 15%)"
    )
    new_customer_discount: float = Field(
        default=0.15, ge=0.0, le=0.50, description="Discount exclusively for 'new' customers"
    )
    low_margin_action: str = Field(
        default="free_shipping",
        pattern="^(free_shipping|no_discount|fixed_amount)$",
        description="Safe action for carts with minimal profit margins",
    )
    whale_threshold: float = Field(
        default=500.0, ge=100.0, description="Cart value threshold to trigger VIP/Manual alerts"
    )
    grace_period_hours: int = Field(
        default=2, ge=1, le=72, description="Hours to wait before sending the recovery message"
    )


class TenantConfigPayload(BaseModel):
    """Tenant-specific margin optimization configuration payload.

    Attributes:
        tenant_id: B2B tenant identifier.
        is_active: Whether recovery automation is enabled for this tenant.
        rules: Margin rules configuration for the tenant.
    """

    tenant_id: str = Field(..., description="B2B tenant identifier")
    is_active: bool = Field(default=True)
    rules: MarginRulesConfig