"""Integration test: HMAC signing matches what the Worker expects."""

from __future__ import annotations

import hashlib
import hmac

from reprompt.sharing.client import sign_request


class TestHmacCompatibility:
    """Verify Python HMAC output matches the format the TS Worker expects."""

    def test_hmac_produces_64_char_hex(self):
        sig = sign_request("a" * 64, '{"test": true}')
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_hmac_is_deterministic(self):
        sig1 = sign_request("a" * 64, '{"test": true}')
        sig2 = sign_request("a" * 64, '{"test": true}')
        assert sig1 == sig2

    def test_hmac_matches_stdlib(self):
        install_id = "b" * 64
        body = '{"total_prompts": 100}'
        sig = sign_request(install_id, body)
        expected = hmac.new(install_id.encode(), body.encode(), hashlib.sha256).hexdigest()
        assert sig == expected
