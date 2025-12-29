from typing import Any, Optional, Union

from pydantic import BaseModel, Field


class IIIFService(BaseModel):
    """IIIF Image Service description."""

    id: Optional[str] = Field(None, alias="@id")
    id_v3: Optional[str] = Field(None, alias="id")
    type: Optional[str] = Field(None, alias="@type")
    type_v3: Optional[str] = Field(None, alias="type")
    profile: str

    @property
    def service_id(self) -> str:
        """Get the base URL for the image service."""
        return self.id_v3 or self.id or ""

    @property
    def is_v3(self) -> bool:
        """Determine if this is a IIIF Image API v3 service."""
        t = (self.type_v3 or self.type or "").lower()
        return "3" in t or "/3/" in (self.service_id or "")


class IIIFImageBody(BaseModel):
    """IIIF Image Body within an annotation."""

    id: str
    type: str
    format: str
    width: int
    height: int
    service: list[IIIFService]


class IIIFAnnotation(BaseModel):
    """IIIF Annotation containing an image body."""

    id: str
    type: str
    motivation: str
    body: IIIFImageBody


class IIIFAnnotationPage(BaseModel):
    """IIIF AnnotationPage containing annotations."""

    id: str
    type: str
    items: list[IIIFAnnotation]


class IIIFCanvas(BaseModel):
    """IIIF Canvas representing a single page."""

    id: str
    type: str
    label: Union[str, dict[str, Any]]
    width: int
    height: int
    items: list[IIIFAnnotationPage]

    def get_image_url(self) -> str:
        """Construct the maximum resolution IIIF Image URL."""
        try:
            body = self.items[0].items[0].body
            service = body.service[0]
            base_url = service.service_id.rstrip("/")
            if service.is_v3:
                return f"{base_url}/full/max/0/default.jpg"
            return f"{base_url}/full/full/0/default.jpg"
        except (IndexError, AttributeError):
            return ""


class IIIFManifest(BaseModel):
    """IIIF Manifest representing the entire document."""

    id: str
    type: str
    label: Union[str, dict[str, Any]]
    items: list[IIIFCanvas]
