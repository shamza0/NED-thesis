CREATE TABLE delivery_zones (
    id INTEGER PRIMARY KEY,
    city TEXT NOT NULL,
    zone_name TEXT NOT NULL
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id),
    signup_date DATE NOT NULL
);

CREATE TABLE restaurants (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine_type TEXT NOT NULL,
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id),
    rating REAL
);

CREATE TABLE menu_items (
    id INTEGER PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);

CREATE TABLE riders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id),
    vehicle_type TEXT NOT NULL,
    joined_date DATE NOT NULL
);

CREATE TABLE promotions (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    discount_pct REAL NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    rider_id INTEGER REFERENCES riders(id),
    promo_id INTEGER REFERENCES promotions(id),
    order_time TIMESTAMP NOT NULL,
    delivered_time TIMESTAMP,
    status TEXT NOT NULL,
    total_amount REAL NOT NULL
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity INTEGER NOT NULL,
    item_price REAL NOT NULL,
    PRIMARY KEY (order_id, menu_item_id)
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    method TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE ratings (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    food_rating INTEGER NOT NULL,
    delivery_rating INTEGER NOT NULL
);

-- Indices for query performance
CREATE INDEX idx_orders_order_time ON orders(order_time);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_restaurant_id ON orders(restaurant_id);
CREATE INDEX idx_orders_rider_id ON orders(rider_id);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_menu_item_id ON order_items(menu_item_id);
CREATE INDEX idx_menu_items_restaurant_id ON menu_items(restaurant_id);
CREATE INDEX idx_customers_zone_id ON customers(zone_id);
CREATE INDEX idx_restaurants_zone_id ON restaurants(zone_id);
CREATE INDEX idx_riders_zone_id ON riders(zone_id);
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_ratings_order_id ON ratings(order_id);
