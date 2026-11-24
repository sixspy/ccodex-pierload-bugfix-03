"""旁封修复第18号 · 三红失败测源文件（旁封修丙）。

红线口径：**旁路禁封**。开放旁路挂起仍在册时，正式快照零增；封闸意图只进
影子草稿，待旁路闭合并原子晋升后正式册才改。甲（直接拒收）与乙（影子草稿）
不得混用；本文件落乙路径。禁止第三旁路写法，禁止只描快照页色点。

三红：
  甲 · test_red_a_side_lane_open_formal_snapshot_zero_growth
  乙 · test_red_b_reconcile_must_not_count_unpromoted_draft_as_sealed
  争用 · test_red_c_two_sessions_same_ticket_seal_lock_and_contention_trace

第18轮用测试器（pytest）见红后，才准动封闸/超重/对账/过磅服务与快照、超重两页。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app
from db import init_db

TAG = "旁封修丙"


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _auth(c: TestClient, user: str = "admin", password: str = "admin123") -> dict:
    tok = c.post(
        "/api/login", json={"username": user, "password": password}
    ).json()["token"]
    return {"Authorization": "Bearer " + tok}


def _side_lane_open_ticket(
    c: TestClient, h: dict, ticket_code: str
) -> tuple[dict, dict]:
    """夹具：开放旁路挂起仍在册、且当前仍可被封闸的过磅票（旁封修丙）。"""
    lanes = c.get("/api/lanes", headers=h).json()["items"]
    lane = next(x for x in lanes if x["lane_code"] == "LN-N-01-IN")
    # 毛重 60t > 阈值 49t，自动落旁路挂起并开超重挂起。
    res = c.post(
        "/api/tickets",
        headers=h,
        json={
            "lane_id": lane["id"],
            "bl_ref": "BL-2026-0103",
            "vehicle_plate": "测旁·018",
            "ticket_code": ticket_code,
            "axle_weights": [
                {"axle": 1, "w": 15.0},
                {"axle": 2, "w": 15.0},
                {"axle": 3, "w": 15.0},
                {"axle": 4, "w": 15.0},
            ],
        },
    )
    assert res.status_code == 200, res.text
    ticket = res.json()
    assert ticket["status"] == "旁路挂起", f"{TAG} 夹具须为旁路挂起"
    holds = c.get("/api/overloads?status=开放", headers=h).json()["items"]
    hold = next(x for x in holds if x["ticket_code"] == ticket_code)
    return ticket, hold


def _seal_rows_for(c: TestClient, h: dict, ticket_id: int) -> list[dict]:
    items = c.get("/api/seals", headers=h).json()["items"]
    return [s for s in items if s["ticket_id"] == ticket_id]


# ---------------------------------------------------------------- 甲路径红线
def test_red_a_side_lane_open_formal_snapshot_zero_growth():
    """旁封修丙 · 甲：旁路开放仍能封闸为假绿；正式快照必须零增。"""
    c = TestClient(app)
    h = _auth(c)
    ticket, hold = _side_lane_open_ticket(c, h, "WT-SIDEFIX-018A")
    assert _seal_rows_for(c, h, ticket["id"]) == [], f"{TAG} 初始不得有正式快照"

    res = c.post("/api/seals", headers=h, json={"ticket_id": ticket["id"]})

    # 旁路禁封：只落影子草稿，正式快照零增、票代不升、票态不改。
    assert res.status_code == 202, f"{TAG} 旁路开放封闸应被收为草稿: {res.text}"
    body = res.json()
    assert body["draft"] is True
    assert body["status"] == "草稿待晋升"
    assert _seal_rows_for(c, h, ticket["id"]) == [], f"{TAG} 正式快照仍增=假绿"
    detail = c.get(f"/api/tickets/{ticket['id']}", headers=h).json()["ticket"]
    assert detail["generation"] == 1
    assert detail["status"] == "旁路挂起"


# ---------------------------------------------------------------- 乙路径红线
def test_red_b_reconcile_must_not_count_unpromoted_draft_as_sealed():
    """旁封修丙 · 乙：对账不得把未晋升草稿当已封；闭环后原子晋升。"""
    c = TestClient(app)
    h = _auth(c)
    ticket, hold = _side_lane_open_ticket(c, h, "WT-SIDEFIX-018B")

    draft = c.post("/api/seals", headers=h, json={"ticket_id": ticket["id"]})

    recon = c.get("/api/reconcile/BL-2026-0103", headers=h).json()
    # 未晋升草稿不是正式快照。
    assert recon["seal_count"] == 0, f"{TAG} 对账把未晋升草稿当已封"
    assert draft.status_code == 202, f"{TAG} 草稿落册失败: {draft.text}"
    assert recon.get("draft_count") == 1, f"{TAG} 对账须显式列草稿待晋升"
    assert recon["proof_ready"] is False
    assert all(t["status"] != "已封闸" for t in recon["tickets"])

    proof = c.get(f"/api/proof/ticket/{ticket['ticket_code']}", headers=h).json()
    assert proof["has_seal"] is False
    assert proof.get("seal_draft_pending") is True
    assert proof["overload_closed"] is False
    assert proof["coherent"] is False

    # 旁路闭环：草稿原子晋升为正式快照，票代 +1，草稿清空。
    closed = c.post(
        "/api/overloads/close",
        headers=h,
        json={"hold_id": hold["id"], "note": "旁封修丙·驳载完成"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json().get("promoted_seal_ref"), f"{TAG} 闭环须原子晋升草稿"

    recon2 = c.get("/api/reconcile/BL-2026-0103", headers=h).json()
    assert recon2["seal_count"] == 1
    assert recon2.get("draft_count") == 0
    rows = _seal_rows_for(c, h, ticket["id"])
    assert len(rows) == 1 and rows[0]["ticket_generation"] == 2
    proof2 = c.get(f"/api/proof/ticket/{ticket['ticket_code']}", headers=h).json()
    assert proof2["has_seal"] is True
    assert proof2["seal_generation"] == 2
    assert proof2["overload_closed"] is True


# --------------------------------------------------------------- 争用第18路
def test_red_c_two_sessions_same_ticket_seal_lock_and_contention_trace():
    """旁封修丙 · 争用：双会话抢同一旁路票封闸须占票锁，败方只落争用痕。"""
    admin = TestClient(app)
    ha = _auth(admin)
    writer = TestClient(app)
    hw = _auth(writer, "writer", "writer123")

    ticket, _hold = _side_lane_open_ticket(writer, hw, "WT-SIDEFIX-018C")
    lock_key = f"ticket:{ticket['id']}"

    # 会话一（管理）先占票锁。
    held = admin.post(
        "/api/locks/acquire", headers=ha, json={"lock_key": lock_key}
    )
    assert held.status_code == 200, held.text

    # 会话二（读写）同票封闸：只许争用失败，不得写正式/草稿。
    res = writer.post(
        "/api/seals", headers=hw, json={"ticket_id": ticket["id"]}
    )
    assert res.status_code == 409, f"{TAG} 同票封闸须占票锁: {res.text}"
    assert "争用" in res.json()["detail"]
    assert _seal_rows_for(writer, hw, ticket["id"]) == []
    detail = writer.get(f"/api/tickets/{ticket['id']}", headers=hw).json()["ticket"]
    assert detail["generation"] == 1 and detail["status"] == "旁路挂起"

    # 败方须落争用痕（即使业务事务回滚也不得丢）。
    cont = admin.get("/api/contention", headers=ha).json()["items"]
    assert any(
        x["lock_key"] == lock_key and x["actor"] == "writer" and x["action"] == "争用"
        for x in cont
    ), f"{TAG} 双人同票封闸无锁/争用痕丢失"

    admin.post("/api/locks/release", headers=ha, json={"lock_key": lock_key})
