# Email Verification Classification

Every discovered email must be classified into one of three categories.

The classification is deterministic and based entirely on technical validation and public evidence.

---

## Tier 1 — Verified

Status

Verified

Requirements

✓ Valid email syntax

✓ Domain exists

✓ MX records exist

✓ Company domain matches

✓ Publicly visible on official website

✓ SMTP verification successful (when supported)

✓ Not disposable

✓ Not blacklisted

✓ High confidence score (95–100)

Export

Yes (Default)

Recommended for

Cold outreach

Sales automation

CRM import

Highest deliverability

---

## Tier 2 — High Confidence

Status

High Confidence

Requirements

✓ Valid email syntax

✓ Domain exists

✓ MX records exist

✓ Company domain matches

✓ Found on official website

✓ Multiple evidence sources preferred

✓ Not disposable

✓ SMTP verification unavailable, blocked, or inconclusive

✓ Confidence score (85–94)

Examples

Microsoft 365

Google Workspace

Catch-all mail servers

SMTP disabled

Export

Yes (Optional or Default, configurable)

Recommended for

Cold outreach

Lead generation

Most production workflows

---

## Tier 3 — Risky

Status

Risky

Requirements

Syntax valid

MX exists

OR

Partial validation only

Possible reasons

Catch-all domain

Unknown SMTP response

Found only once

Third-party directory

Weak evidence

Temporary domain

Low confidence

Confidence

Below 85

Export

Disabled by default

Can be enabled manually.

---

## Tier 4 — Invalid

Status

Invalid

Reasons

Invalid syntax

No domain

No MX

Malformed

Disposable

Spam trap

Blacklisted

Fake

Parked domain

Export

Never

Automatically rejected.

---

# Confidence Score

The confidence score is calculated using deterministic evidence.

Positive Signals

+ Found on official website

+ Contact page

+ mailto link

+ Multiple occurrences

+ Company domain

+ MX exists

+ SMTP verified

+ Same business name

+ Structured data (Schema.org / JSON-LD)

+ Recently crawled

Negative Signals

- Disposable provider

- Catch-all domain

- Third-party source only

- Single occurrence

- Weak evidence

- Temporary domain

- Parked domain

- Inconsistent company match

Final Score

95–100

Verified

85–94

High Confidence

70–84

Risky

Below 70

Invalid

---

# Export Policy

Default Export

Include

Verified

High Confidence

Exclude

Risky

Invalid

Advanced Export

Allow users to choose

Verified Only

Verified + High Confidence

All Including Risky

Invalid emails can never be exported.

---

# Dashboard Indicators

Green

Verified

Blue

High Confidence

Yellow

Risky

Red

Invalid

---

# Final Principle

Never reject a legitimate business email simply because SMTP verification is unavailable.

Public evidence from the company's official website combined with strong technical validation (syntax, domain, MX records, and company-domain matching) is sufficient to classify an email as High Confidence.

The system should maximize both accuracy and coverage while minimizing false positives.