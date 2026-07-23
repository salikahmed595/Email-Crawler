# LOCAL.md

# Local Development Guide

Version: 1.0

---

# Purpose

This document defines the local development environment, development workflow, coding standards, project structure, debugging practices, testing strategy, and day-to-day engineering guidelines for the Lead Intelligence & Email Discovery System.

Every contributor should be able to clone the project and start development with minimal configuration.

The local environment should closely mirror production.

---

# Development Philosophy

Development should prioritize

• Simplicity
• Reproducibility
• Fast iteration
• Deterministic behavior
• Easy debugging
• Modular architecture

Avoid unnecessary complexity.

---

# Development Environment

Operating Systems Supported

• Linux (Preferred)
• macOS
• Windows (WSL2 Recommended)

Development should behave consistently across platforms.

---

# Language

Primary

Python 3.12+

---

# Package Management

Use

uv

or

Poetry

Avoid global package installations.

Every dependency must be pinned.

---

# Virtual Environment

Every developer must work inside an isolated virtual environment.

Never install packages globally.

---

# Project Structure

```
project/

    app/

        api/

        crawler/

        extractors/

        validators/

        parsers/

        storage/

        workers/

        models/

        schemas/

        services/

        queue/

        config/

        logging/

        monitoring/

        utils/

    tests/

    scripts/

    docker/

    docs/

    migrations/

    sample_data/

    logs/

    output/

    temp/

    requirements/

    pyproject.toml

    README.md

    MAIN.md

    RULES.md

    FRAMEWORK.md

    LOCAL.md
```

---

# Configuration

Never hardcode values.

Use environment variables.

Examples

```
DATABASE_URL

REDIS_URL

MAX_WORKERS

HTTP_TIMEOUT

USER_AGENT

MAX_RETRIES

PLAYWRIGHT_ENABLED

OCR_ENABLED

PDF_ENABLED

LOG_LEVEL
```

---

# Secrets

Never commit

Passwords

Tokens

API Keys

Cookies

Private certificates

Use

.env

only.

---

# Local Services

Development environment should include

PostgreSQL

Redis

Playwright browsers

Optional

MinIO

Prometheus

Grafana

---

# Docker

Every service should have its own container.

Examples

crawler

redis

postgres

worker

api

monitoring

Containers should communicate using Docker networks.

---

# Development Workflow

CSV Input

↓

Import Queue

↓

Crawler

↓

Parser

↓

Extractor

↓

Validator

↓

Database

↓

Export JSON

Every stage should be executable independently.

---

# Running Individual Modules

Developers should be able to execute

Crawler only

Parser only

Validator only

Extractor only

Exporter only

without running the complete pipeline.

---

# Sample Dataset

Maintain a local dataset containing

small.csv

medium.csv

large.csv

broken_websites.csv

duplicates.csv

Each dataset should be version controlled.

---

# Logging

Log everything.

Examples

Website started

Website completed

Emails discovered

Validation result

Retry

Timeout

Exception

Processing duration

Never suppress exceptions silently.

---

# Log Levels

DEBUG

INFO

WARNING

ERROR

CRITICAL

Development should default to DEBUG.

Production should default to INFO.

---

# Testing

Every module must include tests.

Examples

Crawler Tests

Parser Tests

Validator Tests

Email Tests

Duplicate Tests

OCR Tests

PDF Tests

Technology Detection Tests

Queue Tests

API Tests

Regression Tests

---

# Test Principles

Tests should be

Deterministic

Fast

Independent

Repeatable

Never depend on internet connectivity when avoidable.

Use fixtures and mocked HTTP responses whenever possible.

---

# Local Database

Use PostgreSQL locally.

Never use production databases.

Seed with sample businesses.

---

# Local Storage

Store

HTML

PDF

Logs

JSON

inside dedicated folders.

Automatically clean temporary files.

---

# Development Rules

Never write business logic inside

API routes

CLI commands

Workers

Business logic belongs inside services.

---

# Code Organization

One responsibility per module.

Avoid giant files.

Prefer

100–300 lines

per module whenever practical.

---

# Naming Conventions

Classes

PascalCase

Functions

snake_case

Variables

snake_case

Constants

UPPER_CASE

Files

snake_case.py

---

# Documentation

Every module should include

Purpose

Inputs

Outputs

Dependencies

Limitations

Usage Example

---

# Error Handling

Never ignore exceptions.

Every exception should

Log details

Provide context

Return meaningful errors

Continue processing whenever possible.

---

# Retry Strategy

Retry

Timeouts

Network failures

Temporary HTTP errors

Do not retry

404

Invalid domains

Malformed URLs

---

# Performance During Development

Avoid Playwright unless necessary.

Prefer static crawling.

Use a small worker count.

Enable verbose logs.

Disable OCR unless testing OCR.

Disable PDF parsing unless testing PDFs.

---

# Local Debugging

Developers should be able to inspect

Raw HTML

Parsed DOM

Extracted emails

Validation results

Company metadata

Final JSON

Every stage should be inspectable independently.

---

# Output Format

Development outputs should include

Pretty JSON

Validation summary

Email confidence

Discovery source

Execution time

---

# Git Workflow

Feature branches only.

Small commits.

Meaningful commit messages.

Pull requests should focus on one feature or bug fix.

Never mix unrelated changes.

---

# Code Quality

Use

ruff

black

mypy

before every commit.

Code should pass formatting, linting, and type checking.

---

# Dependencies

Prefer mature, actively maintained open-source libraries.

Avoid abandoned projects.

Minimize dependency count.

Replace dependencies only with measurable benefits.

---

# Browser Automation

Playwright should run in headless mode by default.

Enable headed mode only for debugging.

Reuse browser instances whenever possible.

Avoid opening a new browser per website.

---

# Network Requests

Use connection pooling.

Respect request timeouts.

Respect retry limits.

Set a descriptive User-Agent.

Throttle requests to avoid overloading websites.

---

# Local Performance Goals

Startup time

Less than 10 seconds

Small dataset crawl

Less than 1 minute

Memory usage

Keep as low as practical

CPU

Efficient asynchronous processing

---

# Local Success Criteria

A successful local development environment should allow a developer to:

• Import a CSV.
• Crawl sample websites.
• Extract emails.
• Validate emails.
• Store results in PostgreSQL.
• Export structured JSON.
• Inspect logs.
• Run tests.
• Restart interrupted jobs.
• Debug any stage independently.

---

# Final Principle

Local development should optimize for developer productivity, deterministic behavior, and rapid iteration.

Every feature must be testable in isolation before being integrated into the complete pipeline.

The local environment should remain lightweight, reproducible, and as close to production as practical.