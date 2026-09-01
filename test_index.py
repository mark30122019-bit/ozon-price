import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from index import (
    TARGET_MARKET_PRICE,
    build_price_updates,
    calculate_new_base_price,
    get_base_price,
    get_price_with_ozon_card,
    is_dry_run,
    load_local_env,
    to_decimal,
)


class TestToDecimal(unittest.TestCase):
    def test_converts_int_and_string(self):
        self.assertEqual(to_decimal(1200), Decimal("1200"))
        self.assertEqual(to_decimal("1499.5"), Decimal("1499.5"))

    def test_returns_none_for_invalid_values(self):
        self.assertIsNone(to_decimal(None))
        self.assertIsNone(to_decimal(""))
        self.assertIsNone(to_decimal("not-a-number"))


class TestPriceExtraction(unittest.TestCase):
    def test_get_price_with_ozon_card(self):
        item = {"price_indexes": {"price_with_ozon_card": 1200}}
        self.assertEqual(get_price_with_ozon_card(item), Decimal("1200"))

    def test_get_price_with_ozon_card_missing(self):
        self.assertIsNone(get_price_with_ozon_card({}))
        self.assertIsNone(get_price_with_ozon_card({"price_indexes": {}}))

    def test_get_base_price(self):
        item = {"price": {"price": 1800}}
        self.assertEqual(get_base_price(item), Decimal("1800"))

    def test_get_base_price_missing(self):
        self.assertIsNone(get_base_price({}))
        self.assertIsNone(get_base_price({"price": {}}))


class TestCalculateNewBasePrice(unittest.TestCase):
    def test_increases_base_when_card_price_below_target(self):
        # TARGET=1500, card=1200, base=1800 -> diff=300 -> new base=2100
        result = calculate_new_base_price(Decimal("1200"), Decimal("1800"))
        self.assertEqual(result, Decimal("2100"))

    def test_returns_none_when_card_price_equals_target(self):
        result = calculate_new_base_price(Decimal(str(TARGET_MARKET_PRICE)), Decimal("2000"))
        self.assertIsNone(result)

    def test_returns_none_when_card_price_above_target(self):
        result = calculate_new_base_price(Decimal("1600"), Decimal("2000"))
        self.assertIsNone(result)

    def test_rounds_result_to_integer(self):
        result = calculate_new_base_price(Decimal("1200.7"), Decimal("1800.4"))
        self.assertEqual(result, Decimal("2100"))

    def test_custom_target_market_price(self):
        result = calculate_new_base_price(
            Decimal("900"),
            Decimal("1000"),
            target_market_price=Decimal("1000"),
        )
        self.assertEqual(result, Decimal("1100"))


class TestBuildPriceUpdates(unittest.TestCase):
    def test_builds_updates_only_for_items_below_target(self):
        items = [
            {
                "offer_id": "SKU-001",
                "product_id": 1,
                "price": {"price": 1800},
                "price_indexes": {"price_with_ozon_card": 1200},
            },
            {
                "offer_id": "SKU-002",
                "product_id": 2,
                "price": {"price": 1600},
                "price_indexes": {"price_with_ozon_card": 1550},
            },
        ]

        updates = build_price_updates(items)

        self.assertEqual(updates, [{"offer_id": "SKU-001", "price": "2100"}])

    def test_skips_items_without_offer_id(self):
        items = [
            {
                "product_id": 1,
                "price": {"price": 1800},
                "price_indexes": {"price_with_ozon_card": 1200},
            }
        ]
        self.assertEqual(build_price_updates(items), [])

    def test_skips_items_without_ozon_card_price(self):
        items = [
            {
                "offer_id": "SKU-003",
                "product_id": 3,
                "price": {"price": 1800},
                "price_indexes": {},
            }
        ]
        self.assertEqual(build_price_updates(items), [])

    def test_skips_items_without_base_price(self):
        items = [
            {
                "offer_id": "SKU-004",
                "product_id": 4,
                "price": {},
                "price_indexes": {"price_with_ozon_card": 1200},
            }
        ]
        self.assertEqual(build_price_updates(items), [])

    def test_price_is_string_as_required_by_ozon(self):
        items = [
            {
                "offer_id": "SKU-005",
                "product_id": 5,
                "price": {"price": 1000},
                "price_indexes": {"price_with_ozon_card": 1000},
            }
        ]

        updates = build_price_updates(items)

        self.assertEqual(len(updates), 1)
        self.assertIsInstance(updates[0]["price"], str)
        self.assertEqual(updates[0]["price"], "1500")


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

            with mock.patch("index.LOCAL_ENV_FILE", env_path):
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
            with mock.patch("index.LOCAL_ENV_FILE", missing_env):
                self.assertFalse(load_local_env())

    def test_is_dry_run(self):
        for value in ("1", "true", "TRUE", "yes", "on"):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"DRY_RUN": value}, clear=True):
                    self.assertTrue(is_dry_run())

        with mock.patch.dict(os.environ, {"DRY_RUN": "0"}, clear=True):
            self.assertFalse(is_dry_run())


if __name__ == "__main__":
    unittest.main()
