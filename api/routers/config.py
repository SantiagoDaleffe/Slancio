from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.utils.schemas import TenantConfigPayload
from api.utils.models import TenantConfig
from api.utils.dependencies import get_db
from api.utils.logger import logger, trace_id_var

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.post("/rules", status_code=200)
async def upsert_tenant_rules(
    payload: TenantConfigPayload, db: AsyncSession = Depends(get_db)
):
    """Create or update the margin rules for a tenant.

    Args:
        payload (TenantConfigPayload): Tenant identifier, activation status, and
            margin rules to persist.
        db (AsyncSession, optional): Database session used to upsert the tenant
            configuration. Defaults to Depends(get_db).

    Returns:
        dict: A success response containing the tenant identifier, trace ID,
            and applied margin rules.
    """
    logger.info(f"Updating margin rules for tenant: {payload.tenant_id}")

    try:
        new_config = TenantConfig(
            tenant_id=payload.tenant_id,
            is_active=payload.is_active,
            margin_rules=payload.rules.model_dump(),
        )
        await db.merge(new_config)
        await db.commit()

        return {
            "status": "success",
            "message": "Margin rules updated successfully",
            "tenant_id": payload.tenant_id,
            "trace_id": trace_id_var.get(),
            "applied_rules": payload.rules.model_dump(),
        }
    except Exception as e:
        logger.error(
            f"[Trace: {trace_id_var.get()}] Error updating margin rules for tenant {payload.tenant_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
