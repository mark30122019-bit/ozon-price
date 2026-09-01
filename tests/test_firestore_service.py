import os
import unittest
from decimal import Decimal
from unittest import mock

from app.firestore_service import fetch_catalog_targets, fetch_global_settings
from app.models import GlobalSettings


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict | None, exists: bool = True) -> None:
        self.id = doc_id
        self._data = data
        self.exists = exists

    def to_dict(self) -> dict | None:
        return self._data


class _FakeDocument:
    def __init__(self, snapshot: _FakeSnapshot) -> None:
        self._snapshot = snapshot

    def get(self) -> _FakeSnapshot:
        return self._snapshot


class _FakeCollection:
    def __init__(self, documents: dict[str, _FakeSnapshot] | list[_FakeSnapshot]) -> None:
        if isinstance(documents, dict):
            self._documents = documents
            self._stream = None
        else:
            self._documents = None
            self._stream = documents

    def document(self, doc_id: str) -> _FakeDocument:
        snapshot = self._documents.get(doc_id, _FakeSnapshot(doc_id, None, exists=False))
        return _FakeDocument(snapshot)

    def stream(self):
        if self._stream is None:
            return iter(())
        return iter(self._stream)


class _FakeFirestoreClient:
    def __init__(self, collections: dict[str, _FakeCollection]) -> None:
        self._collections = collections

    def collection(self, name: str) -> _FakeCollection:
        return self._collections[name]


class TestFirestoreService(unittest.TestCase):
    def test_fetch_global_settings_matches_react_native_schema(self):
        db = _FakeFirestoreClient(
            {
                "settings": _FakeCollection(
                    {
                        "global": _FakeSnapshot(
                            "global",
                            {
                                "autoScriptEnabled": True,
                                "targetMarketPrice": 1500,
                                "markupPercent": 7,
                                "dryRun": True,
                            },
                        )
                    }
                )
            }
        )

        settings = fetch_global_settings(db=db)

        self.assertTrue(settings.auto_script_enabled)
        self.assertEqual(settings.target_market_price, Decimal("1500"))
        self.assertEqual(settings.markup_percent, Decimal("7"))
        self.assertTrue(settings.dry_run)

    def test_fetch_global_settings_missing_document(self):
        db = _FakeFirestoreClient({"settings": _FakeCollection({})})
        settings = fetch_global_settings(db=db)
        self.assertFalse(settings.auto_script_enabled)

    def test_fetch_catalog_targets_matches_react_native_schema(self):
        db = _FakeFirestoreClient(
            {
                "catalog": _FakeCollection(
                    [
                        _FakeSnapshot(
                            "SKU-001",
                            {"offerId": "SKU-001", "targetPrice": 1500, "isActive": True},
                        ),
                        _FakeSnapshot(
                            "SKU-002",
                            {"offerId": "SKU-002", "targetPrice": 2000, "isActive": False},
                        ),
                        _FakeSnapshot("broken", {"offerId": "broken", "isActive": True}),
                    ]
                )
            }
        )

        targets = fetch_catalog_targets(db=db)

        self.assertEqual(targets["SKU-001"], Decimal("1500"))
        self.assertNotIn("SKU-002", targets)
        self.assertNotIn("broken", targets)


class TestFirebaseCredentials(unittest.TestCase):
    def test_load_service_account_from_json_env(self):
        from app.env import _load_service_account_info

        payload = '{"type":"service_account","project_id":"demo"}'
        with mock.patch.dict(os.environ, {"FIREBASE_SERVICE_ACCOUNT_JSON": payload}, clear=True):
            info = _load_service_account_info()
        self.assertEqual(info["project_id"], "demo")

    def test_raises_when_credentials_missing(self):
        from app.env import _load_service_account_info

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                _load_service_account_info()


if __name__ == "__main__":
    unittest.main()
