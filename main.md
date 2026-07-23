# Lead Intelligence & Email Discovery System

## Goal

Build a production-grade lead intelligence system that accepts a CSV containing business information and returns verified business emails and structured company insights.

The system should prioritize finding high-quality business email addresses from publicly available information while also collecting enough business context to enable highly personalized cold outreach.

This is NOT an AI-first project.

Use deterministic crawling, parsing, extraction, validation, and enrichment first.

Only use an LLM after structured data has already been collected.

---

# Input

CSV containing fields such as:

- Company Name
- Website (if available)
- Phone Number
- Address
- Google Rating
- Google Reviews
- City
- State
- Country
- Category

Example

Company Name

ABC Medical Spa

Website

https://abcspa.com

Phone

+1 555 111 2222

Address

Los Angeles, California

---

# Expected Output

One JSON object per company.

Example

{
  "company": "...",
  "website": "...",

  "emails": [
      {
          "email": "...",
          "type": "contact",
          "confidence": 98,
          "validation": {
              "syntax": true,
              "mx": true,
              "smtp": true,
              "disposable": false
          },
          "source_page": "...",
          "found_method": "mailto"
      }
  ],

  "phones": [],
  "socials": [],
  "team": [],
  "services": [],
  "technologies": [],
  "business_summary": "...",
  "lead_score": 94
}

---

# Primary Objective

Highest possible email discovery rate.

Never hallucinate.

Never generate emails.

Only return emails discovered from public sources.

Every email must include:

- source page
- discovery method
- confidence score
- validation results

---

# Crawl Strategy

The crawler should intelligently visit pages instead of crawling everything.

Priority order:

/

contact

about

team

staff

providers

doctors

employees

support

locations

faq

privacy

terms

careers

blog

footer links

header navigation

robots.txt

sitemap.xml

RSS feeds

XML sitemaps

Only continue deeper if needed.

Avoid crawling unnecessary pages.

---

# Crawling Engine

Support multiple extraction strategies.

Priority:

1. Static HTML

2. JavaScript rendering

3. PDFs

4. Images

Use:

- Scrapy
- Playwright
- Crawl4AI
- selectolax
- BeautifulSoup
- lxml

---

# Email Discovery

Extract emails from

HTML

mailto links

Footer

Header

Contact page

About page

JSON-LD

Schema.org

JavaScript

Inline scripts

Hidden HTML

Comments

Base64 encoded strings

Unicode encoded strings

Character entities

Cloudflare email protection

Obfuscated emails

Examples

john [at] company.com

john(at)company(dot)com

john&#64;company.com

contact [@] company.com

Decode all supported formats.

---

# PDF Extraction

Many companies publish emails inside

Brochures

Menus

Forms

Catalogs

Guides

Price lists

Service documents

Use

PyMuPDF

pdfplumber

OCR if necessary

---

# OCR

Extract emails from

Images

Flyers

Business cards

Scanned PDFs

Certificates

Use

PaddleOCR

Tesseract

---

# Phone Extraction

Extract

Office

Mobile

Fax

WhatsApp

Support

Sales

---

# Social Profiles

Find

LinkedIn

Facebook

Instagram

Twitter/X

TikTok

YouTube

Pinterest

---

# Business Information

Extract

Company Name

Description

Industry

Categories

Services

Products

Locations

Opening Hours

Doctors

Staff

Team Members

Booking Software

CMS

Chat Widget

Technology Stack

Years in Business

Awards

Certifications

Insurance Accepted

Languages

Testimonials

FAQs

Pricing

---

# Technology Detection

Detect

WordPress

Shopify

Wix

Squarespace

React

Next.js

Cloudflare

Google Analytics

Meta Pixel

Google Tag Manager

Booking Software

Live Chat

CRM

Calendly

HubSpot

Stripe

PayPal

---

# Email Validation Pipeline

Each email passes through

Stage 1

Syntax validation

Stage 2

Normalize email

Lowercase

Trim spaces

Stage 3

Duplicate removal

Stage 4

Disposable email detection

Stage 5

Role account detection

Examples

info@

support@

admin@

sales@

hello@

appointments@

Stage 6

DNS lookup

Stage 7

MX lookup

Stage 8

SMTP verification

Without sending email.

Stage 9

Confidence scoring

---

# Confidence Score

Score using

Found in mailto

Found on contact page

Found multiple times

MX valid

SMTP valid

Same company domain

Not disposable

Not malformed

Role email

Personal email

Recent crawl

Score

0–100

---

# Lead Intelligence

Generate

Business Summary

Main Services

Target Customers

Business Type

Company Size Estimate

Locations

Technology Used

Primary Contact Email

Primary Phone

Social Presence

Years in Business (if available)

---

# SEO Insights

Detect

Missing title

Missing meta description

Broken images

Broken links

Missing schema

Missing alt tags

Slow loading resources

No sitemap

No robots

Large images

Missing favicon

---

# AI Opportunities

Based only on collected evidence.

Examples

No chatbot

No online booking

No FAQ

No blog

Outdated website

No online forms

Weak mobile experience

No automation

Never hallucinate.

---

# Performance

Must support

Millions of websites

Parallel crawling

Queue system

Retry mechanism

Checkpoint recovery

Rate limiting

Automatic proxy support

Browser pooling

Caching

Incremental crawling

Resume after crash

---

# Storage

Store

Raw HTML

Extracted Text

Email Sources

Validation Results

Crawl Logs

JSON Output

Screenshots (optional)

PDFs (optional)

---

# Recommended Stack

Crawler

- Scrapy
- Crawl4AI
- Playwright

HTML Parsing

- selectolax
- BeautifulSoup
- lxml

Email Extraction

- regex
- email-validator

Validation

- dnspython
- pyIsEmail
- SMTP verification

OCR

- PaddleOCR
- Tesseract

PDF

- PyMuPDF
- pdfplumber

Queue

- Redis

Database

- PostgreSQL

API

- FastAPI

Container

- Docker

Monitoring

- Prometheus
- Grafana

---

# Rules

Never invent emails.

Never guess emails.

Never generate emails using name patterns.

Every email must be backed by evidence.

Every extracted field should include its source whenever possible.

Prioritize precision over quantity.

Design the system to be modular, scalable, fault-tolerant, and production-ready.