from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from sonavault.db import Base

ASSET_TYPES = ("audio", "pdf", "docx", "xml")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (CheckConstraint(f"asset_type IN {ASSET_TYPES}", name="ck_assets_type"),)

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sanctuary_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    station_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_qa_flag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(Uuid, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
