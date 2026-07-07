"""Shared Pydantic types for MongoDB documents."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_serializer, field_validator
from pydantic_core import core_schema

from db.models.enums import SourceMethod


def prepare_for_mongo(value: Any) -> Any:
    """Recursively convert values to BSON-compatible forms."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, dict):
        return {key: prepare_for_mongo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [prepare_for_mongo(item) for item in value]
    return value


class PyObjectId(ObjectId):
    """Pydantic-compatible wrapper for bson ObjectId."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [
                            core_schema.str_schema(),
                            core_schema.no_info_plain_validator_function(cls.validate),
                        ]
                    ),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: str(value),
            ),
        )

    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str) and ObjectId.is_valid(value):
            return ObjectId(value)
        raise ValueError("Invalid ObjectId")


ObjectIdField = Annotated[PyObjectId, Field(default_factory=PyObjectId)]


class MongoModel(BaseModel):
    """Base model for persisted MongoDB documents."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class SourceRef(BaseModel):
    """Embedded provenance record reused across collections (§5)."""

    url: str
    publisher: str
    retrieved_at: datetime
    ingestion_run_id: PyObjectId | None = None
    method: SourceMethod
    confidence: float | None = None


class FipsCodes(BaseModel):
    state_fips: str | None = None
    county_fips: str | None = None
    place_fips: str | None = None
    geoid: str | None = None


class GeoJsonPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[float]) -> list[float]:
        if len(value) != 2:
            raise ValueError("Point coordinates must be [longitude, latitude]")
        return value


class GeoJsonPolygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class GeoJsonMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[list[float]]]]


GeoJsonBoundary = Annotated[GeoJsonPolygon | GeoJsonMultiPolygon, Field(discriminator="type")]
GEOJSON_BOUNDARY_ADAPTER = TypeAdapter(GeoJsonBoundary)


class MeetingLocation(BaseModel):
    name: str | None = None
    address: str | None = None
    geo: GeoJsonPoint | None = None


class VoteTally(BaseModel):
    ayes: int = 0
    noes: int = 0
    abstain: int = 0
    absent: int = 0
    recuse: int = 0


class CivicPlatformRef(BaseModel):
    vendor: str
    base_url: str
    detected_at: datetime
    confidence: float | None = None
    notes: str | None = None


class IngestionRunStats(BaseModel):
    meetings_found: int = 0
    meetings_upserted: int = 0
    agenda_items_upserted: int = 0
    actions_upserted: int = 0
    errors: list[str] = Field(default_factory=list)


class TimestampedMongoModel(MongoModel):
    created_at: datetime
    updated_at: datetime


class MongoDocument(MongoModel):
    """Base model with MongoDB _id field."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    @field_serializer("id", when_used="json")
    def serialize_id(self, value: PyObjectId) -> str:
        return str(value)

    def to_mongo(self) -> dict[str, Any]:
        return prepare_for_mongo(self.model_dump(by_alias=True, mode="python"))
