"""
Tests for restocking API endpoints.
"""
from datetime import datetime

import pytest


def _forecast(client, sku):
    """Look up a demand forecast row by SKU."""
    return next(f for f in client.get("/api/demand").json() if f["item_sku"] == sku)


class TestRestockingEndpoints:
    """Test suite for restocking order endpoints."""

    def test_demand_forecast_has_pricing_fields(self, client):
        """Forecast rows carry the category, stock and cost used for restocking."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        for row in response.json():
            assert isinstance(row["category"], str)
            assert isinstance(row["quantity_on_hand"], int)
            assert isinstance(row["unit_cost"], (int, float))
            assert row["unit_cost"] > 0

    def test_get_restocking_orders_empty(self, client):
        """No orders exist until one is submitted."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restock_order(self, client):
        """Submitting an order returns 201 with server-computed totals."""
        wdg = _forecast(client, "WDG-001")
        response = client.post("/api/restocking/orders", json={
            "budget": 100000,
            "lines": [{"sku": "WDG-001", "quantity": 100}],
        })
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith(f"RST-{datetime.now().year}-")
        assert order["budget"] == 100000
        assert len(order["lines"]) == 1
        assert order["lines"][0]["sku"] == "WDG-001"
        assert order["lines"][0]["unit_cost"] == wdg["unit_cost"]
        assert abs(order["total_cost"] - 100 * wdg["unit_cost"]) < 0.01

    def test_restock_order_lead_time_is_longest_line(self, client):
        """Order lead time is the longest category lead time among its lines."""
        response = client.post("/api/restocking/orders", json={
            "budget": 500000,
            "lines": [
                {"sku": "SNR-420", "quantity": 10},   # Sensors, 8 days
                {"sku": "WDG-001", "quantity": 10},   # Actuators, 14 days
            ],
        })
        assert response.status_code == 201

        order = response.json()
        assert order["lead_time_days"] == 14
        created = datetime.fromisoformat(order["created_date"])
        expected = datetime.fromisoformat(order["expected_delivery_date"])
        assert (expected - created).days == 14

    def test_created_order_appears_in_list_newest_first(self, client):
        """Submitted orders are listed newest first."""
        first = client.post("/api/restocking/orders", json={
            "budget": 100000, "lines": [{"sku": "SNR-420", "quantity": 1}],
        }).json()
        second = client.post("/api/restocking/orders", json={
            "budget": 100000, "lines": [{"sku": "CTL-330", "quantity": 1}],
        }).json()

        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        ids = [o["id"] for o in response.json()]
        assert ids == [second["id"], first["id"]]

    def test_create_restock_order_over_budget(self, client):
        """An order whose server-side total exceeds the budget is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 100,
            "lines": [{"sku": "WDG-001", "quantity": 100}],
        })
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()
        assert client.get("/api/restocking/orders").json() == []

    def test_create_restock_order_empty_lines(self, client):
        """An order with no lines is rejected."""
        response = client.post("/api/restocking/orders", json={"budget": 1000, "lines": []})
        assert response.status_code == 400

    def test_create_restock_order_unknown_sku(self, client):
        """An unknown SKU is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000,
            "lines": [{"sku": "NOPE-999", "quantity": 1}],
        })
        assert response.status_code == 400
        assert "unknown sku" in response.json()["detail"].lower()

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_create_restock_order_non_positive_quantity(self, client, quantity):
        """Zero or negative quantities are rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000,
            "lines": [{"sku": "WDG-001", "quantity": quantity}],
        })
        assert response.status_code == 400

    def test_create_restock_order_invalid_body(self, client):
        """A malformed body fails Pydantic validation."""
        response = client.post("/api/restocking/orders", json={"lines": []})
        assert response.status_code == 422

    @pytest.mark.parametrize("budget", ["NaN", "Infinity", "-Infinity", "-1"])
    def test_create_restock_order_rejects_invalid_budget(self, client, budget):
        """NaN, infinite and negative budgets are rejected and nothing is stored."""
        body = f'{{"budget": {budget}, "lines": [{{"sku": "WDG-001", "quantity": 1}}]}}'
        response = client.post(
            "/api/restocking/orders", content=body, headers={"content-type": "application/json"}
        )
        assert response.status_code == 422
        assert client.get("/api/restocking/orders").json() == []

    def test_create_restock_order_zero_budget(self, client):
        """A zero budget cannot fund any line."""
        response = client.post("/api/restocking/orders", json={
            "budget": 0, "lines": [{"sku": "WDG-001", "quantity": 1}],
        })
        assert response.status_code == 400

    def test_create_restock_order_huge_quantity(self, client):
        """An absurd quantity is rejected with a 4xx, not a server error."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000, "lines": [{"sku": "WDG-001", "quantity": 10**400}],
        })
        assert 400 <= response.status_code < 500
        assert client.get("/api/restocking/orders").status_code == 200

    def test_create_restock_order_quantity_above_shortfall(self, client):
        """Quantity beyond forecasted demand minus stock is rejected."""
        wdg = _forecast(client, "WDG-001")
        shortfall = wdg["forecasted_demand"] - wdg["quantity_on_hand"]
        response = client.post("/api/restocking/orders", json={
            "budget": 1_000_000_000,
            "lines": [{"sku": "WDG-001", "quantity": shortfall + 1}],
        })
        assert response.status_code == 400
        assert "shortfall" in response.json()["detail"].lower()

    def test_create_restock_order_sku_without_shortfall(self, client):
        """A SKU whose stock already covers forecast demand cannot be restocked."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1_000_000, "lines": [{"sku": "PSU-501", "quantity": 1}],
        })
        assert response.status_code == 400

    def test_create_restock_order_merges_duplicate_skus(self, client):
        """Repeated SKUs become a single line with summed quantity."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1_000_000,
            "lines": [
                {"sku": "WDG-001", "quantity": 5},
                {"sku": "SNR-420", "quantity": 2},
                {"sku": "WDG-001", "quantity": 7},
            ],
        })
        assert response.status_code == 201

        lines = response.json()["lines"]
        assert [l["sku"] for l in lines] == ["WDG-001", "SNR-420"]
        assert lines[0]["quantity"] == 12

    def test_duplicate_skus_merged_total_respects_shortfall(self, client):
        """The shortfall cap applies to the merged quantity, not each line."""
        wdg = _forecast(client, "WDG-001")
        shortfall = wdg["forecasted_demand"] - wdg["quantity_on_hand"]
        response = client.post("/api/restocking/orders", json={
            "budget": 1_000_000_000,
            "lines": [
                {"sku": "WDG-001", "quantity": shortfall},
                {"sku": "WDG-001", "quantity": 1},
            ],
        })
        assert response.status_code == 400

    def test_create_restock_order_budget_equal_to_total(self, client):
        """A budget exactly equal to the order total is accepted."""
        sku = _forecast(client, "SNR-420")
        total = round(10 * sku["unit_cost"], 2)
        response = client.post("/api/restocking/orders", json={
            "budget": total, "lines": [{"sku": "SNR-420", "quantity": 10}],
        })
        assert response.status_code == 201
        assert response.json()["total_cost"] == total

    def test_restock_order_numbers_are_sequential(self, client):
        """Ids and order numbers increase by one per submission."""
        numbers = []
        for _ in range(3):
            order = client.post("/api/restocking/orders", json={
                "budget": 100000, "lines": [{"sku": "SNR-420", "quantity": 1}],
            }).json()
            numbers.append((order["id"], order["order_number"]))

        year = datetime.now().year
        assert numbers == [(str(i), f"RST-{year}-{i:04d}") for i in (1, 2, 3)]

    def test_unknown_category_uses_default_lead_time(self, client, monkeypatch):
        """A category missing from the lead time table falls back to the default."""
        import main
        monkeypatch.setitem(main.demand_forecasts[0], "category", "Unlisted Category")
        response = client.post("/api/restocking/orders", json={
            "budget": 100000, "lines": [{"sku": main.demand_forecasts[0]["item_sku"], "quantity": 1}],
        })
        assert response.status_code == 201
        assert response.json()["lead_time_days"] == main.DEFAULT_LEAD_TIME_DAYS

    def test_create_restock_order_non_integer_quantity(self, client):
        """A non-numeric quantity fails Pydantic validation."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000, "lines": [{"sku": "WDG-001", "quantity": "lots"}],
        })
        assert response.status_code == 422
