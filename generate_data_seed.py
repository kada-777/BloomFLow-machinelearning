"""
BloomFlow - Chained seed data generator
========================================

Generates historically-consistent CSVs for every table in the dependency
chain, in order, sharing in-memory state so downstream tables never exceed
what upstream tables actually produced.

Chain (each stage only uses data produced by the stage before it):

    farms, branches, flowers          (static master data from CSVs)
      -> receivings / receiving_items (farm -> HO, accepted vs unusable)
        -> flower_batches             (HO stock, allocated same day)
          -> distribution_orders / distribution_order_items / distribution_batch_allocations
             -> distribution_receipts / distribution_receipt_items
               -> branch_stock_lots   (branch stock, aged from farm ship date)
                 -> daily_sales / daily_sales_items  (capped by real stock)
                   -> inventory_movements (audit trail for every step above)

Explicitly NOT generated here (these are the app/model's own output, not
history to fabricate):
    forecast_runs, forecast_results, distribution_plans, distribution_plan_items

Run:
    python generate_data_seed.py
Output:
    ./output/*.csv
"""

import csv
import os
import random
from datetime import date, timedelta

random.seed(42)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
END_DATE = date(2026, 8, 12)
SALES_START = date(2025, 8, 12)  # 1 year of sales data
LEAD_IN_DAYS = 14  # give HO time to stock up before branches start selling
START_DATE = SALES_START - timedelta(days=LEAD_IN_DAYS)

FRESH_DAYS = 7
GRADE_C_DAYS = 4
MAX_SELLABLE_AGE = FRESH_DAYS + GRADE_C_DAYS  # >11 days -> DAMAGED, not sellable

UNUSABLE_RATE_RANGE = (0.02, 0.08)   # farm -> HO rejection rate
TRANSIT_DAMAGE_RATE_RANGE = (0.00, 0.03)
TRANSIT_MISSING_RATE_RANGE = (0.00, 0.02)
SALE_DAMAGE_RATE_RANGE = (0.01, 0.06)

# Weekly multiplier ranges [min, max] per weekday (0=Monday, 6=Sunday)
WEEKLY_RANGES = {
    0: (0.75, 0.90),  # Monday
    1: (0.75, 0.90),  # Tuesday
    2: (0.80, 0.95),  # Wednesday
    3: (0.90, 1.05),  # Thursday
    4: (1.00, 1.15),  # Friday
    5: (1.10, 1.30),  # Saturday
    6: (1.05, 1.25),  # Sunday
}

# Seasonal spikes: (month, day) -> (range_min, range_max, duration_days)
# Updated for 2025-2026 period
SEASONAL_SPIKES = {
    (2, 14): (1.45, 1.75, 3),  # Valentine
    (5, 1):  (1.15, 1.35, 14), # Graduation May
    (11, 1): (1.15, 1.35, 14), # Graduation Nov
    (12, 22): (1.10, 1.30, 5), # Christmas
    (3, 30): (1.25, 1.50, 5),  # Lebaran 2026 (March 30 - April 1)
    (4, 21): (1.10, 1.25, 3),  # Hari Kartini
    (8, 17): (1.15, 1.35, 5),  # Kemerdekaan RI
    (8, 12): (1.05, 1.15, 3),  # Hari Ayah (optional, minor)
    (12, 25): (1.10, 1.30, 5), # Christmas
}

# Base quantity range per branch (different market sizes)
BRANCH_BASE_RANGES = {
    1: (18, 38),   # Jakarta Pusat - biggest market
    2: (12, 28),   # Bandung
    3: (10, 24),   # Bekasi
    4: (15, 34),   # Surabaya - second biggest market
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
OUT_DIR = os.path.join(SCRIPT_DIR, "output_v2")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# ID counters
# ---------------------------------------------------------------------------
class Counter:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return self.n


ids = {
    "receiving": Counter(),
    "receiving_item": Counter(),
    "batch": Counter(),
    "order": Counter(),
    "order_item": Counter(),
    "allocation": Counter(),
    "receipt": Counter(),
    "receipt_item": Counter(),
    "lot": Counter(),
    "sale": Counter(),
    "sale_item": Counter(),
    "movement": Counter(),
}


# ---------------------------------------------------------------------------
# Helper: read CSV
# ---------------------------------------------------------------------------
def read_csv(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ---------------------------------------------------------------------------
# Stage 0: master data from CSVs
# ---------------------------------------------------------------------------
farms = read_csv("farms_rows.csv")
branches = read_csv("branches_rows.csv")
flowers = read_csv("flowers_rows.csv")

farm_ids = [int(f["id"]) for f in farms]
branch_ids = [int(b["id"]) for b in branches]
flower_ids = [int(f["id"]) for f in flowers]


# ---------------------------------------------------------------------------
# Seasonality functions
# ---------------------------------------------------------------------------
def get_weekly_multiplier(date_val):
    """Returns uniform random within range for the day of week."""
    weekday = date_val.weekday()
    min_mult, max_mult = WEEKLY_RANGES[weekday]
    return random.uniform(min_mult, max_mult)


def get_seasonal_multiplier(date_val):
    """Returns spike multiplier if date is near a seasonal event, else 1.0."""
    for (sm, sd), (smin, smax, duration) in SEASONAL_SPIKES.items():
        try:
            spike_date = date_val.replace(month=sm, day=sd)
        except ValueError:
            continue
        days_diff = abs((date_val - spike_date).days)
        if days_diff <= duration:
            return random.uniform(smin, smax)
    return 1.0


def calculate_daily_demand(branch_id, flower_id, date_val):
    """Calculate daily demand with seasonality and randomness."""
    base_min, base_max = BRANCH_BASE_RANGES[branch_id]
    baseline = random.randint(base_min, base_max)
    weekly = get_weekly_multiplier(date_val)
    seasonal = get_seasonal_multiplier(date_val)
    daily_noise = random.gauss(1.0, 0.25)
    return max(0, int(baseline * weekly * seasonal * daily_noise))


# ---------------------------------------------------------------------------
# Rolling state
# ---------------------------------------------------------------------------
receivings = []
receiving_items = []
flower_batches = []          # mutable: availableQuantity depletes via FIFO
distribution_orders = []
distribution_order_items = []
distribution_batch_allocations = []
distribution_receipts = []
distribution_receipt_items = []
daily_sales = []
daily_sales_items = []
inventory_movements = []

# HO batches grouped per flower for FIFO lookup: flowerId -> list of batch dict refs
# Always kept in chronological order (receivedDate, id) since batches are appended in order
ho_batches_by_flower = {fl: [] for fl in flower_ids}

# Track total available per flower for O(1) ho_available()
ho_available_by_flower = {fl: 0 for fl in flower_ids}

# Track the first active index per flower to skip depleted batches at the front
ho_first_active = {fl: 0 for fl in flower_ids}

# running per-branch-flower totals for inventory_movements before/after
branch_flower_total = {(b, fl): 0 for b in branch_ids for fl in flower_ids}

# branch_stock_lots kept as list of dicts, mutable "quantity" field
branch_stock_lots = []

# Index for fast lookup: (branchId, flowerId) -> list of lot refs (active only)
lots_index = {}


def log_movement(flower_id, location_type, branch_id, batch_id, mtype, qty,
                  qty_before, qty_after, reference_type, reference_id, created_at):
    inventory_movements.append((
        ids["movement"].next(), flower_id, location_type,
        branch_id if branch_id is not None else "",
        batch_id if batch_id is not None else "",
        mtype, qty, qty_before, qty_after,
        reference_type, reference_id, created_at.isoformat()
    ))


# ---------------------------------------------------------------------------
# Stage 1+2: Receiving/QC -> Batches (farm -> HO)
# ---------------------------------------------------------------------------
def run_receiving(day):
    """Farm ships one HO supply target per flower, split across farms."""
    receiving_by_farm = {}
    for farm in farms:
        receiving_id = ids["receiving"].next()
        receiving_by_farm[farm["id"]] = receiving_id
        receivings.append({
            "id": receiving_id,
            "farmId": farm["id"],
            "receivedDate": day.isoformat(),
            "status": "COMPLETED",
        })

    for fl in flower_ids:
        d_plus_2 = sum(calculate_daily_demand(b, fl, day + timedelta(days=2)) for b in branch_ids)
        d_plus_3 = sum(calculate_daily_demand(b, fl, day + timedelta(days=3)) for b in branch_ids)
        forecast_target = (d_plus_2 + d_plus_3) / 2

        buffer = random.uniform(1.05, 1.15)
        total_shipped = max(len(farms), int(forecast_target * buffer))
        remaining = total_shipped

        for index, farm in enumerate(farms):
            farms_left = len(farms) - index
            if farms_left == 1:
                shipped_qty = remaining
            else:
                base_share = remaining / farms_left
                share_noise = random.uniform(0.85, 1.15)
                shipped_qty = max(1, round(base_share * share_noise))
                shipped_qty = min(shipped_qty, remaining - (farms_left - 1))
            remaining -= shipped_qty

            unusable_rate = random.uniform(*UNUSABLE_RATE_RANGE)
            unusable_qty = round(shipped_qty * unusable_rate)
            accepted_qty = shipped_qty - unusable_qty
            receiving_id = receiving_by_farm[farm["id"]]

            receiving_items.append({
                "id": ids["receiving_item"].next(),
                "receivingId": receiving_id,
                "flowerId": fl,
                "shippedQuantity": shipped_qty,
                "actualReceivedQuantity": shipped_qty,
                "acceptedQuantity": accepted_qty,
                "unusableQuantity": unusable_qty,
                "unusableNotes": "Rejected at QC: damaged or below grade" if unusable_qty > 0 else "",
            })

            if accepted_qty > 0:
                batch_id = ids["batch"].next()
                batch = {
                    "id": batch_id,
                    "batchNumber": f"B{day.strftime('%Y%m%d')}-{farm['id']}-{fl}-{batch_id}",
                    "receivingId": receiving_id,
                    "flowerId": fl,
                    "receivedDate": day.isoformat(),
                    "initialQuantity": accepted_qty,
                    "availableQuantity": accepted_qty,
                    "status": "AVAILABLE",
                    "createdAt": day.isoformat(),
                }
                flower_batches.append(batch)
                ho_batches_by_flower[fl].append(batch)
                ho_available_by_flower[fl] += accepted_qty

                log_movement(fl, "HO", None, batch_id, "RECEIVING_IN", accepted_qty,
                             0, accepted_qty, "RECEIVING", receiving_id, day)


# ---------------------------------------------------------------------------
# Stage 3+4: Distribution (HO -> branch), FIFO batch allocation
# ---------------------------------------------------------------------------
def ho_available(flower_id):
    return ho_available_by_flower[flower_id]


# Track the first active index per flower to skip depleted batches at the front
ho_first_active = {fl: 0 for fl in flower_ids}


def allocate_fifo(flower_id, qty_needed):
    """Consume oldest AVAILABLE batches first. Returns list of (batch, qty_taken).
    Uses a moving pointer to skip depleted batches at the front of the list."""
    taken = []
    batches = ho_batches_by_flower[flower_id]
    first = ho_first_active[flower_id]
    remaining = qty_needed
    while first < len(batches) and remaining > 0:
        b = batches[first]
        if b["availableQuantity"] <= 0:
            first += 1
            continue
        take = min(b["availableQuantity"], remaining)
        b["availableQuantity"] -= take
        ho_available_by_flower[flower_id] -= take
        if b["availableQuantity"] <= 0:
            b["status"] = "DEPLETED"
            first += 1
        taken.append((b, take))
        remaining -= take
    ho_first_active[flower_id] = first
    return taken, qty_needed - remaining


def sellable_qty(branch_id, flower_id, as_of_day):
    """Calculate sellable quantity - iterate backwards from end (lots are chronological)."""
    key = (branch_id, flower_id)
    lots = lots_index.get(key, [])
    total = 0
    for i in range(len(lots) - 1, -1, -1):
        lot = lots[i]
        age = (as_of_day - lot["shippedAt"]).days
        if age > MAX_SELLABLE_AGE:
            break  # older lots are even further back, stop
        if lot["quantity"] > 0:
            total += lot["quantity"]
    return total


def prune_lots_index(branch_id, flower_id):
    """Remove depleted lots from index to keep lookups fast."""
    key = (branch_id, flower_id)
    if key in lots_index:
        lots_index[key] = [l for l in lots_index[key] if l["quantity"] > 0]


def run_distribution(day):
    """Allocate all accepted HO stock to branches same day, demand-proportional."""
    for fl in flower_ids:
        available = ho_available(fl)
        if available <= 0:
            continue

        branch_demands = []
        for branch in branches:
            branch_id = int(branch["id"])
            base_demand = calculate_daily_demand(branch_id, fl, day + timedelta(days=1))
            allocation_noise = random.uniform(0.90, 1.10)
            branch_demand = max(1, int(base_demand * allocation_noise))
            branch_demands.append((branch_id, branch_demand))

        total_demand = sum(demand for _, demand in branch_demands)
        remaining_available = available
        remaining_demand = total_demand

        for index, (branch_id, branch_demand) in enumerate(branch_demands):
            branches_left = len(branch_demands) - index
            if branches_left == 1:
                ship_qty = remaining_available
            else:
                proportional_qty = round(available * branch_demand / total_demand)
                ship_qty = min(proportional_qty, remaining_available)
                if remaining_available > 0 and remaining_demand > 0 and ship_qty == 0:
                    ship_qty = 1
                ship_qty = min(ship_qty, remaining_available - (branches_left - 1))
                ship_qty = max(0, ship_qty)
            remaining_available -= ship_qty
            remaining_demand -= branch_demand

            if ship_qty <= 0:
                continue

            # Create order
            order_id = ids["order"].next()
            distribution_orders.append({
                "id": order_id,
                "branchId": branch_id,
                "status": "IN_TRANSIT",
                "shippedAt": day.isoformat(),
            })

            # Allocate batches FIFO
            allocations, allocated_qty = allocate_fifo(fl, ship_qty)
            for batch, taken in allocations:
                alloc_id = ids["allocation"].next()
                distribution_batch_allocations.append({
                    "id": alloc_id,
                    "distributionOrderId": order_id,
                    "batchId": batch["id"],
                    "quantity": taken,
                })

            # Create order item (tracks which flowers were in this order)
            if allocated_qty > 0:
                distribution_order_items.append({
                    "id": ids["order_item"].next(),
                    "distributionOrderId": order_id,
                    "flowerId": fl,
                    "quantity": allocated_qty,
                })

            # Log DISTRIBUTION_OUT once per order
            if allocated_qty > 0:
                after = ho_available(fl)
                log_movement(fl, "HO", None, None, "DISTRIBUTION_OUT", allocated_qty,
                             after + allocated_qty, after, "DISTRIBUTION_ORDER", order_id, day)

            # Branch receives same day
            receipt_id = ids["receipt"].next()
            distribution_receipts.append({
                "id": receipt_id,
                "distributionOrderId": order_id,
                "receivedAt": day.isoformat(),
            })

            # Transit damage/missing
            damage_rate = random.uniform(*TRANSIT_DAMAGE_RATE_RANGE)
            missing_rate = random.uniform(*TRANSIT_MISSING_RATE_RANGE)
            damaged = round(allocated_qty * damage_rate)
            missing = round(allocated_qty * missing_rate)
            received = allocated_qty - damaged - missing

            distribution_receipt_items.append({
                "id": ids["receipt_item"].next(),
                "distributionReceiptId": receipt_id,
                "flowerId": fl,
                "receivedQuantity": received,
                "damagedQuantity": damaged,
                "missingQuantity": missing,
            })

            # Create branch stock lot (age starts from today = farm ship date)
            if received > 0:
                lot_id = ids["lot"].next()
                lot = {
                    "id": lot_id,
                    "branchId": branch_id,
                    "flowerId": fl,
                    "sourceOrderId": order_id,
                    "quantity": received,
                    "shippedAt": day,
                }
                branch_stock_lots.append(lot)
                # Add to index for fast lookup
                key = (branch_id, fl)
                if key not in lots_index:
                    lots_index[key] = []
                lots_index[key].append(lot)
                before = branch_flower_total[(branch_id, fl)]
                branch_flower_total[(branch_id, fl)] += received
                log_movement(fl, "BRANCH", branch_id, None, "DISTRIBUTION_IN",
                             received, before, before + received, "DISTRIBUTION_ORDER", order_id, day)

            # Mark order RECEIVED (we just created it, so it's the last one)
            distribution_orders[-1]["status"] = "RECEIVED"


# ---------------------------------------------------------------------------
# Stage 5: Daily sales - capped by real branch stock, FIFO oldest lot first
# ---------------------------------------------------------------------------
def run_daily_sales(day):
    if day < SALES_START:
        return  # branches don't report sales before the historical sales window starts

    for branch in branches:
        branch_id = int(branch["id"])
        sale_id = ids["sale"].next()
        daily_sales.append({
            "id": sale_id,
            "branchId": branch_id,
            "salesDate": day.isoformat(),
        })

        for fl in flower_ids:
            available = sellable_qty(branch_id, fl, day)
            demand = calculate_daily_demand(branch_id, fl, day)
            # demand fluctuates day to day around calculated demand
            wanted = max(0, int(random.gauss(demand, demand * 0.25)))
            sold = min(wanted, available)

            damage_rate = random.uniform(*SALE_DAMAGE_RATE_RANGE)
            damaged = min(available - sold, round(sold * damage_rate))
            damaged = max(0, damaged)

            if sold == 0 and damaged == 0:
                continue

            daily_sales_items.append({
                "id": ids["sale_item"].next(),
                "dailySaleId": sale_id,
                "flowerId": fl,
                "soldQuantity": sold,
                "damagedQuantity": damaged,
            })

            # consume oldest sellable lots first (FIFO), sold + damaged together
            to_consume = sold + damaged
            key = (branch_id, fl)
            all_lots = lots_index.get(key, [])
            # Filter: lots with qty > 0 and age <= MAX_SELLABLE_AGE
            # Since lots are chronological, sellable ones are near the end
            lots = []
            for i in range(len(all_lots) - 1, -1, -1):
                lot = all_lots[i]
                age = (day - lot["shippedAt"]).days
                if age > MAX_SELLABLE_AGE:
                    break
                if lot["quantity"] > 0:
                    lots.append(lot)
            lots.reverse()  # now oldest-first for FIFO consumption
            before_total = branch_flower_total[(branch_id, fl)]
            remaining = to_consume
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(lot["quantity"], remaining)
                lot["quantity"] -= take
                remaining -= take
            branch_flower_total[(branch_id, fl)] = before_total - (to_consume - remaining)

            # Prune depleted lots from index to keep future lookups fast
            if to_consume > 0:
                prune_lots_index(branch_id, fl)

            after_total = branch_flower_total[(branch_id, fl)]
            if sold > 0:
                log_movement(fl, "BRANCH", branch_id, None, "SALE_OUT", sold,
                             before_total, before_total - sold, "DAILY_SALE", sale_id, day)
            if damaged > 0:
                log_movement(fl, "BRANCH", branch_id, None, "DAMAGED_OUT", damaged,
                             before_total - sold, after_total, "DAILY_SALE", sale_id, day)


# ---------------------------------------------------------------------------
# Run simulation day by day
# ---------------------------------------------------------------------------
def main():
    day = START_DATE
    while day <= END_DATE:
        run_receiving(day)
        run_distribution(day)
        run_daily_sales(day)
        day += timedelta(days=1)

    write_all()
    print_summary()


def write_csv(filename, rows, fieldnames):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_all():
    write_csv("receivings.csv", receivings, ["id", "farmId", "receivedDate", "status"])
    write_csv("receiving_items.csv", receiving_items,
              ["id", "receivingId", "flowerId", "shippedQuantity", "actualReceivedQuantity",
               "acceptedQuantity", "unusableQuantity", "unusableNotes"])

    write_csv("flower_batches.csv", flower_batches,
              ["id", "batchNumber", "receivingId", "flowerId", "receivedDate",
               "initialQuantity", "availableQuantity", "status", "createdAt"])

    write_csv("distribution_orders.csv", distribution_orders,
              ["id", "branchId", "status", "shippedAt"])
    write_csv("distribution_order_items.csv", distribution_order_items,
              ["id", "distributionOrderId", "flowerId", "quantity"])
    write_csv("distribution_batch_allocations.csv", distribution_batch_allocations,
              ["id", "distributionOrderId", "batchId", "quantity"])
    write_csv("distribution_receipts.csv", distribution_receipts,
              ["id", "distributionOrderId", "receivedAt"])
    write_csv("distribution_receipt_items.csv", distribution_receipt_items,
              ["id", "distributionReceiptId", "flowerId", "receivedQuantity",
               "damagedQuantity", "missingQuantity"])

    # branch_stock_lots: only export lots with qty > 0 at END_DATE
    live_lots = [
        {**l, "shippedAt": l["shippedAt"].isoformat()}
        for l in branch_stock_lots if l["quantity"] > 0
    ]
    write_csv("branch_stock_lots.csv", live_lots,
              ["id", "branchId", "flowerId", "sourceOrderId", "quantity", "shippedAt"])

    write_csv("daily_sales.csv", daily_sales, ["id", "branchId", "salesDate"])
    write_csv("daily_sales_items.csv", daily_sales_items,
              ["id", "dailySaleId", "flowerId", "soldQuantity", "damagedQuantity"])

    write_csv("inventory_movements.csv",
              [{"id": m[0], "flowerId": m[1], "locationType": m[2], "branchId": m[3],
                "batchId": m[4], "type": m[5], "quantity": m[6], "qtyBefore": m[7],
                "qtyAfter": m[8], "referenceType": m[9], "referenceId": m[10],
                "createdAt": m[11]} for m in inventory_movements],
              ["id", "flowerId", "locationType", "branchId", "batchId", "type", "quantity",
               "qtyBefore", "qtyAfter", "referenceType", "referenceId", "createdAt"])


def print_summary():
    print("=== Generation summary ===")
    print(f"Date range        : {START_DATE} -> {END_DATE}  (sales start {SALES_START})")
    print(f"farms              : {len(farms)}")
    print(f"branches           : {len(branches)}")
    print(f"flowers            : {len(flowers)}")
    print(f"receivings         : {len(receivings)}")
    print(f"receiving_items    : {len(receiving_items)}")
    print(f"flower_batches     : {len(flower_batches)}")
    print(f"distribution_orders: {len(distribution_orders)}")
    print(f"distribution_order_items: {len(distribution_order_items)}")
    print(f"batch_allocations  : {len(distribution_batch_allocations)}")
    print(f"distribution_receipts     : {len(distribution_receipts)}")
    print(f"distribution_receipt_items: {len(distribution_receipt_items)}")
    print(f"branch_stock_lots (live)  : {len([l for l in branch_stock_lots if l['quantity'] > 0])}")
    print(f"daily_sales        : {len(daily_sales)}")
    print(f"daily_sales_items  : {len(daily_sales_items)}")
    print(f"inventory_movements: {len(inventory_movements)}")

    # sanity checks
    neg_batch = [b for b in flower_batches if b["availableQuantity"] < 0]
    neg_lot = [l for l in branch_stock_lots if l["quantity"] < 0]
    print(f"\nNegative availableQuantity batches: {len(neg_batch)}")
    print(f"Negative quantity lots: {len(neg_lot)}")


if __name__ == "__main__":
    main()
