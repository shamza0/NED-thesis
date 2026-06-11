"""SQL guard: validates and sanitises LLM-generated SQL before execution."""
import re
import sqlglot
import sqlglot.expressions as exp

DENYLIST = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "PRAGMA", "REPLACE", "TRUNCATE", "VACUUM",
}

# All table + column names known to exist in the schema
KNOWN_TABLES = {
    "delivery_zones", "customers", "restaurants", "menu_items",
    "riders", "promotions", "orders", "order_items", "payments", "ratings",
}

KNOWN_COLUMNS = {
    # delivery_zones
    "city", "zone_name",
    # customers
    "signup_date",
    # restaurants
    "cuisine_type", "rating",
    # menu_items
    "restaurant_id", "category", "price",
    # riders
    "vehicle_type", "joined_date",
    # promotions
    "code", "discount_pct", "valid_from", "valid_to",
    # orders
    "customer_id", "rider_id", "promo_id", "order_time",
    "delivered_time", "status", "total_amount",
    # order_items
    "order_id", "menu_item_id", "quantity", "item_price",
    # payments
    "method", "amount",
    # ratings
    "food_rating", "delivery_rating",
    # shared
    "id", "name", "zone_id",
}


class GuardError(Exception):
    pass


class HallucinationError(GuardError):
    pass


def guard(sql: str) -> str:
    """Validate and potentially mutate SQL. Returns cleaned SQL or raises GuardError."""
    sql = sql.strip().rstrip(";")

    # 1. Denylist token check (fast, case-insensitive)
    upper = sql.upper()
    for token in DENYLIST:
        # word-boundary match to avoid false positives like "CREATED_AT"
        if re.search(rf"\b{token}\b", upper):
            raise GuardError(f"Forbidden token in SQL: {token}")

    # 2. Parse
    try:
        statements = sqlglot.parse(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as e:
        raise GuardError(f"SQL parse error: {e}") from e

    if not statements or statements[0] is None:
        raise GuardError("Empty or unparseable SQL")

    if len(statements) > 1:
        raise GuardError("Multiple statements are not allowed")

    stmt = statements[0]

    # 3. Must be SELECT (CTEs that end in SELECT are fine)
    if not isinstance(stmt, (exp.Select, exp.With)):
        raise GuardError(f"Only SELECT statements are allowed, got: {type(stmt).__name__}")

    if isinstance(stmt, exp.With):
        # The final expression in a CTE chain must be a SELECT
        final = stmt.this
        if not isinstance(final, exp.Select):
            raise GuardError("CTE must end with a SELECT statement")

    # 4. Hallucination check: table names (skip CTE aliases — they are local names)
    cte_names = {cte.alias.lower() for cte in stmt.find_all(exp.CTE)}
    # Build alias→real-table map for column check below
    alias_to_table: dict[str, str] = {}
    for table in stmt.find_all(exp.Table):
        tname = table.name.lower()
        if tname and tname not in KNOWN_TABLES and tname not in cte_names:
            raise HallucinationError(f"Unknown table referenced: '{tname}'")
        talias = (table.alias or table.name).lower()
        alias_to_table[talias] = tname

    # 5. Hallucination check: columns that explicitly reference a known base table
    for col in stmt.find_all(exp.Column):
        raw_ref = col.table.lower() if col.table else None
        if raw_ref:
            real_table = alias_to_table.get(raw_ref, raw_ref)
            if real_table in KNOWN_TABLES:
                cname = col.name.lower()
                if cname and cname not in KNOWN_COLUMNS:
                    raise HallucinationError(f"Unknown column '{cname}' on table '{real_table}'")

    # 6. Inject LIMIT 100 if absent and not an aggregate-only result
    sql_out = sql
    has_limit = stmt.find(exp.Limit) is not None
    if not has_limit:
        # Check if it's a single-row aggregate (e.g. SELECT COUNT(*) FROM orders)
        is_pure_agg = _is_pure_aggregate(stmt if isinstance(stmt, exp.Select) else stmt.this)
        if not is_pure_agg:
            sql_out = sql + " LIMIT 100"

    return sql_out


def _is_pure_aggregate(select: exp.Select) -> bool:
    """True if every projection is an aggregate function with no GROUP BY."""
    if select.find(exp.Group):
        return False
    projections = select.expressions
    if not projections:
        return False
    return all(
        isinstance(p, exp.Alias) and isinstance(p.this, exp.Anonymous)
        or isinstance(p, (exp.Count, exp.Sum, exp.Avg, exp.Max, exp.Min))
        or (isinstance(p, exp.Alias) and isinstance(p.this, (exp.Count, exp.Sum, exp.Avg, exp.Max, exp.Min)))
        for p in projections
    )
