from typing import List
from core.models import CartEvent, RecoveryAction, ActionType
from core.rules import RecoveryRule


class MarginEngine:
    """Evaluate cart events against recovery rules."""

    def __init__(self, rules: List[RecoveryRule]):
        """Initialize the engine with an ordered collection of recovery rules.

        Args:
            rules: Rules evaluated in order until one returns a recovery action.
        """
        self.rules = rules

    def process(self, event: CartEvent) -> RecoveryAction:
        """Process a cart event and return the first applicable recovery action.

        Args:
            event: Cart event to evaluate against the configured rules.

        Returns:
            The action returned by the first matching rule, or an ignore action
            when no rule applies.
        """
        for rule in self.rules:
            decision = rule.evaluate(event)
            if decision is not None:
                return decision

        return RecoveryAction(
            action_type=ActionType.IGNORE,
            reason="Fallback: Cart did not qualify for any recovery action.",
        )
