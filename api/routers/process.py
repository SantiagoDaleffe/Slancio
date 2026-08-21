import os
import json
import uuid
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from qstash import Receiver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from api.utils.dependencies import get_db
from api.utils.logger import logger, trace_id_var

from core.engine import MarginEngine
from core.rules import (
    WhaleAlertRule,
    LowMarginRule,
    NewCustomerRule,
    StandardRecoveryRule,
)
from core.models import CartEvent, ActionType

router = APIRouter()

qstash_receiver = Receiver(
    current_signing_key=os.environ["QSTASH_CURRENT_SIGNING_KEY"],
    next_signing_key=os.environ["QSTASH_NEXT_SIGNING_KEY"],
)


@router.post("/process", status_code=200)
async def process_event(request: Request, db: AsyncSession = Depends(get_db)):
    """Process a signed abandoned-cart event and schedule its recovery action.

    Args:
        request: Incoming HTTP request containing the QStash signature and event
            payload.
        db: Database session used to load tenant configuration and persist
            scheduled recoveries. Defaults to ``Depends(get_db)``.

    Raises:
        HTTPException: If the QStash signature is missing or invalid, the
            request body is not valid JSON, or processing fails.

    Returns:
        A status dictionary describing whether the event was ignored or
        processed and, when applicable, the selected recovery decision.
    """
    signature = request.headers.get("Upstash-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Signature missing")

    body_bytes = await request.body()
    try:
        qstash_receiver.verify(body=body_bytes.decode("utf-8"), signature=signature)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid QStash signature")

    try:
        trace_id = request.headers.get("Upstash-Trace-Id", trace_id_var.get())
        trace_id_var.set(trace_id)

        try:
            payload = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        event_id = payload.get("event_id")
        tenant_id = payload.get("tenant_id")
        cart_data = payload.get("data", {})

        logger.info(f"[Trace: {trace_id}] Processing abandoned cart {event_id}.")

        async with db.begin():
            result = await db.execute(
                text(
                    "SELECT margin_rules FROM slancio_tenant_configs WHERE tenant_id = :tenant_id AND is_active = true"
                ),
                {"tenant_id": tenant_id},
            )
            config_row = result.first()

        if not config_row:
            logger.warning(
                f"[Trace: {trace_id}] Tenant {tenant_id} not active. Ignoring."
            )
            return {"status": "ignored", "reason": "Tenant inactive"}

        rules_json = config_row[0]

        margin_engine = MarginEngine(
            rules=[
                WhaleAlertRule(threshold=rules_json.get("whale_threshold", 500.0)),
                LowMarginRule(
                    action_pref=rules_json.get("low_margin_action", "free_shipping"),
                    delay_hours=rules_json.get("grace_period_hours", 2),
                ),
                NewCustomerRule(
                    discount_pct=rules_json.get("new_customer_discount", 0.15),
                    delay_hours=rules_json.get("grace_period_hours", 2),
                ),
                StandardRecoveryRule(
                    max_discount=rules_json.get("max_discount_pct", 0.05),
                    delay_hours=rules_json.get("grace_period_hours", 2),
                ),
            ]
        )

        cart_event = CartEvent(
            event_id=event_id,
            tenant_id=tenant_id,
            cart_id=cart_data.get("cart_id"),
            total_value=cart_data.get("total_value"),
            customer_type=cart_data.get("customer_type"),
            margin_category=cart_data.get("margin_category"),
            currency=cart_data.get("currency", "USD"),
        )

        decision = margin_engine.process(cart_event)
        logger.info(
            f"[Trace: {trace_id}] Decision: {decision.action_type.name} - {decision.reason}"
        )

        if decision.action_type == ActionType.IGNORE:
            return {"status": "ignored", "reason": decision.reason}

        if decision.scheduled_for:
            async with db.begin():
                await db.execute(
                    text("""
                        INSERT INTO slancio_scheduled_recovery (id, tenant_id, event_id, execute_at, payment_data, status, created_at)
                        VALUES (:id, :tenant_id, :event_id, :execute_at, CAST(:payment_data AS JSON), :status, NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "tenant_id": cart_event.tenant_id,
                        "event_id": cart_event.event_id,
                        "execute_at": decision.scheduled_for,
                        "payment_data": json.dumps(
                            {"payload": payload, "discount_pct": decision.discount_pct}
                        ),
                        "status": "PENDING",
                    },
                )

            qstash_token = os.environ["QSTASH_TOKEN"]
            api_url = os.environ["PUBLIC_API_URL"]
            unix_timestamp = str(int(decision.scheduled_for.timestamp()))

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://qstash-us-east-1.upstash.io/v2/publish/{api_url}/webhook/execute-recovery",
                    headers={
                        "Authorization": f"Bearer {qstash_token}",
                        "Content-Type": "application/json",
                        "Upstash-Not-Before": unix_timestamp,
                        "Upstash-Trace-Id": trace_id,
                    },
                    json={"event_id": event_id, "tenant_id": cart_event.tenant_id},
                )

        return {"status": "processed", "decision": decision.action_type.name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Trace: {trace_id_var.get()}] Error processing: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
