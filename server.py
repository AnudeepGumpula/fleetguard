"""FleetGuard API.  Run: uvicorn server:app --port 8000   (docs at /docs)

POST /v1/check                 check a proposed agent action -> allow / ask / block
GET  /v1/decisions             audit log (optionally ?status=pending)
GET  /v1/decisions/{id}        one decision
POST /v1/decisions/{id}/review approve or deny a pending ("ask") decision

If FLEETGUARD_API_KEY is set, every request must send it in the X-API-Key header.
"""
import os
from typing import Any, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import fleet
import store
from guard import check

app = FastAPI(title="FleetGuard", version="0.2.0",
              description="A Jev safety checkpoint for AI IT agents.")
store.init()


def require_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.environ.get("FLEETGUARD_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


class CheckRequest(BaseModel):
    tool: str = Field(examples=["reassign_device"])
    args: dict[str, Any] = Field(default_factory=dict, examples=[{"device_id": "MAC-0142", "to_user": "j.rivera"}])
    ticket: str = Field(min_length=1, examples=["New teacher J. Rivera starts Monday. Please assign laptop MAC-0142."])
    requester_role: str = Field(default="unknown", examples=["site_admin"])


class ReviewRequest(BaseModel):
    action: Literal["approve", "deny"]
    reviewer: str = Field(min_length=1)
    note: str = ""


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/check", dependencies=[Depends(require_key)])
def check_action(req: CheckRequest):
    call = req.model_dump()
    # Blast radius comes from our inventory, never from the agent's own claim.
    call["devices_affected"] = fleet.devices_affected(req.tool, req.args)
    result = check(call)
    rid = store.record(call, result)
    return {"id": rid, "status": store.INITIAL_STATUS[result["decision"]], **result}


@app.get("/v1/decisions", dependencies=[Depends(require_key)])
def decisions(status: Optional[str] = None, limit: int = 50):
    return store.list_decisions(status=status, limit=min(limit, 500))


@app.get("/v1/decisions/{rid}", dependencies=[Depends(require_key)])
def decision(rid: str):
    d = store.get(rid)
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")
    return d


@app.post("/v1/decisions/{rid}/review", dependencies=[Depends(require_key)])
def review(rid: str, req: ReviewRequest):
    d = store.review(rid, req.action == "approve", req.reviewer, req.note)
    if not d:
        existing = store.get(rid)
        if not existing:
            raise HTTPException(status_code=404, detail="Decision not found")
        raise HTTPException(status_code=409, detail=f"Decision is '{existing['status']}', not pending")
    return d
