"""Offline sync must be safe to repeat: a phone that never saw our response retries."""

API = "/api/v1"


def _meter(client, auth) -> str:
    partner = client.post(
        f"{API}/partners/", json={"name": "Test partner", "country": "EC", "new_organization_name": "Test org"}, headers=auth
    ).json()
    committee = client.post(
        f"{API}/water-committees/", json={"name": "Test WC", "partner_id": partner["id"]}, headers=auth
    ).json()
    community = client.post(
        f"{API}/communities/",
        json={"name": "Test community", "country": "EC", "water_committee_id": committee["id"]},
        headers=auth,
    ).json()
    household = client.post(
        f"{API}/households/",
        json={
            "account_number": "A-001",
            "head_of_household": "Field tester",
            "community_id": community["id"],
            "meter_serial_number": "SN-001",
            "meter_initial_reading": 100.0,
        },
        headers=auth,
    ).json()
    meters = client.get(
        f"{API}/meters/", params={"household_id": household["id"]}, headers=auth
    ).json()
    return meters[0]["id"]


def _push(client, auth, meter_id: str, client_id: str, value: float):
    return client.post(
        f"{API}/sync/push",
        json={
            "readings": [
                {
                    "client_id": client_id,
                    "meter_id": meter_id,
                    "reading_value": value,
                    "reading_date": "2026-01-15T09:00:00Z",
                }
            ]
        },
        headers=auth,
    )


def test_repeated_push_records_one_reading(client, auth):
    meter_id = _meter(client, auth)

    first = _push(client, auth, meter_id, "device-abc-123", 130.0)
    assert first.status_code == 200, first.text
    first_item = first.json()["readings"][0]
    assert first_item["success"] and not first_item["duplicate"]

    second = _push(client, auth, meter_id, "device-abc-123", 130.0)
    second_item = second.json()["readings"][0]
    assert second_item["success"] and second_item["duplicate"]
    assert second_item["server_id"] == first_item["server_id"]

    readings = client.get(
        f"{API}/meters/readings", params={"meter_id": meter_id}, headers=auth
    ).json()
    assert len([r for r in readings if r["reading_value"] == 130.0]) == 1

    meter = client.get(f"{API}/meters/", headers=auth).json()[0]
    assert meter["last_reading_value"] == 130.0
    assert meter["avg_consumption_m3"] == 30.0


def test_unknown_meter_is_reported_without_failing_the_batch(client, auth):
    response = _push(
        client, auth, "00000000-0000-0000-0000-000000000000", "device-missing", 10.0
    )
    item = response.json()["readings"][0]
    assert not item["success"]
    assert item["error"] == "Meter not found"
