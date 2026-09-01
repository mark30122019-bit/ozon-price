import unittest
from decimal import Decimal

from app.pricing import (
    build_price_updates,
    calculate_desired_site_price,
    calculate_new_base_price,
    get_base_price,
    get_price_with_ozon_card,
    to_decimal,
)

PRODUCT_TARGETS = {
    "SKU-001": Decimal("1500"),
    "SKU-002": Decimal("1500"),
    "SKU-005": Decimal("1500"),
}


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


class TestCalculateDesiredSitePrice(unittest.TestCase):
    def test_adds_five_percent(self):
        result = calculate_desired_site_price(Decimal("1200"), Decimal("5"))
        self.assertEqual(result, Decimal("1260"))

    def test_custom_markup_percent(self):
        result = calculate_desired_site_price(Decimal("1000"), Decimal("10"))
        self.assertEqual(result, Decimal("1100"))


class TestCalculateNewBasePrice(unittest.TestCase):
    def test_increases_base_by_markup_when_below_target(self):
        result = calculate_new_base_price(
            Decimal("1200"),
            Decimal("1800"),
            target_price=Decimal("1500"),
            markup_percent=Decimal("5"),
        )
        self.assertEqual(result, Decimal("1860"))

    def test_returns_none_when_card_price_equals_target(self):
        result = calculate_new_base_price(
            Decimal("1500"),
            Decimal("2000"),
            target_price=Decimal("1500"),
            markup_percent=Decimal("5"),
        )
        self.assertIsNone(result)

    def test_returns_none_when_card_price_above_target(self):
        result = calculate_new_base_price(
            Decimal("1600"),
            Decimal("2000"),
            target_price=Decimal("1500"),
            markup_percent=Decimal("5"),
        )
        self.assertIsNone(result)

    def test_rounds_result_to_integer(self):
        result = calculate_new_base_price(
            Decimal("1200.7"),
            Decimal("1800.4"),
            target_price=Decimal("1500"),
            markup_percent=Decimal("5"),
        )
        self.assertEqual(result, Decimal("1861"))

    def test_custom_target_and_markup(self):
        result = calculate_new_base_price(
            Decimal("900"),
            Decimal("1000"),
            target_price=Decimal("1000"),
            markup_percent=Decimal("5"),
        )
        self.assertEqual(result, Decimal("1045"))


class TestBuildPriceUpdates(unittest.TestCase):
    def test_builds_updates_only_for_items_below_target_in_firebase(self):
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

        updates = build_price_updates(
            items,
            product_targets=PRODUCT_TARGETS,
            markup_percent=Decimal("5"),
        )

        self.assertEqual(updates, [{"offer_id": "SKU-001", "price": "1860"}])

    def test_skips_items_not_in_catalog(self):
        items = [
            {
                "offer_id": "SKU-UNKNOWN",
                "product_id": 99,
                "price": {"price": 1800},
                "price_indexes": {"price_with_ozon_card": 1200},
            }
        ]
        self.assertEqual(
            build_price_updates(items, product_targets=PRODUCT_TARGETS, markup_percent=Decimal("5")),
            [],
        )

    def test_skips_items_without_offer_id(self):
        items = [
            {
                "product_id": 1,
                "price": {"price": 1800},
                "price_indexes": {"price_with_ozon_card": 1200},
            }
        ]
        self.assertEqual(
            build_price_updates(items, product_targets=PRODUCT_TARGETS, markup_percent=Decimal("5")),
            [],
        )

    def test_skips_items_without_ozon_card_price(self):
        items = [
            {
                "offer_id": "SKU-001",
                "product_id": 3,
                "price": {"price": 1800},
                "price_indexes": {},
            }
        ]
        self.assertEqual(
            build_price_updates(items, product_targets=PRODUCT_TARGETS, markup_percent=Decimal("5")),
            [],
        )

    def test_skips_items_without_base_price(self):
        items = [
            {
                "offer_id": "SKU-001",
                "product_id": 4,
                "price": {},
                "price_indexes": {"price_with_ozon_card": 1200},
            }
        ]
        self.assertEqual(
            build_price_updates(items, product_targets=PRODUCT_TARGETS, markup_percent=Decimal("5")),
            [],
        )

    def test_price_is_string_as_required_by_ozon(self):
        items = [
            {
                "offer_id": "SKU-005",
                "product_id": 5,
                "price": {"price": 1000},
                "price_indexes": {"price_with_ozon_card": 1000},
            }
        ]

        updates = build_price_updates(
            items,
            product_targets=PRODUCT_TARGETS,
            markup_percent=Decimal("5"),
        )

        self.assertEqual(len(updates), 1)
        self.assertIsInstance(updates[0]["price"], str)
        self.assertEqual(updates[0]["price"], "1050")


if __name__ == "__main__":
    unittest.main()
