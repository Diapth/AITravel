from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class PlanRequest(BaseModel):
    query: str = Field(..., description="自然语言旅行需求")
    start_city: str | None = Field(default=None, description="出发城市")
    target_city: str | None = Field(default=None, description="目的城市")
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
