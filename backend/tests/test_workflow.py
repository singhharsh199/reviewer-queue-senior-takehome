import asyncio
import pytest
from fastapi import HTTPException
from app.main import (
    list_review_items, 
    apply_action, 
    reset_items, 
    ActionRequest,
    ITEMS
)

def run_async(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset_state():
    run_async(reset_items())
    yield
    run_async(reset_items())


def test_active_queue_sorting_and_exclusion() -> None:
    # 1. Active items must exclude terminal items: approved, rejected, escalated
    response = run_async(list_review_items(active_only=True))
    active_items = response["items"]
    
    for item in active_items:
        assert item["status"] not in {"approved", "rejected", "escalated"}
        
    # 2. Check urgency sorting rules:
    # Rule 1: High risk > Medium risk > Low risk
    # Rule 2: Priority > Standard
    # Rule 3: Older submitted_at first
    for i in range(len(active_items) - 1):
        item_a = active_items[i]
        item_b = active_items[i+1]
        
        # Risk map: high=0, medium=1, low=2 (we want smaller first)
        risk_map = {"high": 0, "medium": 1, "low": 2}
        risk_a = risk_map[item_a["risk_level"]]
        risk_b = risk_map[item_b["risk_level"]]
        
        assert risk_a <= risk_b, f"Risk level out of order: {item_a['id']} vs {item_b['id']}"
        
        if risk_a == risk_b:
            tier_map = {"priority": 0, "standard": 1}
            tier_a = tier_map[item_a["customer_tier"]]
            tier_b = tier_map[item_b["customer_tier"]]
            assert tier_a <= tier_b, f"Customer tier out of order: {item_a['id']} vs {item_b['id']}"
            
            if tier_a == tier_b:
                assert item_a["submitted_at"] <= item_b["submitted_at"], f"Submitted date out of order: {item_a['id']} vs {item_b['id']}"


def test_claim_unassigned_item_success() -> None:
    # Find an unassigned item
    unassigned_item = next(item for item in ITEMS if item["status"] == "unassigned")
    item_id = unassigned_item["id"]
    
    # Claim it
    req = ActionRequest(action="claim", reviewer="alex")
    res = run_async(apply_action(item_id, req))
    updated_item = res["item"]
    
    assert updated_item["status"] == "in_review"
    assert updated_item["assigned_reviewer"] == "alex"


def test_claim_already_claimed_or_terminal_fails() -> None:
    # 1. Claiming an in-progress item fails
    in_review_item = next(item for item in ITEMS if item["status"] == "in_review")
    req = ActionRequest(action="claim", reviewer="alex")
    
    with pytest.raises(HTTPException) as exc_info:
        run_async(apply_action(in_review_item["id"], req))
    assert exc_info.value.status_code == 400
    assert "Only unassigned items can be claimed" in exc_info.value.detail

    # 2. Claiming a terminal item fails
    approved_item = next(item for item in ITEMS if item["status"] == "approved")
    with pytest.raises(HTTPException) as exc_info:
        run_async(apply_action(approved_item["id"], req))
    assert exc_info.value.status_code == 400
    assert "Cannot perform actions on a terminal item" in exc_info.value.detail


def test_approve_reject_escalate_transitions() -> None:
    # 1. Action on unassigned item fails
    unassigned_item = next(item for item in ITEMS if item["status"] == "unassigned")
    req = ActionRequest(action="approve", reviewer="alex")
    
    with pytest.raises(HTTPException) as exc_info:
        run_async(apply_action(unassigned_item["id"], req))
    assert exc_info.value.status_code == 400
    assert "Only items in review can be approved, rejected, or escalated" in exc_info.value.detail
    
    # 2. Action on in_review item by assigned reviewer succeeds
    in_review_alex = next(item for item in ITEMS if item["status"] == "in_review" and item["assigned_reviewer"] == "alex")
    req = ActionRequest(action="approve", reviewer="alex")
    res = run_async(apply_action(in_review_alex["id"], req))
    assert res["item"]["status"] == "approved"
    
    # 3. Action on in_review item by DIFFERENT reviewer fails
    in_review_other = next(item for item in ITEMS if item["status"] == "in_review" and item["assigned_reviewer"] != "alex")
    req_other = ActionRequest(action="approve", reviewer="alex")
    
    with pytest.raises(HTTPException) as exc_info:
        run_async(apply_action(in_review_other["id"], req_other))
    assert exc_info.value.status_code == 403
    assert "Only the assigned reviewer" in exc_info.value.detail


def test_terminal_items_reject_all_actions() -> None:
    approved_item = next(item for item in ITEMS if item["status"] == "approved")
    
    for action in ["claim", "approve", "reject", "escalate"]:
        req = ActionRequest(action=action, reviewer="alex")
        with pytest.raises(HTTPException) as exc_info:
            run_async(apply_action(approved_item["id"], req))
        assert exc_info.value.status_code == 400
        assert "Cannot perform actions on a terminal item" in exc_info.value.detail
