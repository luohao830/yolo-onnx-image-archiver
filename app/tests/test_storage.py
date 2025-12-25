import tempfile
import unittest
from pathlib import Path

from app import storage


class TestStorage(unittest.TestCase):
    def test_init_and_upsert_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "app.db"
            storage.init_db(db)
            seen, inserted = storage.upsert_images(db, ["a.jpg", "b.jpg", "a.jpg"])
            self.assertEqual(seen, 3)
            self.assertEqual(inserted, 2)
            self.assertEqual(storage.count_images(db), 2)

    def test_predictions_top1_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "app.db"
            storage.init_db(db)
            storage.upsert_images(db, ["a.jpg"])
            storage.upsert_model(db, "m1", "/data/models/m1.onnx", 640, ["a"])
            run_id = storage.create_run(db, "m1", 0.25)
            storage.write_predictions_top1(db, run_id, "m1", [("a.jpg", "person", 0.9)], overwrite=True)
            storage.write_predictions_top1(db, run_id, "m1", [("a.jpg", "car", 0.8)], overwrite=True)
            labels = storage.list_labels(db, model_id="m1")
            self.assertEqual(labels, ["car"])


if __name__ == "__main__":
    unittest.main()

