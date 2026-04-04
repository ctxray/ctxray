"""Tests for telemetry HTTP batch sender (mocked urllib)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ctxray.telemetry.sender import DEFAULT_ENDPOINT, send_batch


class TestSendBatch:
    def test_send_empty_batch_is_noop(self):
        """Sending empty list should return True (nothing to do)."""
        result = send_batch([])
        assert result is True

    @patch("ctxray.telemetry.sender.urlopen")
    def test_send_batch_posts_json(self, mock_urlopen: MagicMock):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        events = [
            '{"install_id": "a", "score_total": 72.0}',
            '{"install_id": "b", "score_total": 55.0}',
        ]
        result = send_batch(events)
        assert result is True

        # Verify the request was made
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.full_url == DEFAULT_ENDPOINT
        assert request.get_header("Content-type") == "application/json"

        # Verify payload structure
        body = json.loads(request.data.decode())
        assert "events" in body
        assert len(body["events"]) == 2

    @patch("ctxray.telemetry.sender.urlopen")
    def test_send_batch_timeout_returns_false(self, mock_urlopen: MagicMock):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("timeout")
        events = ['{"test": true}']
        result = send_batch(events)
        assert result is False

    @patch("ctxray.telemetry.sender.urlopen")
    def test_send_batch_server_error_returns_false(self, mock_urlopen: MagicMock):
        from io import BytesIO
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            DEFAULT_ENDPOINT, 500, "Internal Server Error", {}, BytesIO(b"")
        )
        events = ['{"test": true}']
        result = send_batch(events)
        assert result is False

    @patch("ctxray.telemetry.sender.urlopen")
    def test_send_batch_uses_2s_timeout(self, mock_urlopen: MagicMock):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        send_batch(['{"x": 1}'])
        call_args = mock_urlopen.call_args
        assert call_args[1].get("timeout") == 2

    def test_send_batch_with_custom_endpoint(self):
        """Custom endpoint should be used in request."""
        with patch("ctxray.telemetry.sender.urlopen") as mock:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock.return_value = mock_response

            send_batch(['{"x": 1}'], endpoint="https://custom.example.com/v1/events")
            request = mock.call_args[0][0]
            assert request.full_url == "https://custom.example.com/v1/events"

    @patch("ctxray.telemetry.sender.urlopen")
    def test_send_batch_generic_exception_returns_false(self, mock_urlopen: MagicMock):
        """Any unexpected exception should be caught and return False."""
        mock_urlopen.side_effect = OSError("network error")
        result = send_batch(['{"test": true}'])
        assert result is False
