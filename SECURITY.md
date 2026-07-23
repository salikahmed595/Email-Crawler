# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it privately
rather than opening a public issue:

- Use GitHub's [private vulnerability reporting](../../security/advisories/new) for this
  repository, or
- Open a draft security advisory under the repo's **Security** tab.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any relevant logs or proof-of-concept code

You should expect an initial response within a few days.

## Supported Versions

This project is under active development on the `main` branch. Only the latest commit
on `main` is supported with security fixes.

## Project Security Notes

- Never commit a real `.env` file — copy `.env.example` and fill in your own local
  values. `.env` is git-ignored by default.
- The crawler enforces SSRF protections (blocked hosts/IP ranges, protocol allowlist)
  in `app/utils/url_utils.py` and `app/validators/url_validator.py` — do not disable
  these checks.
- SMTP-based email validation and the optional OpenAI summary polish are both
  off by default and must be explicitly opted into via `.env`.
