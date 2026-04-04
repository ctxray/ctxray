"""Sensitive content detection in stored prompts.

Scans prompts for API keys, tokens, emails, IP addresses, passwords,
environment secrets, and home directory paths. All detection is regex-based
(zero LLM, zero network).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

PATTERNS: dict[str, re.Pattern[str]] = {
    # API keys
    "api_key_openai": re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    "api_key_aws": re.compile(r"AKIA[0-9A-Z]{16}"),
    "api_key_github": re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    "api_key_github_fine": re.compile(r"github_pat_[a-zA-Z0-9_]{22,}"),
    "api_key_anthropic": re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),
    "api_key_stripe": re.compile(r"sk_(?:live|test)_[a-zA-Z0-9]{24,}"),
    "api_key_google": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "api_key_slack_bot": re.compile(r"xoxb-[0-9a-zA-Z\-]{24,}"),
    "api_key_slack_user": re.compile(r"xoxp-[0-9a-zA-Z\-]{24,}"),
    "api_key_slack_app": re.compile(r"xapp-[0-9a-zA-Z\-]{24,}"),
    "api_key_npm": re.compile(r"npm_[a-zA-Z0-9]{36}"),
    # Tokens
    "jwt_token": re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}"),
    # PII
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # Credentials
    "password_assignment": re.compile(
        r"(?:password|passwd|pwd)\s*[=:]\s*[\"']?\S{4,}", re.IGNORECASE
    ),
    "env_secret": re.compile(
        r"(?:DATABASE_URL|SECRET_KEY|API_KEY|AUTH_TOKEN|PRIVATE_KEY|ACCESS_TOKEN)"
        r"\s*=\s*\S{4,}",
        re.IGNORECASE,
    ),
    "db_connection_string": re.compile(
        r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql)"
        r"://[^:]+:[^@]+@[^\s\"']{4,}",
        re.IGNORECASE,
    ),
    # SSH keys & certificates
    "ssh_private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "pem_certificate": re.compile(r"-----BEGIN CERTIFICATE-----"),
    "ssh_key_path": re.compile(
        r"~/\.ssh/(?:id_(?:rsa|ed25519|ecdsa|dsa)|authorized_keys|known_hosts)"
    ),
    # Paths
    "home_path_unix": re.compile(r"/(?:Users|home)/\w+/"),
}

# IPs to exclude (localhost, broadcast, metadata)
_SAFE_IPS = {"127.0.0.1", "0.0.0.0", "255.255.255.255", "169.254.169.254"}

# Email domains to exclude (examples, tests)
_SAFE_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "test.com",
    "localhost",
    "noreply.github.com",
}

# Category grouping for display
CATEGORY_MAP: dict[str, str] = {
    "api_key_openai": "API keys",
    "api_key_aws": "API keys",
    "api_key_github": "API keys",
    "api_key_github_fine": "API keys",
    "api_key_anthropic": "API keys",
    "api_key_stripe": "API keys",
    "api_key_google": "API keys",
    "api_key_slack_bot": "API keys",
    "api_key_slack_user": "API keys",
    "api_key_slack_app": "API keys",
    "api_key_npm": "API keys",
    "jwt_token": "JWT tokens",
    "email": "Emails",
    "ipv4": "IP addresses",
    "password_assignment": "Passwords",
    "env_secret": "Env secrets",
    "db_connection_string": "Database credentials",
    "ssh_private_key": "SSH keys",
    "pem_certificate": "SSH keys",
    "ssh_key_path": "SSH keys",
    "home_path_unix": "Home paths",
}


@dataclass
class SensitiveMatch:
    """A single sensitive content match."""

    category: str  # Display category (e.g. "API keys")
    pattern_name: str  # Specific pattern (e.g. "api_key_openai")
    matched_text: str  # Redacted match
    source: str  # Prompt source (e.g. "claude-code")
    prompt_id: int | None = None


@dataclass
class SensitiveScanResult:
    """Aggregate result of scanning all prompts."""

    prompts_scanned: int = 0
    matches: list[SensitiveMatch] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
    category_sources: dict[str, set[str]] = field(default_factory=dict)
    highest_risk: SensitiveMatch | None = None


def _redact(text: str, keep_prefix: int = 4, keep_suffix: int = 0) -> str:
    """Redact sensitive text, keeping a small prefix for identification."""
    if len(text) <= keep_prefix + keep_suffix + 3:
        return text[:keep_prefix] + "***"
    prefix = text[:keep_prefix]
    suffix = text[-keep_suffix:] if keep_suffix else ""
    return f"{prefix}***{suffix}"


def _is_safe_ip(ip: str) -> bool:
    """Check if an IP is a safe/common address to ignore."""
    if ip in _SAFE_IPS:
        return True
    # Skip 10.x.x.x and 192.168.x.x private ranges (common in code examples)
    if ip.startswith("10.") or ip.startswith("192.168."):
        return True
    return False


def _is_safe_email(email: str) -> bool:
    """Check if an email is a safe/example address to ignore."""
    domain = email.split("@", 1)[-1].lower()
    if domain in _SAFE_EMAIL_DOMAINS:
        return True
    # Check if domain ends with a safe suffix (e.g. users.noreply.github.com)
    return any(domain.endswith(safe) for safe in _SAFE_EMAIL_DOMAINS)


def scan_prompts(
    prompts: list[dict],
) -> SensitiveScanResult:
    """Scan a list of prompt dicts for sensitive content.

    Each prompt dict should have at least 'text', 'source', and optionally 'id'.
    """
    result = SensitiveScanResult(prompts_scanned=len(prompts))

    # Risk priority for highest_risk selection
    risk_priority = {
        "SSH keys": 5,
        "API keys": 5,
        "Database credentials": 5,
        "Passwords": 4,
        "Env secrets": 4,
        "JWT tokens": 3,
        "Emails": 2,
        "IP addresses": 1,
        "Home paths": 0,
    }

    for prompt in prompts:
        text = prompt.get("text", "")
        source = prompt.get("source", "unknown")
        prompt_id = prompt.get("id")

        for pattern_name, pattern in PATTERNS.items():
            for m in pattern.finditer(text):
                matched = m.group(0)
                category = CATEGORY_MAP[pattern_name]

                # Apply safety filters
                if pattern_name == "ipv4" and _is_safe_ip(matched):
                    continue
                if pattern_name == "email" and _is_safe_email(matched):
                    continue

                match = SensitiveMatch(
                    category=category,
                    pattern_name=pattern_name,
                    matched_text=_redact(matched),
                    source=source,
                    prompt_id=prompt_id,
                )
                result.matches.append(match)

                # Update category counts
                result.category_counts[category] = result.category_counts.get(category, 0) + 1

                # Track sources per category
                if category not in result.category_sources:
                    result.category_sources[category] = set()
                result.category_sources[category].add(source)

                # Track highest risk
                if result.highest_risk is None or risk_priority.get(
                    category, 0
                ) > risk_priority.get(result.highest_risk.category, 0):
                    result.highest_risk = match

    return result
