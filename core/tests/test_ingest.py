import os
import hmac
import hashlib
import base64
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.utils.dependencies import get_db
from contextlib import asynccontextmanager


async def mock_get_db():
    mock_session = AsyncMock()
    @asynccontextmanager
    async def mock_begin():
        yield
    mock_session.begin = mock_begin
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.execute.return_value = mock_result
    yield mock_session

app.dependency_overrides[get_db] = mock_get_db
client = TestClient(app)

@patch("api.routers.ingest.httpx.AsyncClient")
@patch.dict(os.environ, {"QSTASH_TOKEN": "mock", "PUBLIC_API_URL": "http://mock", "SHOPIFY_WEBHOOK_SECRET": "shop_secret"})
def test_ingest_shopify_valid_signature(mock_httpx_client):
    """_summary_

    Args:
        mock_httpx_client (_type_): _description_
    """    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

    payload = {"id": 12345, "email": "test@fucina.com", "total_price": "200.00", "currency": "USD", "line_items": [{}]}
    body_bytes = json.dumps(payload).encode("utf-8")
    signature = base64.b64encode(
        hmac.new(b"shop_secret", body_bytes, hashlib.sha256).digest()
    ).decode("utf-8")

    response = client.post(
        "/webhook/shopify",
        content=body_bytes,
        headers={"X-Shopify-Hmac-Sha256": signature, "X-Shopify-Shop-Domain": "store.com"}
    )
    
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    mock_httpx_client.return_value.__aenter__.return_value.post.assert_called_once()

@patch.dict(os.environ, {"SHOPIFY_WEBHOOK_SECRET": "shop_secret"})
def test_ingest_shopify_invalid_signature():
    """_summary_
    """    
    payload = {"id": 12345}
    body_bytes = json.dumps(payload).encode("utf-8")

    response = client.post(
        "/webhook/shopify",
        content=body_bytes,
        headers={"X-Shopify-Hmac-Sha256": "bad_signature", "X-Shopify-Shop-Domain": "store.com"}
    )
    
    assert response.status_code == 401
    assert "Invalid signature" in response.json()["detail"]

@patch.dict(os.environ, {"SHOPIFY_WEBHOOK_SECRET": "shop_secret"})
def test_ingest_shopify_ignores_missing_email():
    """_summary_
    """    
    payload = {"id": 12345, "email": "", "total_price": "200.00"}
    body_bytes = json.dumps(payload).encode("utf-8")
    
    signature = base64.b64encode(
        hmac.new(b"shop_secret", body_bytes, hashlib.sha256).digest()
    ).decode("utf-8")

    response = client.post(
        "/webhook/shopify",
        content=body_bytes,
        headers={"X-Shopify-Hmac-Sha256": signature, "X-Shopify-Shop-Domain": "store.com"}
    )
    
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"

@patch.dict(os.environ, {"TIENDANUBE_WEBHOOK_SECRET": "tn_secret"})
def test_ingest_tiendanube_invalid_json():
    """_summary_
    """    
    body_bytes = b"This is not a JSON"
    signature = hmac.new(b"tn_secret", body_bytes, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhook/tiendanube",
        content=body_bytes,
        headers={"X-Linked-Store-HMAC-SHA256": signature}
    )
    
    assert response.status_code == 400
    assert "Invalid JSON body" in response.json()["detail"]