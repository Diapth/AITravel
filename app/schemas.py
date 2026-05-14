from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PlanRequest(BaseModel):
    query: str = Field(..., description="自然语言旅行需求")
    start_city: str | None = Field(default=None, description="出发城市")
    target_city: str | None = Field(default=None, description="目的城市")
    target_cities: list[str] = Field(default_factory=list, description="多目的城市")
    departure_date: date | None = Field(default=None, description="出发日期")
    return_date: date | None = Field(default=None, description="回程日期")
    days: int | None = Field(default=None, ge=1, le=30, description="行程天数")
    people_number: int | None = Field(default=None, ge=1, le=50, description="出行人数")
    budget: int | None = Field(default=None, ge=1, description="总预算，单位人民币")

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value

    @field_validator("start_city", "target_city")
    @classmethod
    def empty_optional_text_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("target_cities", mode="before")
    @classmethod
    def normalize_target_cities(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value)
        cleaned: list[str] = []
        seen = set()
        for item in items:
            city = str(item).strip()
            if city and city not in seen:
                seen.add(city)
                cleaned.append(city)
        return cleaned

    @model_validator(mode="after")
    def normalize_destination_and_dates(self) -> "PlanRequest":
        if self.target_cities and not self.target_city:
            self.target_city = "、".join(self.target_cities)
        if self.departure_date and self.return_date:
            if self.return_date < self.departure_date:
                raise ValueError("return_date must not be earlier than departure_date")
            if self.days is None:
                self.days = (self.return_date - self.departure_date).days + 1
        return self


class FieldExtractionRequest(BaseModel):
    query: str = Field(..., description="自然语言旅行需求")

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class ExtractedFields(BaseModel):
    start_city: str | None = None
    target_city: str | None = None
    days: int | None = Field(default=None, ge=1, le=30)
    people_number: int | None = Field(default=None, ge=1, le=50)
    budget: int | None = Field(default=None, ge=1)
    preferences: list[str] = Field(default_factory=list)


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class FieldExtractionResponse(BaseModel):
    success: bool
    fields: ExtractedFields | None = None
    error: ErrorPayload | None = None


class ImageSearchItem(BaseModel):
    title: str | None = None
    url: str
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None


class ImageSearchResponse(BaseModel):
    success: bool
    images: list[ImageSearchItem] = Field(default_factory=list)
    error: ErrorPayload | None = None


class PlanResponse(BaseModel):
    success: bool
    plan: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    error: ErrorPayload | None = None
