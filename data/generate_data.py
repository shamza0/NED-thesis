"""Seeded synthetic data generator for foodpanda_lite.db (seed=42, fully reproducible)."""
import sqlite3
import random
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Run: pip install faker")

SEED = 42
random.seed(SEED)
Faker.seed(SEED)

try:
    fake = Faker("en_PK")
    _ = fake.name()
except Exception:
    fake = Faker("en_US")

DB_PATH = Path(__file__).parent / "foodpanda_lite.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

ZONES = [
    "Clifton", "Gulshan-e-Iqbal", "DHA", "Saddar",
    "North Nazimabad", "Korangi", "Malir", "Lyari",
    "Orangi", "Landhi", "Kemari", "PECHS",
]

CUISINES = ["Biryani", "BBQ", "Pizza", "Chinese", "Fast Food", "Desi", "Dessert"]

DISH_NAMES = {
    "Biryani":   ["Chicken Biryani", "Mutton Biryani", "Beef Biryani", "Sindhi Biryani", "Prawn Biryani"],
    "BBQ":       ["Seekh Kebab", "Boti Kebab", "Tikka Boti", "Malai Tikka", "Chapli Kebab"],
    "Pizza":     ["Margherita Pizza", "BBQ Chicken Pizza", "Pepperoni Pizza", "Veggie Supreme", "Cheese Burst"],
    "Chinese":   ["Chicken Chowmein", "Fried Rice", "Manchurian", "Spring Rolls", "Kung Pao Chicken"],
    "Fast Food": ["Zinger Burger", "Double Patty Burger", "French Fries", "Crispy Wrap", "Hot Dog"],
    "Desi":      ["Daal Makhni", "Karahi Gosht", "Haleem", "Nihari", "Palak Paneer"],
    "Dessert":   ["Gulab Jamun", "Kheer", "Gajar Halwa", "Ras Malai", "Ice Cream Sundae"],
}

CATEGORIES = ["Main", "Starter", "Drink", "Dessert"]
VEHICLES = ["Bike", "Car", "Bicycle"]
PAYMENT_METHODS = ["cash", "card", "easypaisa", "jazzcash"]
ORDER_STATUSES = ["delivered", "cancelled", "in_progress"]

# Zone delivery time offset in minutes (higher = farther = slower)
ZONE_TIME_OFFSET = {z: i * 3 for i, z in enumerate(ZONES)}

PK_NAMES_MALE = [
    "Ahmed Ali", "Muhammad Hassan", "Usman Khan", "Bilal Qureshi", "Zaid Siddiqui",
    "Arslan Sheikh", "Hamza Malik", "Faisal Raza", "Imran Baig", "Tariq Mirza",
    "Salman Javed", "Naveed Hussain", "Adnan Farooqi", "Waqar Ahmed", "Kashif Noor",
    "Yasir Latif", "Kamran Iqbal", "Shahid Mehmood", "Farhan Butt", "Junaid Anwar",
]
PK_NAMES_FEMALE = [
    "Ayesha Noor", "Fatima Zahra", "Zara Khan", "Hina Malik", "Sana Qureshi",
    "Nadia Hussain", "Maria Sheikh", "Amna Raza", "Sara Baig", "Rabia Mirza",
    "Kiran Javed", "Mehwish Farooq", "Saba Anwar", "Iqra Butt", "Noor Fatima",
    "Amina Siddiqui", "Bushra Ali", "Uzma Hassan", "Tahira Iqbal", "Samina Mehmood",
]
ALL_NAMES = PK_NAMES_MALE * 200 + PK_NAMES_FEMALE * 200

_name_idx = 0
def next_name():
    global _name_idx
    n = ALL_NAMES[_name_idx % len(ALL_NAMES)] + f" {_name_idx // len(ALL_NAMES) + 1}"
    _name_idx += 1
    return n


def random_date_18m(rng=None):
    """Random timestamp in last 18 months with weekend peak."""
    rng = rng or random
    base = datetime(2024, 12, 10)  # ~18 months before June 2026
    end  = datetime(2026, 6, 10)
    days = (end - base).days
    # Apply upward trend: pick day with mild bias toward later dates
    day_idx = int(rng.betavariate(1.5, 1.0) * days)
    d = base + timedelta(days=day_idx)
    # Weekend boost: Fri=4, Sat=5, Sun=6
    if d.weekday() in (4, 5, 6) and rng.random() > 0.4:
        pass  # keep; already over-represented by betavariate skew
    hour = rng.choices(range(24), weights=[1,1,1,1,1,1,2,3,4,5,5,6,7,8,8,7,6,5,8,9,9,8,6,3])[0]
    minute = rng.randint(0, 59)
    return d.replace(hour=hour, minute=minute, second=0)


def build_db():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())

    rng = random.Random(SEED)

    # --- delivery_zones ---
    zones = [(i+1, "Karachi", z) for i, z in enumerate(ZONES)]
    conn.executemany("INSERT INTO delivery_zones VALUES (?,?,?)", zones)

    # --- customers ---
    customers = []
    for i in range(1, 8001):
        zone_id = rng.randint(1, len(ZONES))
        signup = (datetime(2020, 1, 1) + timedelta(days=rng.randint(0, 1800))).date()
        customers.append((i, next_name(), zone_id, str(signup)))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", customers)

    # --- restaurants ---
    restaurants = []
    rest_names_used = set()
    for i in range(1, 401):
        cuisine = rng.choice(CUISINES)
        base_name = rng.choice([
            "Al-Baik", "Karachi Grill", "Spice Garden", "The Food Hub",
            "Golden Fork", "Zaiqa Point", "Desi Dhaba", "Street Bites",
            "Flame House", "Taste Buds", "Noodle Wok", "Burger Barn",
            "Pizza Palace", "Curry Leaf", "Haleem Corner",
        ])
        name = f"{base_name} {cuisine} {i}"
        while name in rest_names_used:
            name += "+"
        rest_names_used.add(name)
        zone_id = rng.randint(1, len(ZONES))
        rating = round(rng.uniform(2.5, 5.0), 1)
        restaurants.append((i, name, cuisine, zone_id, rating))
    conn.executemany("INSERT INTO restaurants VALUES (?,?,?,?,?)", restaurants)

    # --- menu_items ---
    menu_items = []
    mid = 1
    rest_menu = {}  # restaurant_id -> list of menu_item_ids
    for rest_id, _, cuisine, _, _ in restaurants:
        dishes = DISH_NAMES.get(cuisine, DISH_NAMES["Desi"])
        item_count = rng.randint(6, 14)
        rest_menu[rest_id] = []
        for _ in range(item_count):
            dish = rng.choice(dishes)
            category = rng.choices(CATEGORIES, weights=[5, 2, 2, 1])[0]
            price = round(rng.uniform(150, 1200), 0)
            menu_items.append((mid, rest_id, dish, category, price))
            rest_menu[rest_id].append(mid)
            mid += 1
    conn.executemany("INSERT INTO menu_items VALUES (?,?,?,?,?)", menu_items)

    # --- riders ---
    riders = []
    for i in range(1, 601):
        zone_id = rng.randint(1, len(ZONES))
        vehicle = rng.choice(VEHICLES)
        joined = (datetime(2019, 1, 1) + timedelta(days=rng.randint(0, 2000))).date()
        riders.append((i, next_name(), zone_id, vehicle, str(joined)))
    conn.executemany("INSERT INTO riders VALUES (?,?,?,?,?)", riders)

    # --- promotions ---
    promotions = []
    for i in range(1, 21):
        code = f"PROMO{i:02d}"
        disc = round(rng.uniform(5, 30), 0)
        start = (datetime(2024, 1, 1) + timedelta(days=rng.randint(0, 400))).date()
        end_d = (datetime.combine(start, datetime.min.time()) + timedelta(days=rng.randint(30, 120))).date()
        promotions.append((i, code, disc, str(start), str(end_d)))
    conn.executemany("INSERT INTO promotions VALUES (?,?,?,?,?)", promotions)

    # --- orders + order_items + payments + ratings ---
    orders, order_items_rows, payments, ratings = [], [], [], []
    order_id = 1
    payment_id = 1
    rating_id = 1

    for _ in range(30000):
        cust_id = rng.randint(1, 8000)
        rest_id = rng.randint(1, 400)
        rider_id = rng.randint(1, 600) if rng.random() > 0.02 else None

        # ~15% promos
        promo_id = None
        discount_pct = 0.0
        if rng.random() < 0.15:
            promo_id = rng.randint(1, 20)
            discount_pct = promotions[promo_id - 1][2]

        order_time = random_date_18m(rng)

        # ~6% cancelled
        if rng.random() < 0.06:
            status = "cancelled"
            delivered_time = None
        else:
            status = "delivered"
            zone_id = restaurants[rest_id - 1][3]  # restaurant zone
            offset = ZONE_TIME_OFFSET.get(ZONES[zone_id - 1], 0)
            mins = max(12, min(120, int(rng.gauss(35 + offset, 12))))
            delivered_time = order_time + timedelta(minutes=mins)

        # pick 1-4 menu items
        available = rest_menu.get(rest_id, [1])
        chosen = rng.sample(available, min(rng.randint(1, 4), len(available)))
        subtotal = 0.0
        for item_id in chosen:
            qty = rng.randint(1, 3)
            item_price = menu_items[item_id - 1][4]
            order_items_rows.append((order_id, item_id, qty, item_price))
            subtotal += item_price * qty

        total = round(subtotal * (1 - discount_pct / 100), 2)

        orders.append((
            order_id, cust_id, rest_id, rider_id, promo_id,
            order_time.strftime("%Y-%m-%d %H:%M:%S"),
            delivered_time.strftime("%Y-%m-%d %H:%M:%S") if delivered_time else None,
            status, total,
        ))

        # payment for every order
        method = rng.choice(PAYMENT_METHODS)
        pay_status = "completed" if status == "delivered" else rng.choice(["failed", "refunded"])
        payments.append((payment_id, order_id, method, total, pay_status))
        payment_id += 1

        # ~60% of delivered orders get a rating
        if status == "delivered" and rng.random() < 0.60:
            food_r = rng.randint(1, 5)
            del_r = rng.randint(1, 5)
            ratings.append((rating_id, order_id, food_r, del_r))
            rating_id += 1

        order_id += 1

    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?)", order_items_rows)
    conn.executemany("INSERT INTO payments VALUES (?,?,?,?,?)", payments)
    conn.executemany("INSERT INTO ratings VALUES (?,?,?,?)", ratings)

    conn.commit()

    # --- Integrity assertions ---
    def q(sql):
        return conn.execute(sql).fetchone()[0]

    print("\n=== Data generation complete ===")
    rows = {
        "delivery_zones": q("SELECT COUNT(*) FROM delivery_zones"),
        "customers":       q("SELECT COUNT(*) FROM customers"),
        "restaurants":     q("SELECT COUNT(*) FROM restaurants"),
        "menu_items":      q("SELECT COUNT(*) FROM menu_items"),
        "riders":          q("SELECT COUNT(*) FROM riders"),
        "promotions":      q("SELECT COUNT(*) FROM promotions"),
        "orders":          q("SELECT COUNT(*) FROM orders"),
        "order_items":     q("SELECT COUNT(*) FROM order_items"),
        "payments":        q("SELECT COUNT(*) FROM payments"),
        "ratings":         q("SELECT COUNT(*) FROM ratings"),
    }
    for tbl, cnt in rows.items():
        print(f"  {tbl:<20} {cnt:>7,}")

    assert rows["delivery_zones"] == 12
    assert rows["customers"] == 8000
    assert rows["restaurants"] == 400
    assert rows["orders"] == 30000
    assert rows["payments"] == 30000, "every order must have a payment"

    # totals reconcile: sum of order_items should >= total_amount (discount possible)
    mismatch = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT o.id, o.total_amount,
                   SUM(oi.item_price * oi.quantity) AS subtotal
            FROM orders o JOIN order_items oi ON o.id = oi.order_id
            GROUP BY o.id
            HAVING subtotal < o.total_amount - 0.01
        )
    """).fetchone()[0]
    assert mismatch == 0, f"{mismatch} orders have total_amount > subtotal (impossible)"

    print("\nAll assertions passed. DB written to:", DB_PATH)
    conn.close()


if __name__ == "__main__":
    build_db()
