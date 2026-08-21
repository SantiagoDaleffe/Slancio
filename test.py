import hmac
import hashlib
import json
import httpx

# 1. Ajustá esto a tu entorno real
TIENDANUBE_SECRET = "dummy_tiendanube_secret_123" 
RAILWAY_URL = "https://TU_DOMINIO.up.railway.app/webhook/tiendanube"

# 2. Armamos un carrito abandonado falso
payload = {
    "store_id": 987654,
    "checkout": {
        "id": "cart_tn_001",
        "customer": {"email": "cliente@tiendanube.com"},
        "total": "25000.00",
        "currency": "ARS",
        "products": [{"id": 1}, {"id": 2}]
    }
}

body = json.dumps(payload)

# 3. Firmamos el payload exactamente como lo hace Tiendanube (con hexdigest)
firma = hmac.new(
    TIENDANUBE_SECRET.encode("utf-8"), 
    body.encode("utf-8"), 
    hashlib.sha256
).hexdigest()

# 4. Disparamos el webhook
print(f"Enviando webhook a {RAILWAY_URL}...")
respuesta = httpx.post(
    RAILWAY_URL, 
    content=body, 
    headers={"X-Linked-Store-Hmac-Sha256": firma}
)

print(f"Status: {respuesta.status_code}")
print(f"Body: {respuesta.text}")