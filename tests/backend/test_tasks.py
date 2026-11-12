"""
Tests for task API endpoints.
"""
import pytest


def _create(client, **overrides):
    body = {"title": "Check stock", "priority": "high", "dueDate": "2025-10-08", **overrides}
    return client.post("/api/tasks", json=body)


class TestTasksEndpoints:
    """Test suite for task endpoints."""

    def test_get_tasks_empty(self, client):
        """No tasks exist until one is created."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """A created task is pending and returned with an id."""
        response = _create(client)
        assert response.status_code == 201

        task = response.json()
        assert task["title"] == "Check stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2025-10-08"
        assert task["status"] == "pending"
        assert isinstance(task["id"], int)

    def test_task_ids_do_not_collide_with_sample_tasks(self, client):
        """Ids start high enough to stay clear of the client's built-in sample tasks."""
        assert _create(client).json()["id"] >= 1000

    def test_task_ids_increase_and_are_not_reused(self, client):
        """Deleting a task does not cause its id to be handed out again."""
        first = _create(client).json()
        second = _create(client).json()
        assert second["id"] == first["id"] + 1

        client.delete(f"/api/tasks/{second['id']}")
        third = _create(client).json()
        assert third["id"] > second["id"]

    def test_get_tasks_newest_first(self, client):
        """Tasks are listed newest first."""
        first = _create(client, title="first").json()
        second = _create(client, title="second").json()
        ids = [t["id"] for t in client.get("/api/tasks").json()]
        assert ids == [second["id"], first["id"]]

    def test_title_is_trimmed(self, client):
        """Surrounding whitespace is removed from the title."""
        assert _create(client, title="  Review PO  ").json()["title"] == "Review PO"

    def test_blank_title_rejected(self, client):
        """A whitespace-only title is rejected and nothing is stored."""
        assert _create(client, title="   ").status_code == 400
        assert client.get("/api/tasks").json() == []

    @pytest.mark.parametrize("overrides", [
        {"title": ""},
        {"priority": "urgent"},
        {"dueDate": "10/08/2025"},
    ])
    def test_invalid_fields_rejected(self, client, overrides):
        """Empty title, unknown priority and malformed dates fail validation."""
        assert _create(client, **overrides).status_code == 422

    def test_impossible_date_rejected(self, client):
        """A well-formed but impossible date is rejected."""
        assert _create(client, dueDate="2025-02-31").status_code == 400

    def test_toggle_task(self, client):
        """Toggling flips pending to completed and back."""
        task_id = _create(client).json()["id"]

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        assert client.patch(f"/api/tasks/{task_id}").json()["status"] == "pending"

    def test_toggle_nonexistent_task(self, client):
        """Toggling an unknown task returns 404."""
        response = client.patch("/api/tasks/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_task(self, client):
        """A deleted task no longer appears in the list."""
        task_id = _create(client).json()["id"]
        assert client.delete(f"/api/tasks/{task_id}").status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_delete_nonexistent_task(self, client):
        """Deleting an unknown task returns 404."""
        assert client.delete("/api/tasks/99999").status_code == 404
