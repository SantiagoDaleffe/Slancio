import pytest
from datetime import datetime, timezone, timedelta
from core.rules import WhaleAlertRule, LowMarginRule, NewCustomerRule, StandardRecoveryRule
from core.models import CartEvent, ActionType

def test_whale_alert_rule_triggers_on_high_value():
    rule = WhaleAlertRule(threshold=1000.0)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=1200.0, customer_type="returning", margin_category="high")
    
    action = rule.evaluate(event)
    assert action is not None
    assert action.action_type == ActionType.ALERT
    assert "Whale cart detected" in action.reason

def test_whale_alert_rule_ignores_normal_value():
    rule = WhaleAlertRule(threshold=1000.0)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=400.0, customer_type="returning", margin_category="high")
    
    assert rule.evaluate(event) is None

def test_low_margin_rule_offers_free_shipping():
    rule = LowMarginRule(action_pref="free_shipping", delay_hours=2)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=100.0, customer_type="new", margin_category="low")
    
    action = rule.evaluate(event)
    assert action is not None
    assert action.action_type == ActionType.FREE_SHIPPING
    assert action.discount_pct == 0.0 # No discount, only shipping

def test_low_margin_rule_ignores_if_configured():
    rule = LowMarginRule(action_pref="ignore", delay_hours=2)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=100.0, customer_type="new", margin_category="low")
    
    action = rule.evaluate(event)
    assert action is not None
    assert action.action_type == ActionType.IGNORE

def test_new_customer_rule_applies_discount():
    rule = NewCustomerRule(discount_pct=0.20, delay_hours=1)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=150.0, customer_type="new", margin_category="standard")
    
    action = rule.evaluate(event)
    assert action is not None
    assert action.action_type == ActionType.DISCOUNT
    assert action.discount_pct == 0.20

def test_standard_recovery_rule_caps_discount():
    # If max_discount is high, standard rule still caps at 5% implicitly (as defined in our business logic)
    rule = StandardRecoveryRule(max_discount=0.50, delay_hours=2)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=100.0, customer_type="returning", margin_category="standard")
    
    action = rule.evaluate(event)
    assert action is not None
    assert action.action_type == ActionType.DISCOUNT
    assert action.discount_pct == 0.05

def test_standard_recovery_rule_respects_strict_max_discount():
    # If max_discount is strictly lower than 5%, it respects it
    rule = StandardRecoveryRule(max_discount=0.02, delay_hours=2)
    event = CartEvent(event_id="e1", tenant_id="t1", cart_id="c1", total_value=100.0, customer_type="returning", margin_category="standard")
    
    action = rule.evaluate(event)
    assert action is not None
    assert action.action_type == ActionType.DISCOUNT
    assert action.discount_pct == 0.02