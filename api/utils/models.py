from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative ORM models.
    All ORM models in this module should inherit from this base class so
    SQLAlchemy can configure the declarative mappings and metadata.
    """
    pass


class TenantConfig(Base):
    """Tenant-specific configuration for the margin system.

    Attributes:
        tenant_id: Unique identifier for the tenant.
        is_active: Flag indicating whether the tenant configuration is active.
        margin_rules: JSON payload defining the tenant's margin rules.
        updated_at: Timestamp of the last update to the tenant configuration.
    """

    __tablename__ = "slancio_tenant_configs"

    tenant_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    margin_rules: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ScheduledMargin(Base):
    """Scheduled margin adjustment entry for a tenant.

    Attributes:
        id: UUID primary key for the scheduled margin record.
        tenant_id: Reference to the tenant owning the margin schedule.
        event_id: Unique identifier for the payment event.
        execute_at: Scheduled execution time for the margin adjustment.
        payment_data: JSON payload containing payment-related data.
        status: Current status of the margin schedule.
        created_at: Timestamp when the margin record was created.
    """

    __tablename__ = "slancio_scheduled_recovery"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("slancio_tenant_configs.tenant_id"), index=True)
    event_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payment_data: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
