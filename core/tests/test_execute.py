import os
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import Request
from api.routers.execute import execute_recovery

@pytest.mark.asyncio
@patch("api.routers.execute.qstash_receiver")
@patch.dict(os.environ, {"QSTASH_CURRENT_SIGNING_KEY": "c", "QSTASH_NEXT_SIGNING_KEY": "n"})
async def test_execute_recovery_success_and_masks_data(mock_receiver):
    mock_receiver.verify.return_value = True

    mock_db = AsyncMock()
    mock_result = MagicMock()
    # Retornamos el payload tal cual está guardado en DB
    db_payload = {"payload": {"data": {"customer_id": "test@fucina.com", "cart_id": "c1"}}, "discount_pct": 0.15}
    mock_result.first.return_value = (db_payload,)
    mock_db.execute.return_value = mock_result

    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def mock_begin():
        yield
    mock_db.begin = mock_begin

    mock_request = AsyncMock(spec=Request)
    mock_request.headers = {"Upstash-Signature": "valid_sig"}
    mock_request.body.return_value = b'{"event_id": "evt_1", "tenant_id": "t1"}'
    mock_request.json.return_value = {"event_id": "evt_1", "tenant_id": "t1"}

    response = await execute_recovery(mock_request, db=mock_db)

    assert response["status"] == "success"
    assert response["action"] == "email_sent"

    # Verificamos que la query de actualización borre el payload (el escudo de seguridad PII)
    call_args = mock_db.execute.call_args_list[1][0]
    query_text = str(call_args[0])
    
    assert "payment_data = '{}'::jsonb" in query_text
    assert "UPDATE slancio_scheduled_recovery" in query_text

@pytest.mark.asyncio
@patch("api.routers.execute.qstash_receiver")
@patch.dict(os.environ, {"QSTASH_CURRENT_SIGNING_KEY": "c", "QSTASH_NEXT_SIGNING_KEY": "n"})
async def test_execute_recovery_not_found(mock_receiver):
    mock_receiver.verify.return_value = True

    mock_db = AsyncMock()
    mock_result = MagicMock()
    # Simulamos que la DB no encontró el evento pendiente
    mock_result.first.return_value = None 
    mock_db.execute.return_value = mock_result

    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def mock_begin():
        yield
    mock_db.begin = mock_begin

    mock_request = AsyncMock(spec=Request)
    mock_request.headers = {"Upstash-Signature": "valid_sig"}
    mock_request.body.return_value = b'{"event_id": "evt_1", "tenant_id": "t1"}'
    mock_request.json.return_value = {"event_id": "evt_1", "tenant_id": "t1"}

    response = await execute_recovery(mock_request, db=mock_db)

    # Si no lo encuentra, hace skip silencioso
    assert response["status"] == "skipped"