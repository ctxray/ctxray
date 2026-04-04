# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| 1.x     | :x:                |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Open a [private security advisory](https://github.com/ctxray/ctxray/security/advisories/new) on GitHub
3. Include: description, reproduction steps, potential impact
4. We will respond within 72 hours

## Scope

reprompt processes local session files and stores data in a local SQLite database. It does not transmit data externally unless explicitly configured with optional backends (Ollama, OpenAI).
