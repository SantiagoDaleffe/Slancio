import os
import httpx
import hmac
import hashlib
import json
import base64
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.utils.dependencies import get_db
from api.utils.logger import logger, trace_id_var
from api.utils.schemas import WebhookIngestPayload, AbandonedCartData
from api.utils.security import limiter, verify_api_key, verify_webhook_signature

router = APIRouter()


@router.post(
    "/ingest",
    status_code=202,
    dependencies=[Depends(verify_api_key), Depends(verify_webhook_signature)],
)
@limiter.limit("50/minute")
async def ingest_webhook(
    request: Request, payload: WebhookIngestPayload, db: AsyncSession = Depends(get_db)
):
    """Accept a webhook event and enqueue it for asynchronous processing.

    Duplicate events are detected before publishing so that an event is not
    processed more than once. New events are sent to the QStash queue.

    Args:
        request: The incoming FastAPI request.
        payload: The webhook event to process.
        db: The database session used to check for duplicate events.

    Raises:
        HTTPException: If QStash communication fails or an internal error
            occurs.

    Returns:
        A dictionary acknowledging the event, including its processing status
        and trace ID. Duplicate events also include a note indicating that
        they were already processed.
    """
    try:
        async with db.begin():
            result = await db.execute(
                text(
                    "SELECT 1 FROM scheduled_recoveries WHERE event_id = :event_id LIMIT 1"
                ),
                {"event_id": payload.event_id},
            )
        if result.first():
            logger.warning(f"Cart event {payload.event_id} duplicated. Ignoring.")
            return {
                "status": "accepted",
                "trace_id": trace_id_var.get(),
                "note": "Already processed",
            }

        logger.info(f"Cart event {payload.event_id} accepted. Sending to QStash queue.")

        qstash_token = os.environ["QSTASH_TOKEN"]
        api_url = os.environ["PUBLIC_API_URL"]
        trace_id = trace_id_var.get()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://qstash-us-east-1.upstash.io/v2/publish/{api_url}/webhook/process",
                headers={
                    "Authorization": f"Bearer {qstash_token}",
                    "Content-Type": "application/json",
                    "Upstash-Trace-Id": trace_id,
                },
                json=payload.model_dump(mode="json"),
            )
            if response.status_code >= 400:
                logger.error(f"[Trace: {trace_id}] QStash API Error: {response.text}")
                raise HTTPException(
                    status_code=500, detail="Error communicating with message broker"
                )

        return {"status": "accepted", "trace_id": trace_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Trace: {trace_id_var.get()}] Error in ingest_webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _enqueue_to_qstash(payload: WebhookIngestPayload, db: AsyncSession):
    """Check for duplicate events and enqueue new events in QStash.

    Args:
        payload: The webhook event to enqueue.
        db: The database session used to check for duplicate events.

    Raises:
        HTTPException: If QStash communication fails or an internal error
            occurs.

    Returns:
        A dictionary acknowledging the event. Duplicate events include a note
        indicating that they were already processed.
    """
    try:
        async with db.begin():
            result = await db.execute(
                text(
                    "SELECT 1 FROM scheduled_recoveries WHERE event_id = :event_id LIMIT 1"
                ),
                {"event_id": payload.event_id},
            )
        if result.first():
            logger.warning(f"Cart event {payload.event_id} duplicated. Ignoring.")
            return {"status": "accepted", "note": "Already processed"}

        logger.info(f"Cart event {payload.event_id} accepted. Sending to QStash queue.")

        qstash_token = os.environ["QSTASH_TOKEN"]
        api_url = os.environ["PUBLIC_API_URL"]
        trace_id = trace_id_var.get()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://qstash-us-east-1.upstash.io/v2/publish/{api_url}/webhook/process",
                headers={
                    "Authorization": f"Bearer {qstash_token}",
                    "Content-Type": "application/json",
                    "Upstash-Trace-Id": trace_id,
                },
                json=payload.model_dump(mode="json"),
            )
            if response.status_code >= 400:
                logger.error(f"[Trace: {trace_id}] QStash API Error: {response.text}")
                raise HTTPException(
                    status_code=500, detail="Error communicating with message broker"
                )

        return {"status": "accepted", "trace_id": trace_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[Trace: {trace_id_var.get()}] Error in _enqueue_to_qstash: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ingest", status_code=202, dependencies=[Depends(verify_api_key)])
@limiter.limit("50/minute")
async def ingest_generic(
    request: Request, payload: WebhookIngestPayload, db: AsyncSession = Depends(get_db)
):
    """Accept a pre-formatted Slancio payload and enqueue it in QStash.

    Args:
        request: The incoming FastAPI request.
        payload: The webhook event formatted according to Slancio's internal
            schema.
        db: The database session used to check for duplicate events.

    Raises:
        HTTPException: If QStash communication fails or an internal error
            occurs.

    Returns:
        A dictionary acknowledging the event. Duplicate events include a note
        indicating that they were already processed.
    """
    try:
        return await _enqueue_to_qstash(payload, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Trace: {trace_id_var.get()}] Error in ingest_generic: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shopify", status_code=202)
async def ingest_shopify(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_shop_domain: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Validate and enqueue a Shopify webhook for asynchronous processing.

    The request body is verified using Shopify's HMAC signature before it is
    parsed or submitted for processing. Invalid or missing signatures and
    malformed JSON result in an HTTP error response.

    Args:
        request: Incoming Shopify webhook request.
        x_shopify_hmac_sha256: HMAC-SHA256 signature supplied by Shopify.
        x_shopify_shop_domain: Shopify shop domain supplied with the webhook.
        db: Database session used while enqueueing the webhook.

    Raises:
        HTTPException: If the signature is missing or invalid, the request body
            is not valid JSON, or enqueueing the webhook fails.

    Returns:
        A dictionary acknowledging the accepted Shopify webhook.
    """
    try:
        if not x_shopify_hmac_sha256:
            raise HTTPException(status_code=401, detail="Missing Shopify signature")

        raw_body = await request.body()
        shopify_secret = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")

        expected_sig_bytes = hmac.new(
            shopify_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).digest()
        expected_sig = base64.b64encode(expected_sig_bytes).decode("utf-8")

        if not hmac.compare_digest(expected_sig, x_shopify_hmac_sha256):
            logger.warning(
                f"Invalid Shopify signature for shop {x_shopify_shop_domain}"
            )
            raise HTTPException(status_code=401, detail="Invalid signature")

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        cart_id = str(data.get("id", ""))
        customer_email = data.get("email", "")
        total_price = float(data.get("total_price", 0.0))
        currency = data.get("currency", "USD")
        items_count = len(data.get("line_items", []))

        tenant_id = x_shopify_shop_domain or "unknown_shopify_store"

        if not customer_email or total_price <= 0:
            logger.info("Ignoring checkout without email or zero value.")
            return {"status": "ignored", "reason": "No email or zero value"}

        slancio_payload = WebhookIngestPayload(
            event_id=f"evt_shp_{cart_id}",
            tenant_id=tenant_id,
            data=AbandonedCartData(
                customer_id=customer_email,
                cart_id=cart_id,
                total_value=total_price,
                currency=currency,
                customer_type="new",
                margin_category="standard",
                items_count=items_count,
            ),
        )

        return await _enqueue_to_qstash(slancio_payload, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Trace: {trace_id_var.get()}] Error in ingest_shopify: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/tiendanube", status_code=202)
async def ingest_tiendanube(
    request: Request,
    x_linked_store_hmac_sha256: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Validate and enqueue a Tiendanube webhook payload.

    The request body is authenticated with the configured Tiendanube webhook
    secret, parsed as JSON, converted to the internal abandoned-cart payload,
    and sent to the queue for asynchronous processing.

    Args:
        request: Incoming Tiendanube webhook request.
        x_linked_store_hmac_sha256: HMAC-SHA256 signature supplied by
            Tiendanube in the request headers.
        db: Database session used while enqueueing the payload.

    Raises:
        HTTPException: If the signature is missing or invalid, the request body
            is not valid JSON, or an internal error occurs.

    Returns:
        The result of enqueueing the webhook payload.
    """
    try:
        if not x_linked_store_hmac_sha256:
            raise HTTPException(status_code=401, detail="Missing Tiendanube signature")

        raw_body = await request.body()
        tiendanube_secret = os.environ.get("TIENDANUBE_WEBHOOK_SECRET", "")

        expected_sig = hmac.new(
            tiendanube_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, x_linked_store_hmac_sha256):
            logger.warning("Invalid Tiendanube signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        store_id = str(data.get("store_id", ""))
        checkout = data.get("checkout", {})

        cart_id = str(checkout.get("id", ""))
        customer_email = checkout.get("customer", {}).get("email", "")
        total_price = float(checkout.get("total", 0.0))
        currency = checkout.get("currency", "ARS")
        items_count = len(checkout.get("products", []))

        tenant_id = f"tn_{store_id}"

        if not customer_email or total_price <= 0:
            logger.info("Ignoring checkout without email or zero value.")
            return {"status": "ignored", "reason": "No email or zero value"}

        slancio_payload = WebhookIngestPayload(
            event_id=f"evt_tn_{cart_id}",
            tenant_id=tenant_id,
            data=AbandonedCartData(
                customer_id=customer_email,
                cart_id=cart_id,
                total_value=total_price,
                currency=currency,
                customer_type="new",
                margin_category="standard",
                items_count=items_count,
            ),
        )

        return await _enqueue_to_qstash(slancio_payload, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[Trace: {trace_id_var.get()}] Error in ingest_tiendanube: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
