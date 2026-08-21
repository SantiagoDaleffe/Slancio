from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ActionType(Enum):
    """Types of actions that can be recommended for an abandoned cart."""

    DISCOUNT = "DISCOUNT"
    FREE_SHIPPING = "FREE_SHIPPING"
    ALERT = "ALERT"
    IGNORE = "IGNORE"


@dataclass
class CartEvent:
    """Represents an abandoned checkout event internally."""

    event_id: str
    tenant_id: str
    cart_id: str
    total_value: float
    customer_type: str
    margin_category: str
    currency: str = "USD"
    items_count: int = 1


@dataclass
class RecoveryAction:
    """Represents the suggested action to recover the cart while preserving margin."""

    action_type: ActionType
    reason: str
    discount_pct: float = 0.0
    scheduled_for: Optional[datetime] = None
