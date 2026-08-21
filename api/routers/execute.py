from datetime import datetime
import os
import uuid
import httpx
import secrets

from fastapi import APIRouter, Request, Depends, HTTPException
from qstash import Receiver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils.logger import logger, trace_id_var
from api.utils.dependencies import get_db

router = APIRouter()
qstash_receiver = Receiver(
    current_signing_key=os.environ["QSTASH_CURRENT_SIGNING_KEY"],
    next_signing_key=os.environ["QSTASH_NEXT_SIGNING_KEY"],
)


def mask_email(email: str) -> str:
    """_summary_

    Args:
        email (str): _description_

    Returns:
        str: _description_
    """
    if not email or "@" not in email:
        return "unknown_email"
    name, domain = email.split("@")
    return f"{name[0]}***@{domain}"


@router.post("/execute-recovery", status_code=200)
async def execute_recovery(request: Request, db: AsyncSession = Depends(get_db)):
    """Execute a pending cart recovery received from QStash.

    The request signature is verified before the recovery is loaded and
    processed. If the recovery is missing or has already been executed, the
    operation is skipped. Otherwise, a simulated coupon is generated, the
    recovery status is updated, and the payment data is cleared.

    Args:
        request (Request): Incoming QStash request containing the recovery
            event payload and signature header.
        db (AsyncSession, optional): Database session used to retrieve and
            update the scheduled recovery. Defaults to Depends(get_db).

    Raises:
        HTTPException: If the QStash signature is missing or invalid.
        HTTPException: If the stored recovery data has an invalid structure.
        HTTPException: If an unexpected error occurs while executing the
            recovery.

    Returns:
        dict: A status response containing the event ID and recovery action.
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
        payload = await request.json()
        event_id = payload.get("event_id")
        tenant_id = payload.get("tenant_id")
        trace_id = trace_id_var.get()

        logger.info(f"[Trace: {trace_id}] Executing cart recovery for {event_id}")

        async with db.begin():
            result = await db.execute(
                text(
                    "SELECT payment_data FROM scheduled_recoveries WHERE event_id = :event_id AND status = 'PENDING'"
                ),
                {"event_id": event_id},
            )
            row = result.first()

            if not row:
                logger.warning(
                    f"[Trace: {trace_id}] Recovery for {event_id} not found or already executed."
                )
                return {"status": "skipped"}

            recovery_data = row[0]
            if not isinstance(recovery_data, dict):
                logger.error(
                    f"[Trace: {trace_id}] recovery_data is not a valid dictionary"
                )
                raise HTTPException(
                    status_code=500, detail="Invalid recovery data structure"
                )

            original_payload = recovery_data.get("payload", {}).get("data", {})
            discount_pct = recovery_data.get("discount_pct", 0)

            customer_id = original_payload.get("customer_id")
            cart_id = original_payload.get("cart_id")

            try:
                secure_suffix = secrets.token_hex(3).upper()
                coupon_code = f"SLANCIO-{int(discount_pct * 100)}OFF-{secure_suffix}"

                logger.info(
                    f"[Trace: {trace_id}] [SIMULATION] Created unique coupon {coupon_code} for cart {cart_id}"
                )

                safe_email = mask_email(customer_id)
                logger.info(
                    f"[Trace: {trace_id}] [SIMULATION] Sending email to {safe_email} with coupon"
                )

                final_status = "SUCCESS"

            except Exception as e:
                logger.error(
                    f"[Trace: {trace_id}] Error executing recovery for event {event_id}: {str(e)}"
                )
                final_status = "ERROR"

            await db.execute(
                text("""
                    UPDATE scheduled_recoveries 
                    SET status = :status, payment_data = '{}'::jsonb 
                    WHERE event_id = :event_id
                """),
                {"status": final_status, "event_id": event_id},
            )

        return {"status": "success", "event_id": event_id, "action": "email_sent"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[Trace: {trace_id_var.get()}] Unexpected error in execute: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
