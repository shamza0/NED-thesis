"""System prompt and few-shot examples for the LLM call."""
import json
from .schema_context import get_schema_block

SYSTEM_TEMPLATE = """\
You are an expert SQLite analyst for a food delivery platform in Karachi, Pakistan.
Convert the user's question into ONE valid SQLite SELECT query.

DATABASE SCHEMA:
{schema_block}

RULES:
- SQLite dialect only. Use strftime() for date manipulation (e.g. strftime('%Y-%m', order_time)).
- Only SELECT statements. Never modify data.
- status values are lowercase: 'delivered', 'cancelled', 'in_progress'.
- Currency is PKR. Delivery duration in minutes = (julianday(delivered_time) - julianday(order_time)) * 24 * 60.
- Always alias aggregate columns with readable names (e.g. AS total_revenue).
- For time series, GROUP BY a strftime() bucket and ORDER BY it ascending.
- LIMIT results to 100 rows unless the question implies a top-N (then use that N).
- chart_hint guide: time series → line; category comparison → bar; share-of-whole with ≤6 categories → pie; two numeric measures → scatter; single number → stat; anything else → table.
"""

FEW_SHOT_PAIRS = [
    # 1. Time series + join → line
    (
        "Show monthly revenue for the last 6 months",
        {
            "reasoning": "I need to group orders by month using strftime and sum total_amount, filtering to last 6 months only.",
            "sql": "SELECT strftime('%Y-%m', order_time) AS month, SUM(total_amount) AS total_revenue FROM orders WHERE status = 'delivered' AND order_time >= date('now', '-6 months') GROUP BY month ORDER BY month ASC",
            "chart_hint": "line",
            "title": "Monthly Revenue (Last 6 Months)",
        },
    ),
    # 2. Top-N aggregation → bar
    (
        "Top 5 restaurants by number of orders",
        {
            "reasoning": "Join orders with restaurants, count orders per restaurant, order descending and take top 5.",
            "sql": "SELECT r.name AS restaurant_name, COUNT(o.id) AS order_count FROM orders o JOIN restaurants r ON o.restaurant_id = r.id GROUP BY r.id ORDER BY order_count DESC LIMIT 5",
            "chart_hint": "bar",
            "title": "Top 5 Restaurants by Order Count",
        },
    ),
    # 3. Share-of-whole → pie
    (
        "Split of payment methods",
        {
            "reasoning": "Count orders grouped by payment method to show proportional share.",
            "sql": "SELECT p.method AS payment_method, COUNT(*) AS count FROM payments p GROUP BY p.method ORDER BY count DESC",
            "chart_hint": "pie",
            "title": "Payment Method Distribution",
        },
    ),
    # 4. Computed metric + filter → bar
    (
        "Average delivery time by zone for delivered orders",
        {
            "reasoning": "Compute delivery duration in minutes using julianday difference, join with delivery_zones, filter to delivered only, group by zone.",
            "sql": "SELECT dz.zone_name AS zone, ROUND(AVG((julianday(o.delivered_time) - julianday(o.order_time)) * 24 * 60), 1) AS avg_delivery_minutes FROM orders o JOIN riders r ON o.rider_id = r.id JOIN delivery_zones dz ON r.zone_id = dz.id WHERE o.status = 'delivered' GROUP BY dz.id ORDER BY avg_delivery_minutes DESC",
            "chart_hint": "bar",
            "title": "Average Delivery Time by Zone (minutes)",
        },
    ),
]


def build_system_prompt() -> str:
    return SYSTEM_TEMPLATE.format(schema_block=get_schema_block())


def build_few_shot_messages() -> list[dict]:
    msgs = []
    for user_q, plan_dict in FEW_SHOT_PAIRS:
        msgs.append({"role": "user", "content": user_q})
        msgs.append({"role": "assistant", "content": json.dumps(plan_dict)})
    return msgs
