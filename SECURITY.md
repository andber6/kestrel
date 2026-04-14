# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Kestrel, please report it responsibly.

**Email:** andre.bergan99@hotmail.com

**Do not** open a public GitHub issue for security vulnerabilities.

## What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response timeline

- **Acknowledgment:** within 48 hours
- **Initial assessment:** within 1 week
- **Fix or mitigation:** as soon as possible, depending on severity

## Scope

The following are in scope:

- API key exposure or leakage
- Authentication bypass
- Provider credential leakage
- Request/response data exposure
- Injection attacks (SQL, command, etc.)

The following are out of scope:

- Denial of service (rate limiting is intentionally not implemented for the open-source core)
- Vulnerabilities in upstream LLM provider APIs
- Issues requiring physical access to the server
