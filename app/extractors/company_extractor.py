"""
Company metadata extractor — extracts business information from parsed pages.
Sources: Schema.org, JSON-LD, OpenGraph, visible HTML text.
"""

from __future__ import annotations

import re
from typing import Any

from app.logging import get_logger
from app.parsers.html_parser import ParsedPage

logger = get_logger(__name__)


class CompanyExtractor:
    """
    Extracts business metadata from structured page data.
    Prioritizes Schema.org/JSON-LD over plain HTML scraping.
    """

    def extract(self, parsed: ParsedPage, domain: str) -> dict[str, Any]:
        """
        Extract company metadata from a parsed page.
        Returns a dict of enrichment fields.
        """
        metadata: dict[str, Any] = {
            "name": None,
            "description": None,
            "address": None,
            "phone_numbers": [],
            "social_links": {},
            "opening_hours": None,
            "services": [],
            "team_members": [],
        }

        # Priority: JSON-LD/Schema.org > OpenGraph > HTML meta > text
        for schema in parsed.schema_org:
            self._extract_from_schema(schema, metadata)

        # OpenGraph fallback
        if not metadata["name"] and parsed.open_graph.get("site_name"):
            metadata["name"] = parsed.open_graph["site_name"]

        if not metadata["description"] and parsed.open_graph.get("description"):
            metadata["description"] = parsed.open_graph["description"]

        # HTML meta fallback
        if not metadata["name"]:
            metadata["name"] = parsed.meta.get("og:site_name") or parsed.title or None

        if not metadata["description"]:
            metadata["description"] = parsed.description or None

        return metadata

    def _extract_from_schema(
        self, schema: dict, metadata: dict[str, Any]
    ) -> None:
        """Extract fields from a Schema.org/JSON-LD object."""
        schema_type = str(schema.get("@type", "")).lower()

        # Name
        if not metadata["name"] and schema.get("name"):
            metadata["name"] = str(schema["name"])[:500]

        # Description
        if not metadata["description"] and schema.get("description"):
            metadata["description"] = str(schema["description"])[:2000]

        # Address
        if not metadata["address"]:
            addr = schema.get("address")
            if isinstance(addr, dict):
                metadata["address"] = {
                    "street": addr.get("streetAddress"),
                    "city": addr.get("addressLocality"),
                    "state": addr.get("addressRegion"),
                    "postal_code": addr.get("postalCode"),
                    "country": addr.get("addressCountry"),
                }
            elif isinstance(addr, str):
                metadata["address"] = {"raw": addr}

        # Phone
        if schema.get("telephone"):
            phone = str(schema["telephone"])
            if phone not in metadata["phone_numbers"]:
                metadata["phone_numbers"].append(phone)

        # Opening hours
        if not metadata["opening_hours"] and schema.get("openingHours"):
            metadata["opening_hours"] = schema["openingHours"]

        # Services / products
        if schema.get("hasOfferCatalog"):
            catalog = schema["hasOfferCatalog"]
            if isinstance(catalog, dict) and catalog.get("itemListElement"):
                for item in catalog["itemListElement"]:
                    if isinstance(item, dict) and item.get("name"):
                        svc = str(item["name"])
                        if svc not in metadata["services"]:
                            metadata["services"].append(svc)

        # Team members (Person schema)
        if schema_type == "person":
            person: dict[str, Any] = {}
            if schema.get("name"):
                person["name"] = str(schema["name"])
            if schema.get("jobTitle"):
                person["title"] = str(schema["jobTitle"])
            if schema.get("email"):
                person["email"] = str(schema["email"])
            if person:
                metadata["team_members"].append(person)
