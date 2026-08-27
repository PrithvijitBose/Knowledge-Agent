import os
import hmac
import hashlib
import json
import unittest
from unittest.mock import patch, MagicMock

import webhook_server


class TestWebhookSecurity(unittest.TestCase):
    def setUp(self):
        self.secret = "test_secret_12345"
        self.payload = json.dumps({"action": "created", "comment": {"body": "@Knowledge test"}}).encode("utf-8")

    def _compute_sig(self, body: bytes, secret: str) -> str:
        mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={mac}"

    def test_verify_signature_valid(self):
        sig = self._compute_sig(self.payload, self.secret)
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": self.secret}):
            self.assertTrue(webhook_server.verify_signature(self.payload, sig))

    def test_verify_signature_tampered_payload(self):
        sig = self._compute_sig(self.payload, self.secret)
        tampered = json.dumps({"action": "created", "comment": {"body": "tampered"}}).encode("utf-8")
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": self.secret}):
            self.assertFalse(webhook_server.verify_signature(tampered, sig))

    def test_verify_signature_invalid_header(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": self.secret}):
            self.assertFalse(webhook_server.verify_signature(self.payload, "invalid_header"))
            self.assertFalse(webhook_server.verify_signature(self.payload, None))

    def test_verify_signature_no_secret_configured(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": ""}):
            # When no secret is configured, fails closed for security
            self.assertFalse(webhook_server.verify_signature(self.payload, None))
            self.assertFalse(webhook_server.verify_signature(self.payload, "sha256=somesig"))


if __name__ == "__main__":
    unittest.main()
