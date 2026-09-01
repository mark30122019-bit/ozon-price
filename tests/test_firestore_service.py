import os
import unittest
from decimal import Decimal
from unittest import mock

from app.firestore_service import fetch_global_settings, fetch_product_targets
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
    def test_fetch_global_settings_active(self):
        db = _FakeFirestoreClient(
            {
                "settings": _FakeCollection(
                    {
                        "global": _FakeSnapshot(
                            "global",
                            {"is_active": True, "site_price_markup_percent": 7},
                        )
                    }
                )
            }
        )

        settings = fetch_global_settings(db=db)

        self.assertTrue(settings.is_active)
        self.assertEqual(settings.site_price_markup_percent, Decimal("7"))

    def test_fetch_global_settings_missing_document(self):
        db = _FakeFirestoreClient({"settings": _FakeCollection({})})
        settings = fetch_global_settings(db=db)
        self.assertFalse(settings.is_active)

    def test_fetch_product_targets(self):
        db = _FakeFirestoreClient(
            {
                "products": _FakeCollection(
                    [
                        _FakeSnapshot("SKU-001", {"target_price": 1500}),
                        _FakeSnapshot("SKU-002", {"offer_id": "SKU-002", "target_price": 2000}),
                        _FakeSnapshot("broken", {}),
                    ]
                )
            }
        )

        targets = fetch_product_targets(db=db)

        self.assertEqual(targets["SKU-001"], Decimal("1500"))
        self.assertEqual(targets["SKU-002"], Decimal("2000"))
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
