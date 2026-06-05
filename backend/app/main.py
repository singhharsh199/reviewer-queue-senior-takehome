from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "review_items.json"

ReviewAction = Literal["claim", "approve", "reject", "escalate"]


class ActionRequest(BaseModel):
    action: ReviewAction
    reviewer: str = "alex"


app = FastAPI(title="Reviewer Queue API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_seed_items() -> list[dict]:
    with DATA_FILE.open() as file:
        return json.load(file)


ITEMS = load_seed_items()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/dev/reset")
async def reset_items() -> dict:
    global ITEMS
    ITEMS = load_seed_items()
    return {"items": deepcopy(ITEMS)}


def get_urgency_key(item: dict) -> tuple:
    # TAKEHOME: Order active items by urgency:
    # 1. higher risk_level outranks lower (high > medium > low)
    # 2. within same risk level, priority customers outrank standard
    # 3. older items outrank newer items (ascending submitted_at)
    risk_map = {"high": 0, "medium": 1, "low": 2}
    risk_val = risk_map.get(item.get("risk_level", "low"), 2)

    tier_map = {"priority": 0, "standard": 1}
    tier_val = tier_map.get(item.get("customer_tier", "standard"), 1)

    submitted_at = item.get("submitted_at", "")
    return (risk_val, tier_val, submitted_at)


@app.get("/review-items")
async def list_review_items(active_only: bool = True) -> dict:
    items = deepcopy(ITEMS)

    if active_only:
        # TAKEHOME: Exclude all terminal states (approved, rejected, escalated)
        items = [
            item for item in items 
            if item["status"] not in {"approved", "rejected", "escalated"}
        ]
        items.sort(key=get_urgency_key)
    else:
        # For the all-items list, keep active items sorted by urgency first,
        # and terminal items sorted by submitted_at descending at the end.
        active = [item for item in items if item["status"] not in {"approved", "rejected", "escalated"}]
        terminal = [item for item in items if item["status"] in {"approved", "rejected", "escalated"}]
        
        active.sort(key=get_urgency_key)
        terminal.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
        items = active + terminal

    return {"items": items}


@app.get("/review-items/{item_id}")
async def get_review_item(item_id: str) -> dict:
    item = find_item(item_id)
    return {"item": deepcopy(item)}


@app.post("/review-items/{item_id}/actions")
async def apply_action(item_id: str, request: ActionRequest) -> dict:
    item = find_item(item_id)

    # TAKEHOME: Terminal items must not allow further actions
    if item["status"] in {"approved", "rejected", "escalated"}:
        raise HTTPException(
            status_code=400, 
            detail="Cannot perform actions on a terminal item"
        )

    if request.action == "claim":
        # TAKEHOME: Only items with status unassigned can be claimed
        if item["status"] != "unassigned":
            raise HTTPException(
                status_code=400, 
                detail="Only unassigned items can be claimed"
            )
        item["status"] = "in_review"
        item["assigned_reviewer"] = request.reviewer
    elif request.action in {"approve", "reject", "escalate"}:
        # TAKEHOME: Only items with status in_review can be approved, rejected, or escalated
        if item["status"] != "in_review":
            raise HTTPException(
                status_code=400, 
                detail="Only items in review can be approved, rejected, or escalated"
            )
        # TAKEHOME: Ensure only the assigned reviewer can perform the action
        if item.get("assigned_reviewer") != request.reviewer:
            raise HTTPException(
                status_code=403, 
                detail=f"Only the assigned reviewer ({item.get('assigned_reviewer')}) can perform this action"
            )
        item["status"] = status_for_action(request.action)
    else:
        raise HTTPException(status_code=400, detail="Unsupported action")

    return {"item": deepcopy(item)}


def find_item(item_id: str) -> dict:
    for item in ITEMS:
        if item["id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="Review item not found")


def status_for_action(action: ReviewAction) -> str:
    if action == "approve":
        return "approved"
    if action == "reject":
        return "rejected"
    if action == "escalate":
        return "escalated"
    return "in_review"
