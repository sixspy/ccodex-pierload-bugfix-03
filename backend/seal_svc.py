"""闸代快照：旁路禁封，开放旁路只落影子草稿，闭环后原子晋升。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from locks import release, require_lock
from models import SealIn
from side_lane_policy import DRAFT_STATUS, FORMAL_STATUS, SEAL_PATH, assert_fate_path
from validators import (
    format_manifest,
    validate_side_lane_sealable,
    validate_ticket_sealable,
)

router = APIRouter(tags=["seal"])


def _pending_drafts(conn, ticket_id: int):
    return conn.execute(
        """SELECT * FROM seal_drafts WHERE ticket_id=? AND status=?
           ORDER BY id""",
        (ticket_id, DRAFT_STATUS),
    ).fetchall()


def promote_pending_drafts(conn, ticket_id: int, user: str) -> list[str]:
    """旁路闭合后原子晋升：草稿 → 正式快照，仅此一处写正式册。"""
    assert_fate_path(SEAL_PATH)
    ticket = conn.execute(
        "SELECT * FROM weigh_tickets WHERE id=?", (ticket_id,)
    ).fetchone()
    if not ticket:
        return []
    now = now_iso()
    promoted: list[str] = []
    for draft in _pending_drafts(conn, ticket_id):
        gen = max(int(ticket["generation"]), int(draft["ticket_generation"]))
        seal_ref = f"GS-{ticket['ticket_code']}-G{gen}"
        cur = conn.execute(
            """INSERT INTO gate_seals(ticket_id,ticket_generation,manifest,seal_ref,
               status,sealed_at) VALUES (?,?,?,?,?,?)""",
            (ticket_id, gen, draft["manifest"], seal_ref, FORMAL_STATUS, now),
        )
        conn.execute(
            """UPDATE seal_drafts SET status='已晋升', promoted_at=?, promoted_seal_id=?
               WHERE id=?""",
            (now, cur.lastrowid, draft["id"]),
        )
        conn.execute(
            "UPDATE weigh_tickets SET generation=?, status=? WHERE id=?",
            (gen, FORMAL_STATUS, ticket_id),
        )
        write_audit(
            conn,
            user,
            "seal_promote",
            seal_ref,
            {"draft_id": draft["id"], "generation": gen},
        )
        promoted.append(seal_ref)
    return promoted


def _create_draft(conn, ticket: dict, body: SealIn, user: str) -> JSONResponse:
    """旁路开放未结：封闸意图只进影子草稿，正式快照零增。"""
    assert_fate_path(SEAL_PATH)
    if _pending_drafts(conn, body.ticket_id):
        raise HTTPException(409, "已有待晋升草稿，待旁路闭合原子晋升")
    next_gen = int(ticket["generation"]) + 1
    manifest = body.manifest or format_manifest(
        dict(ticket), float(ticket["gross_t"]), next_gen
    )
    now = now_iso()
    draft_ref = f"SD-{ticket['ticket_code']}-G{next_gen}"
    cur = conn.execute(
        """INSERT INTO seal_drafts(ticket_id,ticket_generation,manifest,draft_ref,
           status,requested_by,created_at) VALUES (?,?,?,?,?,?,?)""",
        (body.ticket_id, next_gen, manifest, draft_ref, DRAFT_STATUS, user, now),
    )
    write_audit(
        conn,
        user,
        "seal_draft_hold",
        draft_ref,
        {
            "draft_id": cur.lastrowid,
            "generation": next_gen,
            "manifest": manifest,
            "reason": "旁路开放禁封",
        },
    )
    conn.commit()
    return JSONResponse(
        status_code=202,
        content={
            "id": cur.lastrowid,
            "draft": True,
            "draft_ref": draft_ref,
            "generation": next_gen,
            "manifest": manifest,
            "status": DRAFT_STATUS,
        },
    )


@router.get("/api/seals")
def list_seals(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.*, t.ticket_code, t.vehicle_plate FROM gate_seals s
               JOIN weigh_tickets t ON t.id=s.ticket_id ORDER BY s.id DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/seal-drafts")
def list_seal_drafts(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.*, t.ticket_code FROM seal_drafts d
               JOIN weigh_tickets t ON t.id=d.ticket_id
               ORDER BY d.id DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/seals")
def create_seal(body: SealIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    lock_key = f"ticket:{body.ticket_id}"
    with connect() as conn:
        # 先占票锁；争用失败只落争用痕（旁封修丙 · 争用第18路）。
        require_lock(conn, lock_key, user)
        try:
            ticket = conn.execute(
                "SELECT * FROM weigh_tickets WHERE id=?", (body.ticket_id,)
            ).fetchone()
            if not ticket:
                raise HTTPException(404, "过磅票不存在")
            validate_ticket_sealable(dict(ticket))
            # 旁路禁封：开放旁路未结 → 只落影子草稿，正式快照零增。
            if validate_side_lane_sealable(conn, dict(ticket)):
                return _create_draft(conn, dict(ticket), body, user)
            next_gen = int(ticket["generation"]) + 1
            manifest = body.manifest or format_manifest(
                dict(ticket), float(ticket["gross_t"]), next_gen
            )
            now = now_iso()
            seal_ref = f"GS-{ticket['ticket_code']}-G{next_gen}"
            cur = conn.execute(
                """INSERT INTO gate_seals(ticket_id,ticket_generation,manifest,seal_ref,status,sealed_at)
                   VALUES (?,?,?,?,?,?)""",
                (body.ticket_id, next_gen, manifest, seal_ref, FORMAL_STATUS, now),
            )
            conn.execute(
                "UPDATE weigh_tickets SET generation=?, status=? WHERE id=?",
                (next_gen, FORMAL_STATUS, body.ticket_id),
            )
            write_audit(
                conn,
                user,
                "gate_seal",
                seal_ref,
                {
                    "seal_id": cur.lastrowid,
                    "generation": next_gen,
                    "manifest": manifest,
                },
            )
            conn.commit()
            return {
                "id": cur.lastrowid,
                "seal_ref": seal_ref,
                "generation": next_gen,
                "manifest": manifest,
                "status": FORMAL_STATUS,
            }
        finally:
            release(conn, lock_key, user)


@router.get("/api/seals/{seal_ref}")
def get_seal(seal_ref: str, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            """SELECT s.*, t.ticket_code, t.axle_weights, t.gross_t
               FROM gate_seals s JOIN weigh_tickets t ON t.id=s.ticket_id
               WHERE s.seal_ref=?""",
            (seal_ref,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "快照不存在")
        data = dict(row)
        data["axle_weights"] = json.loads(data["axle_weights"] or "[]")
        return data