"""
Technology detector — identifies CMS, analytics, chat widgets, booking software, CDN.
Uses HTTP headers, HTML signatures, and script patterns.
All detection is deterministic — no AI, no external APIs.
"""

from __future__ import annotations

import re
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

# Technology fingerprints: (name, category, pattern)
# Patterns checked against: HTML content, headers, script src URLs
_SIGNATURES: list[dict[str, Any]] = [
    # CMS
    {"name": "WordPress", "category": "CMS", "html_pattern": r'wp-content|wp-includes|/wp-json/'},
    {"name": "Shopify", "category": "E-commerce", "html_pattern": r'cdn\.shopify\.com|Shopify\.theme'},
    {"name": "Squarespace", "category": "CMS", "html_pattern": r'squarespace\.com|static1\.squarespace'},
    {"name": "Wix", "category": "CMS", "html_pattern": r'wix\.com|wixsite\.com'},
    {"name": "Webflow", "category": "CMS", "html_pattern": r'webflow\.io|webflow\.com'},
    {"name": "Drupal", "category": "CMS", "html_pattern": r'drupal\.js|Drupal\.settings'},
    {"name": "Joomla", "category": "CMS", "html_pattern": r'/media/jui/|Joomla!'},
    {"name": "Ghost", "category": "CMS", "html_pattern": r'ghost\.org|ghost-theme'},
    {"name": "HubSpot CMS", "category": "CMS", "html_pattern": r'hs-analytics|hubspot\.com/'},
    # Analytics
    {"name": "Google Analytics", "category": "Analytics", "html_pattern": r'google-analytics\.com|ga\.js|gtag\.js|UA-\d{6,9}-\d'},
    {"name": "Google Tag Manager", "category": "Analytics", "html_pattern": r'googletagmanager\.com|GTM-'},
    {"name": "Hotjar", "category": "Analytics", "html_pattern": r'hotjar\.com|hjSetting'},
    {"name": "Mixpanel", "category": "Analytics", "html_pattern": r'mixpanel\.com|mixpanel\.track'},
    {"name": "Segment", "category": "Analytics", "html_pattern": r'segment\.io|segment\.com'},
    {"name": "Matomo", "category": "Analytics", "html_pattern": r'matomo\.js|piwik\.js'},
    # Chat
    {"name": "Intercom", "category": "Chat", "html_pattern": r'intercom\.io|Intercom\('},
    {"name": "Drift", "category": "Chat", "html_pattern": r'drift\.com|drift\.load'},
    {"name": "Zendesk Chat", "category": "Chat", "html_pattern": r'zdassets\.com|zopim\.com'},
    {"name": "LiveChat", "category": "Chat", "html_pattern": r'livechatinc\.com|LiveChatWidget'},
    {"name": "Crisp", "category": "Chat", "html_pattern": r'crisp\.chat|CRISP_WEBSITE_ID'},
    {"name": "Tidio", "category": "Chat", "html_pattern": r'tidiochat\.com|tidio\.co'},
    # Booking
    {"name": "Calendly", "category": "Booking", "html_pattern": r'calendly\.com'},
    {"name": "Acuity Scheduling", "category": "Booking", "html_pattern": r'acuityscheduling\.com'},
    {"name": "SimplyBook", "category": "Booking", "html_pattern": r'simplybook\.me'},
    {"name": "Booksy", "category": "Booking", "html_pattern": r'booksy\.com'},
    {"name": "Mindbody", "category": "Booking", "html_pattern": r'mindbodyonline\.com'},
    {"name": "Fresha", "category": "Booking", "html_pattern": r'fresha\.com'},
    # CDN
    {"name": "Cloudflare", "category": "CDN", "html_pattern": r'cloudflare\.com|__cf_bm'},
    {"name": "Fastly", "category": "CDN", "html_pattern": r'fastly\.net'},
    {"name": "AWS CloudFront", "category": "CDN", "html_pattern": r'cloudfront\.net'},
    # Frameworks
    {"name": "React", "category": "Framework", "html_pattern": r'react\.development\.js|react\.production\.min\.js|__REACT'},
    {"name": "Vue.js", "category": "Framework", "html_pattern": r'vue\.runtime|vue\.min\.js'},
    {"name": "Angular", "category": "Framework", "html_pattern": r'ng-version|angular\.min\.js'},
    {"name": "jQuery", "category": "Library", "html_pattern": r'jquery\.min\.js|jquery-\d'},
    # Payment
    {"name": "Stripe", "category": "Payment", "html_pattern": r'js\.stripe\.com|stripe\.com/v\d'},
    {"name": "PayPal", "category": "Payment", "html_pattern": r'paypal\.com/sdk|paypalobjects\.com'},
    # Marketing
    {"name": "Mailchimp", "category": "Email Marketing", "html_pattern": r'mailchimp\.com|mc\.js'},
    {"name": "Klaviyo", "category": "Email Marketing", "html_pattern": r'klaviyo\.com'},
    {"name": "HubSpot", "category": "CRM", "html_pattern": r'hubspot\.com|hs-scripts'},
    {"name": "Salesforce", "category": "CRM", "html_pattern": r'salesforce\.com|force\.com'},
]

# Header-based detection
_HEADER_SIGNATURES: list[dict[str, str]] = [
    {"name": "Cloudflare", "category": "CDN", "header": "cf-ray"},
    {"name": "Nginx", "category": "Web Server", "header_value": "nginx", "header": "server"},
    {"name": "Apache", "category": "Web Server", "header_value": "apache", "header": "server"},
    {"name": "WordPress", "category": "CMS", "header": "x-powered-by", "header_value": "wordpress"},
    {"name": "PHP", "category": "Language", "header": "x-powered-by", "header_value": "php"},
]


class TechnologyExtractor:
    """
    Detects technology stack from HTML content and HTTP response headers.
    Fully deterministic — pattern matching only.
    """

    def extract(
        self,
        html: str,
        headers: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """
        Detect technologies from HTML and headers.
        Returns list of {name, category, confidence}.
        """
        detected: list[dict[str, str]] = []
        seen_names: set[str] = set()

        html_lower = html.lower()

        # HTML-based detection
        for sig in _SIGNATURES:
            name = sig["name"]
            if name in seen_names:
                continue
            pattern = re.compile(sig["html_pattern"], re.IGNORECASE)
            if pattern.search(html):
                detected.append({
                    "name": name,
                    "category": sig["category"],
                    "detection": "html_pattern",
                })
                seen_names.add(name)

        # Header-based detection
        if headers:
            headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
            for sig in _HEADER_SIGNATURES:
                name = sig["name"]
                if name in seen_names:
                    continue
                header_key = sig["header"].lower()
                if header_key in headers_lower:
                    expected_value = sig.get("header_value", "")
                    if not expected_value or expected_value in headers_lower[header_key]:
                        detected.append({
                            "name": name,
                            "category": sig["category"],
                            "detection": "http_header",
                        })
                        seen_names.add(name)

        return detected
