"""
Tests for restocking order API endpoints.
"""
import pytest


def _order(items, budget=10000):
    return {"items": items, "budget": budget}


class TestRestockingOrderEndpoints:
    """Test suite for submitting and listing restocking orders."""

    def test_get_restocking_orders_empty(self, client):
        """Test that no orders exist before anything is submitted."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restocking_order(self, client):
        """Test submitting a valid order."""
        response = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "WDG-001", "quantity": 10}]),
        )
        assert response.status_code == 201

        order = response.json()
        assert order["order_number"] == "RST-0001"
        assert order["status"] == "Submitted"
        assert order["total_value"] == pytest.approx(249.9)
        assert order["lead_time_days"] == 7
        assert len(order["items"]) == 1
        assert order["items"][0]["name"] == "Industrial Widget Type A"

    def test_order_lead_time_is_longest_item_lead_time(self, client):
        """Test that the order lead time is the maximum across its items."""
        response = client.post(
            "/api/restocking-orders",
            # WDG-001 ships in 7 days, MTR-304 in 14
            json=_order([{"sku": "WDG-001", "quantity": 1}, {"sku": "MTR-304", "quantity": 1}]),
        )
        assert response.status_code == 201
        assert response.json()["lead_time_days"] == 14

    def test_expected_delivery_follows_lead_time(self, client):
        """Test that expected delivery is the submission date plus the lead time."""
        from datetime import datetime

        order = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "WDG-001", "quantity": 1}]),
        ).json()
        submitted = datetime.fromisoformat(order["submitted_at"])
        expected = datetime.fromisoformat(order["expected_delivery"])
        assert (expected - submitted).days == order["lead_time_days"]

    def test_prices_come_from_server_not_client(self, client):
        """Test that client-supplied prices are ignored."""
        response = client.post(
            "/api/restocking-orders",
            json={
                "items": [{"sku": "WDG-001", "quantity": 10, "unit_cost": 0.01}],
                "budget": 10000,
            },
        )
        assert response.status_code == 201
        assert response.json()["items"][0]["unit_cost"] == 24.99

    def test_total_above_budget_is_rejected(self, client):
        """Test that an order costing more than the budget is rejected."""
        response = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "WDG-001", "quantity": 100}], budget=100),
        )
        assert response.status_code == 422
        assert client.get("/api/restocking-orders").json() == []

    def test_total_equal_to_budget_is_accepted(self, client):
        """Test that spending exactly the budget is allowed."""
        response = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "MTR-304", "quantity": 1}], budget=445.0),
        )
        assert response.status_code == 201

    def test_unknown_sku_is_rejected(self, client):
        """Test that SKUs outside the demand forecast are rejected."""
        response = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "NOPE-000", "quantity": 1}]),
        )
        assert response.status_code == 422

    def test_duplicate_sku_is_rejected(self, client):
        """Test that the same SKU cannot appear twice in one order."""
        response = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "WDG-001", "quantity": 1}, {"sku": "WDG-001", "quantity": 2}]),
        )
        assert response.status_code == 422

    def test_empty_order_is_rejected(self, client):
        """Test that an order without items is rejected."""
        response = client.post("/api/restocking-orders", json=_order([]))
        assert response.status_code == 422

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_non_positive_quantity_is_rejected(self, client, quantity):
        """Test that quantities must be greater than zero."""
        response = client.post(
            "/api/restocking-orders",
            json=_order([{"sku": "WDG-001", "quantity": quantity}]),
        )
        assert response.status_code == 422

    def test_get_restocking_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        for sku in ("WDG-001", "GSK-203"):
            client.post("/api/restocking-orders", json=_order([{"sku": sku, "quantity": 1}]))

        orders = client.get("/api/restocking-orders").json()
        assert [o["order_number"] for o in orders] == ["RST-0002", "RST-0001"]


class TestDemandForecastCosting:
    """The demand forecast carries the cost and lead time that restocking relies on."""

    def test_forecasts_have_cost_and_lead_time(self, client):
        forecasts = client.get("/api/demand").json()
        assert len(forecasts) > 0
        for forecast in forecasts:
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0
