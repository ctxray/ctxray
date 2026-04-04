"""Tests for sensitive content detection (privacy --deep)."""

from __future__ import annotations

from ctxray.core.privacy_scan import scan_prompts


def _prompt(text: str, source: str = "claude-code", pid: int = 1) -> dict:
    return {"text": text, "source": source, "id": pid}


# ---------------------------------------------------------------------------
# API key detection
# ---------------------------------------------------------------------------


class TestAPIKeys:
    def test_openai_key(self):
        r = scan_prompts([_prompt("Use sk-proj-abc123def456ghi789jkl012mno345")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_aws_key(self):
        r = scan_prompts([_prompt("Set AKIAIOSFODNN7EXAMPLE as the access key")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_github_pat(self):
        r = scan_prompts([_prompt("Token: ghp_abcdefghijklmnopqrstuvwxyz0123456789")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_anthropic_key(self):
        r = scan_prompts([_prompt("sk-ant-api03-abcdefghijklmnop")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_no_false_positive_short_sk(self):
        """'sk-' followed by short text should not match."""
        r = scan_prompts([_prompt("Use sk-abc for testing")])
        assert r.category_counts.get("API keys", 0) == 0


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


class TestJWT:
    def test_jwt_detected(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        r = scan_prompts([_prompt(f"Bearer {jwt}")])
        assert r.category_counts.get("JWT tokens", 0) >= 1


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------


class TestEmails:
    def test_real_email_detected(self):
        r = scan_prompts([_prompt("Contact admin@company.com for access")])
        assert r.category_counts.get("Emails", 0) >= 1

    def test_example_email_excluded(self):
        r = scan_prompts([_prompt("Use user@example.com as test")])
        assert r.category_counts.get("Emails", 0) == 0

    def test_noreply_github_excluded(self):
        r = scan_prompts([_prompt("user@users.noreply.github.com")])
        assert r.category_counts.get("Emails", 0) == 0


# ---------------------------------------------------------------------------
# IP addresses
# ---------------------------------------------------------------------------


class TestIPs:
    def test_public_ip_detected(self):
        r = scan_prompts([_prompt("Connect to 45.33.32.156 via SSH")])
        assert r.category_counts.get("IP addresses", 0) >= 1

    def test_localhost_excluded(self):
        r = scan_prompts([_prompt("Running on 127.0.0.1:8080")])
        assert r.category_counts.get("IP addresses", 0) == 0

    def test_private_range_excluded(self):
        r = scan_prompts([_prompt("Server at 192.168.1.100")])
        assert r.category_counts.get("IP addresses", 0) == 0

    def test_10_range_excluded(self):
        r = scan_prompts([_prompt("Pod IP 10.0.0.42")])
        assert r.category_counts.get("IP addresses", 0) == 0


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


class TestPasswords:
    def test_password_assignment(self):
        r = scan_prompts([_prompt('password = "mysecret123"')])
        assert r.category_counts.get("Passwords", 0) >= 1

    def test_passwd_colon(self):
        r = scan_prompts([_prompt("passwd: hunter2_secret")])
        assert r.category_counts.get("Passwords", 0) >= 1


# ---------------------------------------------------------------------------
# Env secrets
# ---------------------------------------------------------------------------


class TestEnvSecrets:
    def test_database_url(self):
        r = scan_prompts([_prompt("DATABASE_URL=postgres://user:pass@host/db")])
        assert r.category_counts.get("Env secrets", 0) >= 1

    def test_secret_key(self):
        r = scan_prompts([_prompt("SECRET_KEY=abc123def456")])
        assert r.category_counts.get("Env secrets", 0) >= 1


# ---------------------------------------------------------------------------
# Home paths
# ---------------------------------------------------------------------------


class TestHomePaths:
    def test_macos_home_path(self):
        r = scan_prompts([_prompt("Edit /Users/chris/projects/app/main.py")])
        assert r.category_counts.get("Home paths", 0) >= 1

    def test_linux_home_path(self):
        r = scan_prompts([_prompt("Config at /home/deploy/.bashrc")])
        assert r.category_counts.get("Home paths", 0) >= 1


# ---------------------------------------------------------------------------
# SSH keys & certificates
# ---------------------------------------------------------------------------


class TestSSHKeys:
    def test_rsa_private_key(self):
        r = scan_prompts([_prompt("-----BEGIN RSA PRIVATE KEY-----\nMIIEow...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_openssh_private_key(self):
        r = scan_prompts([_prompt("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Blbn...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_ec_private_key(self):
        r = scan_prompts([_prompt("-----BEGIN EC PRIVATE KEY-----\nMHQCAQ...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_dsa_private_key(self):
        r = scan_prompts([_prompt("-----BEGIN DSA PRIVATE KEY-----\nMIIBuw...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_pkcs8_private_key(self):
        r = scan_prompts([_prompt("-----BEGIN PRIVATE KEY-----\nMIIEvg...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_encrypted_private_key(self):
        r = scan_prompts([_prompt("-----BEGIN ENCRYPTED PRIVATE KEY-----\nMIIFH...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_pem_certificate(self):
        r = scan_prompts([_prompt("-----BEGIN CERTIFICATE-----\nMIIDXTCC...")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_ssh_key_path_rsa(self):
        r = scan_prompts([_prompt("Copy your key from ~/.ssh/id_rsa")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_ssh_key_path_ed25519(self):
        r = scan_prompts([_prompt("cat ~/.ssh/id_ed25519")])
        assert r.category_counts.get("SSH keys", 0) >= 1

    def test_no_false_positive_public_key_header(self):
        """Public key headers are not private keys."""
        r = scan_prompts([_prompt("-----BEGIN PUBLIC KEY-----\nMIIBIj...")])
        assert r.category_counts.get("SSH keys", 0) == 0


# ---------------------------------------------------------------------------
# Slack / Google / npm tokens
# ---------------------------------------------------------------------------


class TestServiceTokens:
    def test_slack_bot_token(self):
        # Token constructed to avoid GitHub push protection
        prefix = "xoxb-"
        r = scan_prompts([_prompt(f"SLACK_TOKEN={prefix}fake-test-token-placeholder")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_slack_user_token(self):
        prefix = "xoxp-"
        r = scan_prompts([_prompt(f"{prefix}fake-test-token-placeholder-val")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_slack_app_token(self):
        prefix = "xapp-"
        r = scan_prompts([_prompt(f"{prefix}fake-test-token-placeholder-val")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_google_api_key(self):
        r = scan_prompts([_prompt("key=AIzaSyA1234567890abcdefghijklmnopqrstuv")])
        assert r.category_counts.get("API keys", 0) >= 1

    def test_npm_token(self):
        token = "npm_abcdefghijklmnopqrstuvwxyz0123456789"
        r = scan_prompts([_prompt(f"//registry.npmjs.org/:_authToken={token}")])
        assert r.category_counts.get("API keys", 0) >= 1


# ---------------------------------------------------------------------------
# Database connection strings
# ---------------------------------------------------------------------------


class TestDatabaseCredentials:
    def test_postgres_url(self):
        r = scan_prompts([_prompt("postgres://admin:secret@db.example.com:5432/mydb")])
        assert r.category_counts.get("Database credentials", 0) >= 1

    def test_postgresql_url(self):
        r = scan_prompts([_prompt("postgresql://user:pass@localhost/db")])
        assert r.category_counts.get("Database credentials", 0) >= 1

    def test_mongodb_url(self):
        r = scan_prompts([_prompt("mongodb://root:p4ssw0rd@mongo.internal:27017/app")])
        assert r.category_counts.get("Database credentials", 0) >= 1

    def test_mongodb_srv_url(self):
        r = scan_prompts([_prompt("mongodb+srv://user:pass@cluster0.abc.mongodb.net/db")])
        assert r.category_counts.get("Database credentials", 0) >= 1

    def test_mysql_url(self):
        r = scan_prompts([_prompt("mysql://root:secret@127.0.0.1:3306/app")])
        assert r.category_counts.get("Database credentials", 0) >= 1

    def test_redis_url(self):
        r = scan_prompts([_prompt("redis://default:mypassword@redis.host:6379/0")])
        assert r.category_counts.get("Database credentials", 0) >= 1

    def test_no_false_positive_without_creds(self):
        """Connection string without user:pass should not match."""
        r = scan_prompts([_prompt("postgres://localhost:5432/mydb")])
        assert r.category_counts.get("Database credentials", 0) == 0


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestScanIntegration:
    def test_empty_prompts(self):
        r = scan_prompts([])
        assert r.prompts_scanned == 0
        assert len(r.matches) == 0

    def test_clean_prompts(self):
        r = scan_prompts(
            [
                _prompt("Fix the auth bug in login.py"),
                _prompt("Add unit tests for the parser module"),
            ]
        )
        assert len(r.matches) == 0

    def test_multiple_categories(self):
        r = scan_prompts(
            [
                _prompt("Use sk-proj-abc123def456ghi789jkl012mno345 for API"),
                _prompt("Contact admin@company.com about the password = hunter2"),
            ]
        )
        assert len(r.category_counts) >= 2

    def test_source_tracking(self):
        r = scan_prompts(
            [
                _prompt("sk-proj-abc123def456ghi789jkl012mno345", source="chatgpt"),
                _prompt("sk-proj-xyz987abc654def321ghi098jkl765", source="claude-code"),
            ]
        )
        sources = r.category_sources.get("API keys", set())
        assert "chatgpt" in sources
        assert "claude-code" in sources

    def test_highest_risk_is_api_key(self):
        """API keys should rank higher than home paths."""
        r = scan_prompts(
            [
                _prompt("/Users/chris/file.py"),
                _prompt("sk-proj-abc123def456ghi789jkl012mno345"),
            ]
        )
        assert r.highest_risk is not None
        assert r.highest_risk.category == "API keys"

    def test_redaction(self):
        r = scan_prompts([_prompt("sk-proj-abc123def456ghi789jkl012mno345")])
        assert len(r.matches) >= 1
        assert "***" in r.matches[0].matched_text
        # Should NOT contain the full key
        assert "def456ghi789" not in r.matches[0].matched_text
