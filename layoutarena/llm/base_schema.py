from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_serializer


def convert_datetime_to_gmt(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def convert_date_to_iso(d: date) -> str:
    """Convert date object to ISO format string (YYYY-MM-DD)."""
    return d.isoformat()


class CoreModel(BaseModel):
    # Pydantic v2 configuration
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=False,
    )

    @field_serializer("*", mode="wrap")
    def serialize_any(self, value: Any, handler, info) -> Any:
        """Custom serializer for all fields to handle special types like neo4j.time.Date"""
        # Always handle neo4j.time.Date objects as they can't be JSON serialized by SQLAlchemy
        if isinstance(value, (list, dict)):
            # Always recursively handle nested structures to convert neo4j.Date objects
            return self._serialize_nested(value)

        # Only apply custom datetime serialization when serializing to JSON/API format
        # Don't apply when dumping for database operations (mode='python')
        if info.mode == "json":
            if isinstance(value, datetime):
                return convert_datetime_to_gmt(value)
            elif isinstance(value, date):
                return convert_date_to_iso(value)

        # For non-JSON modes or non-special types, use default handler
        return handler(value)

    def _serialize_nested(self, value: Any) -> Any:
        """Recursively serialize nested structures containing neo4j.time.Date objects"""
        if isinstance(value, list):
            return [self._serialize_nested(item) for item in value]
        elif isinstance(value, dict):
            return {key: self._serialize_nested(val) for key, val in value.items()}
        elif isinstance(value, datetime):
            return convert_datetime_to_gmt(value)
        elif isinstance(value, date):
            return convert_date_to_iso(value)
        else:
            return value
