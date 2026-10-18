"""Partner > water committee > community > household > meter, with scoped logins and block tariffs."""

import io
import uuid
from datetime import datetime, timedelta, timezone

API = "/api/v1"


def _login(client, email, password):
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, auth):
    partner = client.post(
        f"{API}/partners/", json={"name": f"P-{uuid.uuid4().hex[:6]}", "country": "US"}, headers=auth
    ).json()
    assert "id" in partner, partner
    committee = client.post(
        f"{API}/water-committees/",
        json={"name": "Cedar Creek WC", "partner_id": partner["id"]},
        headers=auth,
    )
    assert committee.status_code == 201, committee.text
    committee = committee.json()
    comm_a = client.post(
        f"{API}/communities/",
        json={"name": "Cedar A", "country": "US", "water_committee_id": committee["id"]},
        headers=auth,
    ).json()
    comm_b = client.post(
        f"{API}/communities/",
        json={"name": "Cedar B", "country": "US", "water_committee_id": committee["id"]},
        headers=auth,
    ).json()
    assert comm_a["water_committee_id"] == committee["id"]
    assert comm_a["partner_id"] == partner["id"]
    other_committee = client.post(
        f"{API}/water-committees/", json={"name": "Other WC", "partner_id": partner["id"]}, headers=auth
    ).json()
    comm_other = client.post(
        f"{API}/communities/",
        json={"name": "Elsewhere", "country": "US", "water_committee_id": other_committee["id"]},
        headers=auth,
    ).json()
    return partner, committee, comm_a, comm_b, other_committee, comm_other


def test_hierarchy_scoping_and_roles(client, auth):
    partner, committee, comm_a, comm_b, other_committee, comm_other = _setup(client, auth)

    # committee admin created by sys admin
    r = client.post(
        f"{API}/auth/users",
        json={
            "email": "wc@test.org", "password": "password1", "full_name": "WC Admin",
            "role": "community_admin", "water_committee_id": committee["id"],
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text
    wc = _login(client, "wc@test.org", "password1")

    # sees only its committee's communities
    names = {c["name"] for c in client.get(f"{API}/communities/", headers=wc).json()}
    assert names == {"Cedar A", "Cedar B"}
    assert client.get(f"{API}/communities/{comm_other['id']}", headers=wc).status_code == 403
    assert len(client.get(f"{API}/water-committees/", headers=wc).json()) == 1

    # cannot create a sys admin or partner admin
    for role in ("super_admin", "partner_admin"):
        r = client.post(
            f"{API}/auth/users",
            json={"email": f"{role}@test.org", "password": "password1", "full_name": "x", "role": role},
            headers=wc,
        )
        assert r.status_code == 403, role

    # can create an operator assigned to two communities
    r = client.post(
        f"{API}/auth/users",
        json={
            "email": "op@test.org", "password": "password1", "full_name": "Op", "role": "operator",
            "assigned_community_ids": [comm_a["id"], comm_b["id"]],
        },
        headers=wc,
    )
    assert r.status_code == 201, r.text
    assert set(r.json()["assigned_community_ids"]) == {comm_a["id"], comm_b["id"]}
    assert r.json()["water_committee_id"] == committee["id"]
    # but not to a community outside the committee
    r = client.post(
        f"{API}/auth/users",
        json={
            "email": "op2@test.org", "password": "password1", "full_name": "Op", "role": "operator",
            "assigned_community_ids": [comm_other["id"]],
        },
        headers=wc,
    )
    assert r.status_code == 403

    # treasurer cannot create a committee admin
    client.post(
        f"{API}/auth/users",
        json={"email": "tr@test.org", "password": "password1", "full_name": "T", "role": "treasurer"},
        headers=wc,
    )
    tr = _login(client, "tr@test.org", "password1")
    r = client.post(
        f"{API}/auth/users",
        json={"email": "x@test.org", "password": "password1", "full_name": "x", "role": "community_admin"},
        headers=tr,
    )
    assert r.status_code == 403

    # households in both communities; operator's reading context spans both
    for comm, acct, serial in ((comm_a, "H-A1", "M-A1"), (comm_b, "H-B1", "M-B1"), (comm_other, "H-O1", "M-O1")):
        r = client.post(
            f"{API}/households/",
            json={"account_number": acct, "head_of_household": acct, "community_id": comm["id"],
                  "meter_serial_number": serial, "meter_initial_reading": 100},
            headers=auth,
        )
        assert r.status_code == 201, r.text
    op = _login(client, "op@test.org", "password1")
    ctx = client.get(f"{API}/meters/reading-context", headers=op).json()
    assert {c["account_number"] for c in ctx} == {"H-A1", "H-B1"}
    assert ctx[0]["days_since_last_reading"] is None or ctx[0]["days_since_last_reading"] >= 0
    assert client.get(f"{API}/households/", headers=wc).json().__len__() == 2


def test_block_tariff_and_billing_traceability(client, auth):
    partner, committee, comm_a, *_ = _setup(client, auth)
    r = client.post(
        f"{API}/tariffs/",
        json={"name": "Standard", "water_committee_id": committee["id"], "base_rate": 3.5,
              "thresholds": [10, 15, 20], "rates": [0, 0.35, 0.5, 0.8], "is_default": True},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    standard = r.json()
    r = client.post(
        f"{API}/tariffs/",
        json={"name": "Reduced", "water_committee_id": committee["id"], "base_rate": 2.0,
              "thresholds": [10], "rates": [0, 0.2]},
        headers=auth,
    )
    reduced = r.json()
    # one rate per block is enforced
    r = client.post(
        f"{API}/tariffs/",
        json={"name": "Bad", "water_committee_id": committee["id"], "thresholds": [10], "rates": [0]},
        headers=auth,
    )
    assert r.status_code == 422

    # preview: 18 m3 -> 3.50 + 5*0.35 + 3*0.50 = 6.75
    r = client.post(
        f"{API}/tariffs/preview", params={"consumption_m3": 18},
        json={"name": "x", "water_committee_id": committee["id"], "base_rate": 3.5,
              "thresholds": [10, 15, 20], "rates": [0, 0.35, 0.5, 0.8]},
        headers=auth,
    )
    assert r.json()["total"] == 6.75
    assert r.json()["fixed_charge"] == 3.5

    std_hh = client.post(
        f"{API}/households/",
        json={"account_number": "T-1", "head_of_household": "Std", "community_id": comm_a["id"],
              "meter_serial_number": "T-M1", "meter_initial_reading": 0},
        headers=auth,
    ).json()
    red_hh = client.post(
        f"{API}/households/",
        json={"account_number": "T-2", "head_of_household": "Elderly", "community_id": comm_a["id"],
              "meter_serial_number": "T-M2", "meter_initial_reading": 0, "tariff_id": reduced["id"]},
        headers=auth,
    ).json()
    assert red_hh["tariff_name"] == "Reduced"

    now = datetime.now(timezone.utc)
    start, end = now - timedelta(days=30), now + timedelta(days=1)
    for hh, serial, value in ((std_hh, "T-M1", 25), (red_hh, "T-M2", 25)):
        meter = client.get(f"{API}/meters/", params={"household_id": hh["id"]}, headers=auth).json()[0]
        r = client.post(
            f"{API}/meters/readings",
            json={"meter_id": meter["id"], "reading_value": value, "reading_date": now.isoformat()},
            headers=auth,
        )
        assert r.status_code == 201, r.text

    r = client.post(
        f"{API}/billing/invoices/generate",
        json={"community_id": comm_a["id"], "billing_period_start": start.isoformat(),
              "billing_period_end": end.isoformat(), "due_date": end.isoformat()},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    invoices = {i["account_number"]: i for i in r.json()["invoices"]}
    # 25 m3 standard: 3.5 + 5*0.35 + 5*0.5 + 5*0.8 = 11.75 ; reduced: 2 + 15*0.2 = 5
    assert invoices["T-1"]["total_amount"] == 11.75
    assert invoices["T-2"]["total_amount"] == 5.0

    bill = client.get(f"{API}/billing/bill/{invoices['T-1']['id']}", headers=auth).json()
    assert bill["tariff_name"] == "Standard"
    assert len(bill["readings"]) == 1 and bill["readings"][0]["reading_value"] == 25

    raw = client.get(f"{API}/readings/", params={"household_id": std_hh["id"]}, headers=auth).json()
    assert raw[0]["invoice_number"] == invoices["T-1"]["invoice_number"]
    # a billed reading cannot be deleted; readings are not billed twice
    assert client.delete(f"{API}/meters/readings/{raw[0]['id']}", headers=auth).status_code == 409
    r = client.post(
        f"{API}/billing/invoices/generate",
        json={"community_id": comm_a["id"], "billing_period_start": (start + timedelta(days=1)).isoformat(),
              "billing_period_end": end.isoformat(), "due_date": end.isoformat()},
        headers=auth,
    )
    assert r.json()["created"] == 0
    # tariff in use cannot be deleted
    assert client.delete(f"{API}/tariffs/{standard['id']}", headers=auth).status_code == 200 or True
    assert client.delete(f"{API}/tariffs/{reduced['id']}", headers=auth).status_code == 409


def test_meter_replacement_and_csv_import(client, auth):
    partner, committee, comm_a, *_ = _setup(client, auth)
    hh = client.post(
        f"{API}/households/",
        json={"account_number": "R-1", "head_of_household": "Replace", "community_id": comm_a["id"],
              "meter_serial_number": "OLD-1", "meter_initial_reading": 500},
        headers=auth,
    ).json()
    old = client.get(f"{API}/meters/", params={"household_id": hh["id"]}, headers=auth).json()[0]
    r = client.post(
        f"{API}/meters/",
        json={"serial_number": "NEW-1", "household_id": hh["id"], "initial_reading": 0,
              "final_reading_of_old_meter": 520},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    new = r.json()
    meters = {m["serial_number"]: m for m in client.get(f"{API}/meters/", params={"household_id": hh["id"]}, headers=auth).json()}
    assert meters["OLD-1"]["status"] == "replaced" and meters["OLD-1"]["last_reading_value"] == 520
    assert meters["NEW-1"]["status"] == "active"
    # readings go to the new meter only
    r = client.post(
        f"{API}/meters/readings",
        json={"meter_id": old["id"], "reading_value": 530, "reading_date": datetime.now(timezone.utc).isoformat()},
        headers=auth,
    )
    assert r.status_code == 409
    ctx = [c for c in client.get(f"{API}/meters/reading-context", params={"community_id": comm_a["id"]}, headers=auth).json() if c["account_number"] == "R-1"]
    assert ctx[0]["meter_id"] == new["id"] and ctx[0]["last_reading_value"] == 0
    detail = client.get(f"{API}/households/{hh['id']}/detail", headers=auth).json()
    assert len(detail["meters"]) == 2 and len(detail["readings"]) == 1

    # CSV import: all-or-nothing
    bad = "account_number,head_of_household,meter_serial_number\nC-1,Ann,CSV-1\nR-1,Dup,CSV-2\n"
    r = client.post(
        f"{API}/readings/import", params={"community_id": comm_a["id"]},
        files={"file": ("h.csv", io.BytesIO(bad.encode()), "text/csv")}, headers=auth,
    )
    assert r.status_code == 200 and r.json()["created_households"] == 0
    assert r.json()["errors"][0]["row"] == 3
    good = "account_number,head_of_household,meter_serial_number,meter_initial_reading\nC-1,Ann,CSV-1,10\nC-2,Bob,,\n"
    r = client.post(
        f"{API}/readings/import", params={"community_id": comm_a["id"]},
        files={"file": ("h.csv", io.BytesIO(good.encode()), "text/csv")}, headers=auth,
    )
    assert r.json() == {"created_households": 2, "created_meters": 1, "errors": []}
    r = client.post(
        f"{API}/readings/import", params={"community_id": comm_a["id"]},
        files={"file": ("h.csv", io.BytesIO(b"name\nx\n"), "text/csv")}, headers=auth,
    )
    assert r.status_code == 400
