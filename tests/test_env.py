import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.config import LOCAL_ENV_FILE
from app.env import is_dry_run, load_local_env


class TestLocalEnv(unittest.TestCase):
    def test_load_local_env_reads_file_without_overwriting_existing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "OZON_CLIENT_ID=from_file\n"
                "OZON_API_KEY=secret\n"
                "DRY_RUN=1\n",
                encoding="utf-8",
            )

            with mock.patch("app.env.LOCAL_ENV_FILE", env_path):
                with mock.patch.dict(
                    os.environ,
                    {"OZON_CLIENT_ID": "already_set"},
                    clear=True,
                ):
                    loaded = load_local_env()

                    self.assertTrue(loaded)
                    self.assertEqual(os.environ["OZON_CLIENT_ID"], "already_set")
                    self.assertEqual(os.environ["OZON_API_KEY"], "secret")
                    self.assertEqual(os.environ["DRY_RUN"], "1")

    def test_load_local_env_returns_false_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_env = Path(tmp_dir) / "missing.env"
            with mock.patch("app.env.LOCAL_ENV_FILE", missing_env):
                self.assertFalse(load_local_env())

    def test_is_dry_run(self):
        for value in ("1", "true", "TRUE", "yes", "on"):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"DRY_RUN": value}, clear=True):
                    self.assertTrue(is_dry_run())

        with mock.patch.dict(os.environ, {"DRY_RUN": "0"}, clear=True):
            self.assertFalse(is_dry_run())

    def test_local_env_file_points_to_project_root(self):
        project_root = Path(__file__).resolve().parent.parent
        self.assertEqual(LOCAL_ENV_FILE, project_root / ".env")


if __name__ == "__main__":
    unittest.main()
