"""
Tests for reports API endpoints.
"""


class TestReportsEndpoints:
    """Test suite for report endpoints."""

    def test_quarterly_unfiltered_matches_orders(self, client):
        """Unfiltered quarterly totals add up to every dated 2025 order."""
        orders = client.get("/api/orders").json()
        quarterly = client.get("/api/reports/quarterly").json()

        assert [q["quarter"] for q in quarterly] == sorted(q["quarter"] for q in quarterly)
        assert sum(q["total_orders"] for q in quarterly) == len(orders)
        assert abs(sum(q["total_revenue"] for q in quarterly) - sum(o["total_value"] for o in orders)) < 0.01

    def test_quarterly_filter_by_warehouse(self, client):
        """The warehouse filter narrows quarterly totals like it does for /api/orders."""
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        quarterly = client.get("/api/reports/quarterly?warehouse=Tokyo").json()
        assert sum(q["total_orders"] for q in quarterly) == len(orders)

    def test_monthly_filter_by_category_and_status(self, client):
        """Category and status filters apply together."""
        url = "category=Sensors&status=Delivered"
        orders = client.get(f"/api/orders?{url}").json()
        monthly = client.get(f"/api/reports/monthly-trends?{url}").json()
        assert sum(m["order_count"] for m in monthly) == len(orders)
        assert sum(m["delivered_count"] for m in monthly) == len(orders)

    def test_monthly_filter_by_month(self, client):
        """A single-month filter returns only that month."""
        monthly = client.get("/api/reports/monthly-trends?month=2025-03").json()
        assert [m["month"] for m in monthly] in ([], ["2025-03"])

    def test_quarter_filter_limits_months(self, client):
        """A quarter filter returns only months inside that quarter."""
        monthly = client.get("/api/reports/monthly-trends?month=Q2-2025").json()
        assert all(m["month"] in ("2025-04", "2025-05", "2025-06") for m in monthly)
        quarterly = client.get("/api/reports/quarterly?month=Q2-2025").json()
        assert all(q["quarter"] == "Q2-2025" for q in quarterly)

    def test_filters_matching_nothing_return_empty_lists(self, client):
        """A filter combination with no orders yields empty lists, not an error."""
        for path in ("quarterly", "monthly-trends"):
            response = client.get(f"/api/reports/{path}?warehouse=Nowhere")
            assert response.status_code == 200
            assert response.json() == []

    def test_quarterly_rates_are_consistent(self, client):
        """Fulfillment rate and average order value follow from the counts."""
        for q in client.get("/api/reports/quarterly").json():
            assert abs(q["fulfillment_rate"] - round(q["delivered_orders"] / q["total_orders"] * 100, 1)) < 0.01
            assert abs(q["avg_order_value"] - round(q["total_revenue"] / q["total_orders"], 2)) < 0.01
