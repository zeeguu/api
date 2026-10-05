import json

from fixtures import logged_in_client as client


def test_totals_are_public_json(client):
    response = client.client.get("/stats/totals")
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"

    totals = json.loads(response.data)
    for key in ("lookups", "exercises", "learners", "articles", "languages", "teachers", "classes"):
        assert isinstance(totals[key], int)
    assert "computed_at" in totals
