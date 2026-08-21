import os
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

@patch("api.routers.process.httpx.AsyncClient")
@patch("api.routers.process.qstash_receiver")
@patch.dict(os.environ, {"QSTASH_TOKEN": "mock", "PUBLIC_API_URL": "http://mock", "QSTASH_CURRENT_SIGNING_KEY": "c", "QSTASH_NEXT_SIGNING_KEY": "n"})
def test_process_event_inactive_tenant(mock_receiver, mock_httpx_client):
    # Simulamos validación exitosa de QStash
    mock_receiver.verify.return_value = True

    # Mock de DB
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None # Tenant inactivo o no existe
    mock_db.execute.return_value = mock_result
    app.dependency_overrides["get_db"] = lambda: mock_db

    payload = {
        "event_id": "evt_1",
        "tenant_id": "t_1",
        "data": {"cart_id": "c1", "total_value": 100, "customer_type": "new", "margin_category": "high"}
    }
    
    response = client.post(
        "/webhook/process",
        json=payload,
        headers={"Upstash-Signature": "valid_sig"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert "Tenant inactive" in response.json()["reason"]


@pytest.mark.asyncio
@patch("api.routers.process.httpx.AsyncClient")
@patch("api.routers.process.qstash_receiver")
@patch.dict(os.environ, {"QSTASH_TOKEN": "mock", "PUBLIC_API_URL": "http://mock", "QSTASH_CURRENT_SIGNING_KEY": "c", "QSTASH_NEXT_SIGNING_KEY": "n"})
async def test_process_event_schedules_recovery(mock_receiver, mock_httpx_client):
    mock_receiver.verify.return_value = True
    
    # Simulamos respuesta exitosa de post a QStash
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_http_resp

    mock_db = AsyncMock()
    mock_result = MagicMock()
    # Retornamos reglas de tenant válidas (Low margin prefiere ignore)
    mock_result.first.return_value = ({"low_margin_action": "ignore"},)
    mock_db.execute.return_value = mock_result
    
    # Creamos un ContextManager asíncrono básico para el mock_db.begin()
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def mock_begin():
        yield
    mock_db.begin = mock_begin

    # Evento de margen bajo
    payload = {
        "event_id": "evt_1",
        "tenant_id": "t_1",
        "data": {"cart_id": "c1", "total_value": 100, "customer_type": "new", "margin_category": "low"}
    }
    
    from api.routers.process import process_event
    from fastapi import Request
    
    mock_request = AsyncMock(spec=Request)
    mock_request.headers = {"Upstash-Signature": "valid_sig"}
    mock_request.body.return_value = json.dumps(payload).encode("utf-8")
    mock_request.json.return_value = payload

    response = await process_event(mock_request, db=mock_db)
    
    # Según la regla, si preferimos ignore para low margin, debe retornar IGNORE
    assert response["status"] == "ignored"
    assert "Ignoring to protect profitability" in response["reason"]