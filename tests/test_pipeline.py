import unittest
from decimal import Decimal
from unittest import mock

from app.models import GlobalSettings
from app.pipeline import DISABLED_MESSAGE, run_price_adjustment


class TestPipeline(unittest.TestCase):
    @mock.patch("app.pipeline._write_audit")
    @mock.patch("app.pipeline.fetch_global_settings")
    def test_stops_when_disabled(self, mock_settings, mock_audit):
        mock_settings.return_value = GlobalSettings(auto_script_enabled=False)

        result = run_price_adjustment()

        self.assertEqual(result.status, "disabled")
        self.assertEqual(result.body, DISABLED_MESSAGE)
        mock_audit.assert_called_once()

    @mock.patch("app.pipeline._write_audit")
    @mock.patch("app.pipeline.fetch_catalog_targets")
    @mock.patch("app.pipeline.fetch_global_settings")
    def test_stops_when_no_products_in_firestore(self, mock_settings, mock_targets, mock_audit):
        mock_settings.return_value = GlobalSettings(auto_script_enabled=True)
        mock_targets.return_value = {}

        result = run_price_adjustment()

        self.assertEqual(result.status, "noop")
        mock_audit.assert_called_once()

    @mock.patch("app.pipeline._write_audit")
    @mock.patch("app.pipeline.build_price_updates")
    @mock.patch("app.pipeline.fetch_all_product_prices")
    @mock.patch("app.pipeline.OzonClient")
    @mock.patch("app.pipeline.fetch_catalog_targets")
    @mock.patch("app.pipeline.fetch_global_settings")
    def test_dry_run_from_firestore_settings(
        self,
        mock_settings,
        mock_targets,
        mock_client,
        mock_fetch_prices,
        mock_build_updates,
        mock_audit,
    ):
        mock_settings.return_value = GlobalSettings(
            auto_script_enabled=True,
            markup_percent=Decimal("5"),
            dry_run=True,
        )
        mock_targets.return_value = {"SKU-001": Decimal("1500")}
        mock_fetch_prices.return_value = [{"offer_id": "SKU-001"}]
        mock_build_updates.return_value = [{"offer_id": "SKU-001", "price": "1860"}]

        result = run_price_adjustment()

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.updated_count, 1)
        mock_audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
