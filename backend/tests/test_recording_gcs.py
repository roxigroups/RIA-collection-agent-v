"""Unit tests for GCS recording archival fallback in ria/recording.py."""
import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock

from ria import recording


class GCSRecordingTests(unittest.TestCase):
    def test_gcs_disabled_returns_none(self):
        """When GCS_RECORDINGS_BUCKET is unset, archive_to_gcs gracefully returns None."""
        with patch.dict(os.environ, {"GCS_RECORDINGS_BUCKET": ""}):
            result = asyncio.run(recording.archive_to_gcs("test_call.ogg"))
            self.assertIsNone(result)

    def test_gcs_missing_file_returns_none(self):
        """When the local file does not exist, archive_to_gcs returns None without throwing."""
        with patch.dict(os.environ, {"GCS_RECORDINGS_BUCKET": "my-bucket"}):
            result = asyncio.run(recording.archive_to_gcs("non_existent_call_123.ogg"))
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
