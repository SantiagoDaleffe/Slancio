from typing import Protocol, Optional
from datetime import datetime, timedelta, timezone
from core.models import CartEvent, RecoveryAction, ActionType


class RecoveryRule(Protocol):
    """Define the interface implemented by cart recovery rules."""

    def evaluate(self, event: CartEvent) -> Optional[RecoveryAction]:
        """Evaluate an event and optionally return a recovery action.

        Args:
            event: The cart event to evaluate.

        Returns:
            A recovery action when the rule applies; otherwise, ``None``.
        """
        pass


class WhaleAlertRule:
    """Create an alert for carts whose value meets a configured threshold."""

    def __init__(self, threshold: float = 500.0):
        """Initialize the whale-cart threshold.

        Args:
            threshold: Minimum cart value that triggers an alert.
        """
        self.threshold = threshold

    def evaluate(self, event: CartEvent) -> Optional[RecoveryAction]:
        """Return a manual-follow-up alert for a qualifying cart.

        Args:
            event: The cart event to inspect.

        Returns:
            An alert action if the cart reaches the threshold; otherwise, ``None``.
        """
        if event.total_value >= self.threshold:
            return RecoveryAction(
                action_type=ActionType.ALERT,
                reason=f"Whale cart detected ({event.total_value} {event.currency}). Manual follow-up required.",
            )
        return None


class LowMarginRule:
    """Choose a margin-protecting action for low-margin carts."""

    def __init__(self, action_pref: str, delay_hours: int = 2):
        """Initialize the preferred action and scheduling delay.

        Args:
            action_pref: Preferred action, such as ``"free_shipping"``.
            delay_hours: Number of hours before a free-shipping action is sent.
        """
        self.action_pref = action_pref
        self.delay_hours = delay_hours

    def evaluate(self, event: CartEvent) -> Optional[RecoveryAction]:
        """Return a free-shipping or ignore action for low-margin carts.

        Args:
            event: The cart event to inspect.

        Returns:
            A margin-protecting action for a low-margin cart; otherwise, ``None``.
        """
        if event.margin_category == "low":
            send_at = datetime.now(timezone.utc) + timedelta(hours=self.delay_hours)

            if self.action_pref == "free_shipping":
                return RecoveryAction(
                    action_type=ActionType.FREE_SHIPPING,
                    scheduled_for=send_at,
                    reason="Low margin cart. Offering free shipping instead of % discount.",
                )

            return RecoveryAction(
                action_type=ActionType.IGNORE,
                reason="Low margin cart. Ignoring to protect profitability.",
            )
        return None


class NewCustomerRule:
    """Offer a discount to customers making their first purchase."""

    def __init__(self, discount_pct: float, delay_hours: int = 2):
        """Initialize the new-customer discount and scheduling delay.

        Args:
            discount_pct: Discount expressed as a decimal fraction, such as ``0.10``.
            delay_hours: Number of hours before the recovery message is sent.
        """
        self.discount_pct = discount_pct
        self.delay_hours = delay_hours

    def evaluate(self, event: CartEvent) -> Optional[RecoveryAction]:
        """Return a discount action for a new customer.

        Args:
            event: The cart event to inspect.

        Returns:
            A scheduled discount for a new customer; otherwise, ``None``.
        """
        if event.customer_type == "new":
            send_at = datetime.now(timezone.utc) + timedelta(hours=self.delay_hours)
            return RecoveryAction(
                action_type=ActionType.DISCOUNT,
                discount_pct=self.discount_pct,
                scheduled_for=send_at,
                reason=f"New customer acquisition. Offering {self.discount_pct * 100}% off.",
            )
        return None


class StandardRecoveryRule:
    """Apply the default recovery discount while protecting margins."""

    def __init__(self, max_discount: float, delay_hours: int = 2):
        """Initialize the capped discount and scheduling delay.

        Args:
            max_discount: Maximum discount as a decimal fraction.
            delay_hours: Number of hours before the recovery message is sent.
        """
        # We cap the standard discount at 5% to protect margins, or lower if max_discount is strict
        self.discount = min(max_discount, 0.05)
        self.delay_hours = delay_hours

    def evaluate(self, event: CartEvent) -> Optional[RecoveryAction]:
        """Return a scheduled standard discount action.

        Args:
            event: The cart event to evaluate.

        Returns:
            A scheduled discount action using the configured capped discount.
        """
        send_at = datetime.now(timezone.utc) + timedelta(hours=self.delay_hours)
        return RecoveryAction(
            action_type=ActionType.DISCOUNT,
            discount_pct=self.discount,
            scheduled_for=send_at,
            reason=f"Standard recovery logic. Offering {self.discount * 100}% off.",
        )
