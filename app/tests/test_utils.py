import os
import tempfile
import unittest
from pathlib import Path

from app import utils


class TestUtils(unittest.TestCase):
    def test_sanitize_label(self):
        self.assertEqual(utils.sanitize_label("person"), "person")
        self.assertEqual(utils.sanitize_label("a/b"), "a_b")
        self.assertEqual(utils.sanitize_label(""), "unknown")
        self.assertEqual(utils.sanitize_label("---"), "unknown")

    def test_link_or_copy_to_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "a.jpg"
            src.write_bytes(b"abc")
            dest_dir = base / "out"

            dest, mode = utils.link_or_copy_to_dir(src=src, dest_dir=dest_dir, prefer_hardlink=True)
            self.assertTrue(dest.exists())
            self.assertIn(mode, {"hardlink", "copy"})
            if mode == "hardlink" and os.name != "nt":
                self.assertEqual(os.stat(src).st_ino, os.stat(dest).st_ino)


if __name__ == "__main__":
    unittest.main()

