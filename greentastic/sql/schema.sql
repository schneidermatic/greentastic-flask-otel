-- All tables of the shop. "IF NOT EXISTS" makes this safe to run on every start.

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email         TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('customer', 'seller', 'admin'))
);

CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    category    TEXT NOT NULL,             -- fruits, vegetables, handmade, handcraft (= image folder)
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       NUMERIC(10, 2) NOT NULL,   -- euro per unit
    stock       INTEGER NOT NULL,
    unit        TEXT NOT NULL,             -- kg or pcs
    image       TEXT NOT NULL              -- file name in static/<category>/
);

CREATE TABLE IF NOT EXISTS cart_items (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL
);

-- one order per checkout ...
CREATE TABLE IF NOT EXISTS orders (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    username   TEXT NOT NULL,
    name       TEXT NOT NULL,              -- delivery address
    street     TEXT NOT NULL,
    city       TEXT NOT NULL,
    payment    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'new' -- only 'new' orders can be changed by the customer
);

-- ... with one row per product; name and price are copied so the order survives product changes
CREATE TABLE IF NOT EXISTS order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    price        NUMERIC(10, 2) NOT NULL,
    quantity     INTEGER NOT NULL
);
