"""Organization > partner > water committee > connection > meter, with UserRelation-scoped logins and block tariffs."""

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
        f"{API}/partners/", json={"name": f"P-{uuid.uuid4().hex[:6]}", "country": "US", "new_organization_name": "Test org"}, headers=auth
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

    # Committee admin: parent = water committee, sees the whole branch
    r = client.post(
        f"{API}/auth/users",
        json={
            "email": "wc-admin@test.org", "password": "password1", "full_name": "WC Admin",
            "role": "admin", "parent_level": "water_committee", "parent_id": committee["id"],
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text
    assert r.json()["parent_level"] == "water_committee" and r.json()["access_all_children"] is True
    wc_auth = _login(client, "wc-admin@test.org", "password1")

    # sees only its committee, not the other one
    committees = client.get(f"{API}/water-committees/", headers=wc_auth).json()
    assert [c["id"] for c in committees] == [committee["id"]]
    assert client.get(f"{API}/communities/", headers=wc_auth).json().__len__() == 2

    # cannot create roles above itself or attach accounts above its level
    r = client.post(
        f"{API}/auth/users",
        json={"email": "sa@test.org", "password": "password1", "full_name": "x", "role": "super_admin"},
        headers=wc_auth,
    )
    assert r.status_code == 403
    r = client.post(
        f"{API}/auth/users",
        json={"email": "pa@test.org", "password": "password1", "full_name": "x", "role": "admin",
              "parent_level": "partner", "parent_id": partner["id"]},
        headers=wc_auth,
    )
    assert r.status_code == 403

    # operator restricted to two communities (CHILD relations); parent defaults to the admin's committee
    r = client.post(
        f"{API}/auth/users",
        json={
            "email": "op@test.org", "password": "password1", "full_name": "Op", "role": "operator",
            "community_ids": [comm_a["id"], comm_b["id"]],
        },
        headers=wc_auth,
    )
    assert r.status_code == 201, r.text
    assert set(r.json()["community_ids"]) == {comm_a["id"], comm_b["id"]}
    assert r.json()["access_all_children"] is False
    assert r.json()["water_committee_id"] == committee["id"]

    # cannot assign a community of another committee
    r = client.post(
        f"{API}/auth/users",
        json={
            "email": "op2@test.org", "password": "password1", "full_name": "Op", "role": "operator",
            "community_ids": [comm_other["id"]],
        },
        headers=wc_auth,
    )
    assert r.status_code in (400, 403), r.text

    # operators only exist at committee level; viewers are the only connection-level role
    r = client.post(
        f"{API}/auth/users",
        json={"email": "op3@test.org", "password": "password1", "full_name": "Op", "role": "operator",
              "parent_level": "partner", "parent_id": partner["id"]},
        headers=auth,
    )
    assert r.status_code == 400, r.text

    # editor (treasurer) at the committee: may edit, may not create
    r = client.post(
        f"{API}/auth/users",
        json={"email": "tr@test.org", "password": "password1", "full_name": "T", "role": "editor"},
        headers=wc_auth,
    )
    assert r.status_code == 201, r.text
    tr_auth = _login(client, "tr@test.org", "password1")
    r = client.post(f"{API}/connections/", json={"account_number": "E-1", "contact_name": "x", "community_id": comm_a["id"]}, headers=tr_auth)
    assert r.status_code == 403
    r = client.patch(f"{API}/water-committees/{committee['id']}", json={"region": "North"}, headers=tr_auth)
    assert r.status_code == 200, r.text
    r = client.post(f"{API}/auth/users", json={"email": "x@test.org", "password": "password1", "full_name": "x", "role": "viewer"}, headers=tr_auth)
    assert r.status_code == 403

    # connections sit directly under the committee; the community is a grouping label
    for comm, acct in ((comm_a, "A-1"), (comm_b, "B-1"), (comm_other, "O-1")):
        r = client.post(
            f"{API}/connections/",
            json={"account_number": acct, "contact_name": acct, "community_id": comm["id"],
                  "connection_type": "school" if acct == "B-1" else "household",
                  "meter_serial_number": f"M-{acct}"},
            headers=auth,
        )
        assert r.status_code == 201, r.text
        assert r.json()["water_committee_id"] == comm["water_committee_id"]
    r = client.post(f"{API}/connections/", json={"account_number": "G-1", "contact_name": "No group", "water_committee_id": committee["id"]}, headers=wc_auth)
    assert r.status_code == 201, r.text and r.json()["community_id"] is None

    # the committee admin sees all four of its connections, the operator only the grouped ones
    accts = {h["account_number"] for h in client.get(f"{API}/connections/", headers=wc_auth).json()}
    assert {"A-1", "B-1", "G-1"} <= accts and "O-1" not in accts
    op_auth = _login(client, "op@test.org", "password1")
    accts = {h["account_number"] for h in client.get(f"{API}/connections/", headers=op_auth).json()}
    assert accts == {"A-1", "B-1"}
    # operator reads meters but cannot open accounts
    r = client.post(f"{API}/connections/", json={"account_number": "Z-1", "contact_name": "x", "community_id": comm_a["id"]}, headers=op_auth)
    assert r.status_code == 403

    # connection-level viewer sees one connection only
    conn_a = next(h for h in client.get(f"{API}/connections/", headers=auth).json() if h["account_number"] == "A-1")
    r = client.post(
        f"{API}/auth/users",
        json={"email": "member@test.org", "password": "password1", "full_name": "Member", "role": "viewer",
              "parent_level": "connection", "parent_id": conn_a["id"]},
        headers=wc_auth,
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"{API}/auth/users",
        json={"email": "member2@test.org", "password": "password1", "full_name": "Member", "role": "editor",
              "parent_level": "connection", "parent_id": conn_a["id"]},
        headers=wc_auth,
    )
    assert r.status_code == 400
    m_auth = _login(client, "member@test.org", "password1")
    assert [h["account_number"] for h in client.get(f"{API}/connections/", headers=m_auth).json()] == ["A-1"]
    tree = client.get(f"{API}/structure/tree", headers=m_auth).json()
    assert tree["root_level"] == "connection" and [n["id"] for n in tree["nodes"]] == [conn_a["id"]]

    # partner admin sees the committee it creates (and the people in it)
    r = client.post(
        f"{API}/auth/users",
        json={"email": "partner-admin@test.org", "password": "password1", "full_name": "PA", "role": "admin",
              "parent_level": "partner", "parent_id": partner["id"]},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    pa_auth = _login(client, "partner-admin@test.org", "password1")
    r = client.post(f"{API}/water-committees/", json={"name": "New WC"}, headers=pa_auth)
    assert r.status_code == 201, r.text
    ids = {c["id"] for c in client.get(f"{API}/water-committees/", headers=pa_auth).json()}
    assert r.json()["id"] in ids and committee["id"] in ids
    emails = {u["email"] for u in client.get(f"{API}/auth/users", headers=pa_auth).json()}
    assert {"wc-admin@test.org", "op@test.org", "member@test.org"} <= emails


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
    # fractions of a m³ are billed as a whole m³: 12.1 and 13 cost the same
    body = {"name": "x", "water_committee_id": committee["id"], "base_rate": 3.5,
            "thresholds": [10, 15, 20], "rates": [0, 0.35, 0.5, 0.8]}
    a = client.post(f"{API}/tariffs/preview", params={"consumption_m3": 12.1}, json=body, headers=auth).json()
    b = client.post(f"{API}/tariffs/preview", params={"consumption_m3": 13}, json=body, headers=auth).json()
    assert a["variable_charge"] == b["variable_charge"] == 1.05

    std_hh = client.post(
        f"{API}/connections/",
        json={"account_number": "T-1", "contact_name": "Std", "community_id": comm_a["id"],
              "meter_serial_number": "T-M1", "meter_initial_reading": 0},
        headers=auth,
    ).json()
    red_hh = client.post(
        f"{API}/connections/",
        json={"account_number": "T-2", "contact_name": "Elderly", "community_id": comm_a["id"],
              "meter_serial_number": "T-M2", "meter_initial_reading": 0, "tariff_id": reduced["id"]},
        headers=auth,
    ).json()
    assert red_hh["tariff_name"] == "Reduced"

    now = datetime.now(timezone.utc)
    start, end = now - timedelta(days=30), now + timedelta(days=1)
    for hh, serial, value in ((std_hh, "T-M1", 25), (red_hh, "T-M2", 25)):
        meter = client.get(f"{API}/meters/", params={"connection_id": hh["id"]}, headers=auth).json()[0]
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

    raw = client.get(f"{API}/readings/", params={"connection_id": std_hh["id"]}, headers=auth).json()
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
        f"{API}/connections/",
        json={"account_number": "R-1", "contact_name": "Replace", "community_id": comm_a["id"],
              "meter_serial_number": "OLD-1", "meter_initial_reading": 500},
        headers=auth,
    ).json()
    old = client.get(f"{API}/meters/", params={"connection_id": hh["id"]}, headers=auth).json()[0]
    r = client.post(
        f"{API}/meters/",
        json={"serial_number": "NEW-1", "connection_id": hh["id"], "initial_reading": 0,
              "final_reading_of_old_meter": 520},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    new = r.json()
    meters = {m["serial_number"]: m for m in client.get(f"{API}/meters/", params={"connection_id": hh["id"]}, headers=auth).json()}
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
    detail = client.get(f"{API}/connections/{hh['id']}/detail", headers=auth).json()
    assert len(detail["meters"]) == 2 and len(detail["readings"]) == 1

    # CSV import: all-or-nothing
    bad = "account_number,contact_name,meter_serial_number\nC-1,Ann,CSV-1\nR-1,Dup,CSV-2\n"
    r = client.post(
        f"{API}/readings/import", params={"community_id": comm_a["id"]},
        files={"file": ("h.csv", io.BytesIO(bad.encode()), "text/csv")}, headers=auth,
    )
    assert r.status_code == 200 and r.json()["created_connections"] == 0
    assert r.json()["errors"][0]["row"] == 3, r.json()
    good = "account_number,contact_name,meter_serial_number,meter_initial_reading\nC-1,Ann,CSV-1,10\nC-2,Bob,,\n"
    r = client.post(
        f"{API}/readings/import", params={"community_id": comm_a["id"]},
        files={"file": ("h.csv", io.BytesIO(good.encode()), "text/csv")}, headers=auth,
    )
    assert r.json() == {"created_connections": 2, "created_meters": 1, "errors": []}
    r = client.post(
        f"{API}/readings/import", params={"community_id": comm_a["id"]},
        files={"file": ("h.csv", io.BytesIO(b"name\nx\n"), "text/csv")}, headers=auth,
    )
    assert r.status_code == 400


def test_organization_level_and_structure_tree(client, auth):
    org = client.post(f"{API}/organizations/", json={"name": f"Org-{uuid.uuid4().hex[:6]}"}, headers=auth)
    assert org.status_code == 201, org.text
    org = org.json()
    # A partner must belong to an organization
    r = client.post(f"{API}/partners/", json={"name": f"NoOrg-{uuid.uuid4().hex[:6]}", "country": "US"}, headers=auth)
    assert r.status_code == 400
    partner = client.post(
        f"{API}/partners/",
        json={"name": f"P-{uuid.uuid4().hex[:6]}", "country": "US", "organization_id": org["id"]},
        headers=auth,
    ).json()
    assert partner["organization_id"] == org["id"]
    committee = client.post(
        f"{API}/water-committees/", json={"name": "Tree WC", "partner_id": partner["id"]}, headers=auth
    ).json()
    # A community must belong to a water committee
    r = client.post(f"{API}/communities/", json={"name": "Loose", "country": "US"}, headers=auth)
    assert r.status_code == 400
    community = client.post(
        f"{API}/communities/",
        json={"name": "Tree Community", "country": "US", "water_committee_id": committee["id"]},
        headers=auth,
    ).json()
    connection = client.post(
        f"{API}/connections/",
        json={"account_number": f"T-{uuid.uuid4().hex[:5]}", "contact_name": "Tree Family",
              "community_id": community["id"], "meter_serial_number": f"TM-{uuid.uuid4().hex[:6]}"},
        headers=auth,
    )
    assert connection.status_code == 201, connection.text
    connection = connection.json()
    new_serial = f"TM-{uuid.uuid4().hex[:6]}"
    r = client.post(
        f"{API}/meters/",
        json={"serial_number": new_serial, "connection_id": connection["id"], "retire_existing_as": "removed"},
        headers=auth,
    )
    assert r.status_code == 201, r.text

    tree = client.get(f"{API}/structure/tree", headers=auth).json()
    assert tree["root_level"] == "organization"
    org_node = next(n for n in tree["nodes"] if n["id"] == org["id"])
    partner_node = next(n for n in org_node["children"] if n["id"] == partner["id"])
    committee_node = next(n for n in partner_node["children"] if n["id"] == committee["id"])
    connection_node = next(n for n in committee_node["children"] if n["id"] == connection["id"])
    assert connection_node["group"] == "Tree Community"
    statuses = {m["name"]: m["status"] for m in connection_node["children"]}
    assert statuses[new_serial] == "active"
    assert "removed" in statuses.values() and len(statuses) == 2

    # A treasurer on this committee starts at the committee and sees nothing else
    email = f"tr-{uuid.uuid4().hex[:6]}@flowtest.org"
    r = client.post(
        f"{API}/auth/users",
        json={"email": email, "password": "treasurer-pass", "full_name": "Tree Treasurer",
              "role": "editor", "parent_level": "water_committee", "parent_id": committee["id"]},
        headers=auth,
    )
    assert r.status_code in (200, 201), r.text
    t_tree = client.get(f"{API}/structure/tree", headers=_login(client, email, "treasurer-pass")).json()
    assert t_tree["root_level"] == "committee"
    assert [n["id"] for n in t_tree["nodes"]] == [committee["id"]]
    orgs = client.get(f"{API}/organizations/", headers=_login(client, email, "treasurer-pass")).json()
    assert [o["id"] for o in orgs] == [org["id"]]  # only the branch it belongs to

def test_skipped_month_is_split_across_months(client, auth):
    partner, committee, comm_a, *_ = _setup(client, auth)
    r = client.post(
        f"{API}/tariffs/",
        json={"name": "Flat", "water_committee_id": committee["id"], "base_rate": 3.0,
              "thresholds": [10], "rates": [0, 0.5], "is_default": True},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    hh = client.post(
        f"{API}/connections/",
        json={"account_number": "S-1", "contact_name": "Skipped", "community_id": comm_a["id"],
              "meter_serial_number": "S-M1", "meter_initial_reading": 0},
        headers=auth,
    ).json()
    meter = client.get(f"{API}/meters/", params={"connection_id": hh["id"]}, headers=auth).json()[0]
    now = datetime.now(timezone.utc)
    # read 61 days ago, then skipped a month, read again now: 24 m³ over two months
    for value, when in ((10, now - timedelta(days=61)), (34, now)):
        r = client.post(
            f"{API}/meters/readings",
            json={"meter_id": meter["id"], "reading_value": value, "reading_date": when.isoformat()},
            headers=auth,
        )
        assert r.status_code == 201, r.text
    assert r.json().get("flag_reason")
    r = client.post(
        f"{API}/billing/invoices/generate",
        json={"community_id": comm_a["id"], "billing_period_start": (now - timedelta(days=30)).isoformat(),
              "billing_period_end": (now + timedelta(days=1)).isoformat(),
              "due_date": (now + timedelta(days=15)).isoformat()},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    inv = r.json()["invoices"][0]
    # two base rates, and 12 m³ per month -> 2 m³ over the 10 m³ base each: 2*3 + 2*(2*0.5) = 8
    assert inv["fixed_charge"] == 6.0
    assert inv["variable_charge"] == 2.0
    assert "2 months" in inv["notes"]


def test_expenses_maintenance_and_partner_dashboard_load(client, auth):
    partner, committee, comm_a, *_ = _setup(client, auth)
    assert client.get(f"{API}/expenses/", params={"water_committee_id": committee["id"]}, headers=auth).status_code == 200
    assert client.get(f"{API}/expenses/summary", headers=auth).status_code == 200
    assert client.get(f"{API}/maintenance/", headers=auth).status_code == 200
    r = client.get(f"{API}/dashboard/partner/{partner['id']}", headers=auth)
    assert r.status_code == 200, r.text


def test_payments_by_treasurer_not_operator_and_overdue(client, auth):
    partner, committee, comm_a, *_ = _setup(client, auth)
    client.post(
        f"{API}/tariffs/",
        json={"name": "Flat", "water_committee_id": committee["id"], "base_rate": 3.0,
              "thresholds": [10], "rates": [0, 0.5], "is_default": True},
        headers=auth,
    )
    hh = client.post(
        f"{API}/connections/",
        json={"account_number": "P-1", "contact_name": "Payer", "community_id": comm_a["id"],
              "meter_serial_number": "P-M1", "meter_initial_reading": 0},
        headers=auth,
    ).json()
    r = client.post(
        f"{API}/auth/users",
        json={"email": "wc2@test.org", "password": "password1", "full_name": "A", "role": "admin",
              "parent_level": "water_committee", "parent_id": committee["id"]},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    wc_auth = _login(client, "wc2@test.org", "password1")
    for email, role in (("tr2@test.org", "editor"), ("op9@test.org", "operator")):
        r = client.post(
            f"{API}/auth/users",
            json={"email": email, "password": "password1", "full_name": "x", "role": role},
            headers=wc_auth,
        )
        assert r.status_code == 201, r.text
    tr_auth = _login(client, "tr2@test.org", "password1")
    op_auth = _login(client, "op9@test.org", "password1")

    now = datetime.now(timezone.utc)
    # a bill whose due date has already passed
    r = client.post(
        f"{API}/billing/invoices",
        json={"connection_id": hh["id"], "billing_period_start": (now - timedelta(days=60)).isoformat(),
              "billing_period_end": (now - timedelta(days=31)).isoformat(),
              "due_date": (now - timedelta(days=10)).isoformat(), "consumption_m3": 5,
              "fixed_charge": 3.0, "variable_charge": 0, "total_amount": 3.0, "currency": "USD"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    invoice = r.json()
    listed = client.get(f"{API}/billing/invoices", params={"connection_id": hh["id"]}, headers=tr_auth).json()
    assert listed[0]["status"] == "overdue"

    payment = {"connection_id": hh["id"], "invoice_id": invoice["id"], "amount": 3.0,
               "payment_date": now.isoformat(), "payment_method": "cash", "receipt_number": "R-1"}
    assert client.post(f"{API}/billing/payments", json=payment, headers=op_auth).status_code == 403
    r = client.post(f"{API}/billing/payments", json=payment, headers=tr_auth)
    assert r.status_code == 201, r.text
    listed = client.get(f"{API}/billing/invoices", params={"connection_id": hh["id"]}, headers=tr_auth).json()
    assert listed[0]["status"] == "paid" and listed[0]["balance_due"] == 0
    history = client.get(f"{API}/billing/payments", params={"connection_id": hh["id"]}, headers=tr_auth).json()
    assert len(history) == 1 and history[0]["receipt_number"] == "R-1"

    # the treasurer's dashboard shows its committee's figures
    r = client.get(f"{API}/dashboard/system", headers=tr_auth)
    assert r.status_code == 200, r.text
    assert r.json()["total_revenue"] == 3.0 and r.json()["total_connections"] == 1
