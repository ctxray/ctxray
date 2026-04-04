"""Tests for sharing client -- HMAC signing and HTTP upload."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

from ctxray.sharing.client import sign_request, upload_share


class TestSignRequest:
    def test_produces_hex_hmac(self):
        install_id = "a" * 64
        body = '{"test": true}'
        sig = sign_request(install_id, body)
        expected = hmac.new(install_id.encode(), body.encode(), hashlib.sha256).hexdigest()
        assert sig == expected
        assert len(sig) == 64

    def test_different_bodies_produce_different_signatures(self):
        install_id = "b" * 64
        sig1 = sign_request(install_id, '{"a": 1}')
        sig2 = sign_request(install_id, '{"a": 2}')
        assert sig1 != sig2


class TestUploadShare:
    @patch("ctxray.sharing.client.urlopen")
    def test_success_returns_url(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {"url": "https://getreprompt.dev/w/abc12345"}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        url = upload_share(
            install_id="a" * 64,
            report_json='{"total_prompts": 100}',
        )
        assert url == "https://getreprompt.dev/w/abc12345"

    @patch("ctxray.sharing.client.urlopen")
    def test_401_raises_auth_error(self, mock_urlopen):
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="", code=401, msg="Unauthorized", hdrs=None, fp=None
        )
        with pytest.raises(RuntimeError, match="auth"):
            upload_share(install_id="a" * 64, report_json="{}")

    @patch("ctxray.sharing.client.urlopen")
    def test_network_error_raises(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("offline")
        with pytest.raises(RuntimeError, match="network"):
            upload_share(install_id="a" * 64, report_json="{}")
