"""Load test for the Greentastic REST API with Locust (https://locust.io).

Three kinds of simulated users call the endpoints in greentastic/api.py:
  Visitor   (weight 3)  anonymous: browses categories, opens products, searches (with typos), uses the type-ahead
  Customer  (weight 2)  registers its own account, fills the cart, checks out, changes and deletes orders
  Seller    (weight 1)  watches all orders, adds products and deletes them again
  Trouble   (weight 1)  calls the simulated errors in greentastic/simulate.py (slow SQL, exceptions, timeouts, ...)

Run it with the shortcuts in .xrc:  x_locust (web UI on http://localhost:8089)  or  x_locust_run 20 5 2m
or directly:  locust -f loadtest/locustfile.py --host http://localhost:8000
"""
import os
import random
import uuid

from locust import HttpUser, between, task

PAYMENTS = ["cash on delivery", "credit card (fake)"]
# real product names, typos (fuzzy search) and terms without a result
SEARCH_TERMS = ["apple", "banana", "mango", "chocolates", "cookies", "garlic", "clay pot", "candle",
                "appel", "bananna", "cokies", "tomato", "xyz"]


class Visitor(HttpUser):
    """Anonymous visitor: only reads - mostly served by Redis (categories) and Elasticsearch (search)."""
    weight = 3
    wait_time = between(1, 3)

    def on_start(self):
        self.categories = [c["key"] for c in self.client.get("/api/categories").json()]
        self.product_ids = [p["id"] for p in self.client.get("/api/products").json()]

    @task(4)
    def browse_category(self):
        self.client.get(f"/api/products?category={random.choice(self.categories)}", name="/api/products?category=[c]")

    @task(2)
    def product_detail(self):
        self.client.get(f"/api/products/{random.choice(self.product_ids)}", name="/api/products/[id]")

    @task(3)
    def search(self):
        self.client.get(f"/api/search?q={random.choice(SEARCH_TERMS)}", name="/api/search?q=[term]")

    @task(2)
    def type_ahead(self):
        """Like typing in the search box: one suggest request per additional letter."""
        term = random.choice(SEARCH_TERMS)
        for length in range(1, min(len(term), 5) + 1):
            self.client.get(f"/api/suggest?q={term[:length]}", name="/api/suggest?q=[prefix]")

    @task(1)
    def unknown_product(self):
        with self.client.get("/api/products/999999", name="/api/products/[unknown]", catch_response=True) as r:
            if r.status_code == 404:
                r.success()  # expected - shows up as a 404 in the traces, not as a Locust failure

    @task(1)
    def wrong_password(self):
        with self.client.post("/api/login", json={"username": "user", "password": "wrong"},
                              name="/api/login [wrong password]", catch_response=True) as r:
            if r.status_code == 401:
                r.success()


class Customer(HttpUser):
    """Customer with an own account (so carts of different Locust users do not interfere)."""
    weight = 2
    wait_time = between(2, 5)

    def on_start(self):
        self.username = f"locust-{uuid.uuid4().hex[:8]}"
        self.client.post("/api/register", json={"username": self.username, "password": "locust",
                                                "email": f"{self.username}@example.invalid"})
        self.client.post("/api/login", json={"username": self.username, "password": "locust"})
        self.product_ids = [p["id"] for p in self.client.get("/api/products").json()]

    @task(3)
    def browse_and_add_to_cart(self):
        product_id = random.choice(self.product_ids)
        self.client.get(f"/api/products/{product_id}", name="/api/products/[id]")
        self.client.post("/api/cart", json={"product_id": product_id, "quantity": random.randint(1, 3)})

    @task(2)
    def checkout(self):
        if not self.client.get("/api/cart").json():
            return
        self.client.post("/api/checkout", json={"name": "Locust User", "street": "Load Street 1",
                                                "city": "Testtown", "payment": random.choice(PAYMENTS)})

    @task(2)
    def my_orders(self):
        orders = self.client.get("/api/orders").json()
        if orders:
            self.client.get(f"/api/orders/{random.choice(orders)['id']}", name="/api/orders/[id]")

    @task(1)
    def change_order(self):
        """Change the payment and one quantity of the newest order."""
        orders = self.client.get("/api/orders").json()
        if not orders:
            return
        order_id = orders[0]["id"]
        detail = self.client.get(f"/api/orders/{order_id}", name="/api/orders/[id]").json()
        if detail["items"]:
            item = random.choice(detail["items"])
            self.client.put(f"/api/orders/{order_id}", name="/api/orders/[id]", json={
                "name": "Locust User", "street": "Load Street 2", "city": "Testtown",
                "payment": random.choice(PAYMENTS), "quantities": {str(item["id"]): random.randint(1, 5)},
            })

    @task(1)
    def cancel_order(self):
        orders = self.client.get("/api/orders").json()
        if len(orders) > 2:  # keep a few orders, delete the oldest one
            self.client.delete(f"/api/orders/{orders[-1]['id']}", name="/api/orders/[id]")

    @task(1)
    def profile(self):
        self.client.get("/api/profile")
        self.client.put("/api/profile", json={"email": f"{self.username}+{random.randint(1, 99)}@example.invalid"})


class Seller(HttpUser):
    """Seller: adds products and deletes them again - each change updates PostgreSQL, Redis and Elasticsearch."""
    weight = 1
    wait_time = between(5, 10)

    def on_start(self):
        self.client.post("/api/login", json={"username": os.environ.get("SELLER_USER", "seller"),
                                             "password": os.environ.get("SELLER_PASSWORD", "seller")})
        self.images = {p["category"]: p["image"] for p in self.client.get("/api/products").json()}
        self.my_products = []

    def on_stop(self):
        for product_id in self.my_products:
            self.client.delete(f"/api/products/{product_id}", name="/api/products/[id]")

    @task(3)
    def watch_orders(self):
        self.client.get("/api/manage/orders")

    @task(1)
    def add_product(self):
        category = random.choice(list(self.images))
        response = self.client.post("/api/products", json={
            "category": category, "name": f"Load test product {uuid.uuid4().hex[:6]}",
            "description": "created by Locust", "price": round(random.uniform(1, 30), 2),
            "stock": random.randint(1, 50), "unit": "pcs", "image": self.images[category],
        })
        if response.status_code == 201:
            self.my_products.append(response.json()["id"])

    @task(1)
    def delete_product(self):
        if len(self.my_products) > 1:
            self.client.delete(f"/api/products/{self.my_products.pop(0)}", name="/api/products/[id]")


class Trouble(HttpUser):
    """Calls the endpoints that fail on purpose. The expected error codes count as success in Locust -
    the point is to see the errors in the telemetry, not in the load test statistics."""
    weight = 1
    wait_time = between(3, 8)

    def expect(self, path, status):
        with self.client.get(f"/api/simulate/{path}", name=f"/api/simulate/{path.split('?')[0]}",
                             catch_response=True) as response:
            if response.status_code == status:
                response.success()

    @task(3)
    def slow_query(self):
        self.expect("slow", 200)

    @task(2)
    def handled_error(self):
        self.expect("error", 500)

    @task(1)
    def crash(self):
        self.expect("crash", 500)

    @task(1)
    def database_error(self):
        self.expect("db-error", 500)

    @task(1)
    def search_error(self):
        self.expect("search-error", 502)

    @task(1)
    def payment_timeout(self):
        self.expect("timeout", 504)
