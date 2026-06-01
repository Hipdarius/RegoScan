# Security Policy

## Reporting a vulnerability

VERA is a research instrument, not production safety-critical software.
That said, if you find a security issue — a vulnerability in the
FastAPI service, an unsafe deserialisation path in the inference
engine, a credential leak, or anything else that would let a third
party compromise a deployment — please report it privately rather
than opening a public issue.

**Email:** dieteticienne@conseildietetique.lu
**Subject line:** `[VERA security] <one-line summary>`

If the issue is straightforward I will acknowledge within 7 days and
patch within 30. If the issue is complex or hardware-related, I will
say so in the acknowledgement and propose a longer timeline.

## What counts as a vulnerability

| In scope | Out of scope |
|--|--|
| Remote code execution via the inference API | Bugs that only affect a researcher running their own copy locally |
| Path traversal in `apps/api.py` | Test failures on unsupported Python versions (< 3.11) |
| Unsafe pickle / ONNX loading from untrusted sources | Style or lint complaints (use `make lint`) |
| Secrets accidentally committed | Theoretical attacks that require physical access to the probe |
| Unsafe firmware behaviour (buffer overflow, panic loop) on malformed serial input | Bugs in third-party dependencies (please report upstream) |

## What you can expect

- A response acknowledging receipt within 7 days
- A clear "in scope" or "out of scope" decision with reasoning
- Public credit in the fix commit, unless you ask to remain anonymous
- A patched release within 30 days for in-scope issues, or a documented timeline if the fix is complex

Thank you for taking the time to report.
