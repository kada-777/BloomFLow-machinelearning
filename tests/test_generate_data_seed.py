import csv
import pathlib
import subprocess
import sys
import unittest
from datetime import date


ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output_v2"


def read_rows(filename):
    with (OUT_DIR / filename).open(newline="") as f:
        return list(csv.DictReader(f))


class GenerateDataSeedV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [sys.executable, "generate_data_seed.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_writes_versioned_output_folder(self):
        self.assertTrue(OUT_DIR.is_dir())
        self.assertTrue((OUT_DIR / "flower_batches.csv").is_file())

    def test_receiving_is_not_multiplied_by_farm_count(self):
        receiving_items = read_rows("receiving_items.csv")
        accepted_total = sum(int(row["acceptedQuantity"]) for row in receiving_items)

        daily_sales_items = read_rows("daily_sales_items.csv")
        sold_total = sum(int(row["soldQuantity"]) for row in daily_sales_items)

        self.assertGreater(sold_total, 0)
        self.assertLess(accepted_total / sold_total, 1.35)

    def test_ho_stock_is_qc_pass_through_not_large_storage(self):
        flower_batches = read_rows("flower_batches.csv")
        ending_ho_stock = sum(int(row["availableQuantity"]) for row in flower_batches)
        initial_ho_stock = sum(int(row["initialQuantity"]) for row in flower_batches)

        self.assertGreater(initial_ho_stock, 0)
        self.assertLess(ending_ho_stock, initial_ho_stock * 0.01)

    def test_sales_never_exceed_sellable_branch_stock(self):
        movements = read_rows("inventory_movements.csv")
        branch_totals = {}
        for row in movements:
            if row["locationType"] != "BRANCH" or row["branchId"] == "":
                continue

            key = (row["branchId"], row["flowerId"])
            qty_before = int(row["qtyBefore"])
            qty_after = int(row["qtyAfter"])
            quantity = int(row["quantity"])

            self.assertEqual(branch_totals.get(key, 0), qty_before)
            if row["type"] in {"SALE_OUT", "DAMAGED_OUT"}:
                self.assertLessEqual(quantity, qty_before)
            self.assertGreaterEqual(qty_after, 0)
            branch_totals[key] = qty_after


if __name__ == "__main__":
    unittest.main()
