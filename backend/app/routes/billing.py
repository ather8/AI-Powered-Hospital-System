from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from app.db import get_db
from app.models.billing import Billing, BillingLineItem
from app.models.patient import Patient
from app.schemas.billing import (
    BillingCreate,
    BillingUpdate,
    BillingResponse,
    LineItemCreate,
    LineItemResponse,
)
from app.services.audit import log_action
from app.services.billing import (
    recalculate_totals,
    validate_status_transition,
    InvalidStatusTransition,
)
from app.utils.rbac import require_roles
from app.utils.pagination import PageParams, PagedResponse


router = APIRouter(
    prefix="/billing",
    tags=["billing"]
)


def _get_bill_or_404(db: Session, bill_id: UUID) -> Billing:
    bill = (
        db.query(Billing)
        .options(joinedload(Billing.line_items))
        .filter(Billing.id == bill_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Billing record not found")
    return bill


@router.post("/", response_model=BillingResponse)
def create_bill(request: BillingCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin", "receptionist"]))):
    """
    Create a new billing record from one or more line items. The invoice
    total (subtotal, then amount after tax/discount) is computed server-side.
    """
    bill = Billing(
        patient_id=request.patient_id,
        tax_amount=request.tax_amount,
        discount_amount=request.discount_amount,
        method=request.method,
    )
    bill.line_items = [
        BillingLineItem(
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        for item in request.line_items
    ]
    recalculate_totals(bill)
    db.add(bill)
    db.commit()
    log_action(db, current_user["sub"], "CREATE_BILL", "BILL", str(bill.id), details=f"bill created, total={bill.amount}")
    db.refresh(bill)
    return bill


# Must be registered before /{patient_id} — otherwise "me" would be parsed
# as a patient_id path param and fail UUID validation before this route is
# ever reached.
@router.get("/me", response_model=PagedResponse[BillingResponse])
def get_my_bills(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient"])),
    page: PageParams = Depends(),
):
    """Get billing records for the current logged-in patient, paginated.

    A patient may accumulate many invoices over years of visits; returning
    them all in one response becomes slow as the history grows.
    """
    patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
    if not patient:
        return PagedResponse.create([], 0, page)
    query = (
        db.query(Billing)
        .options(joinedload(Billing.line_items))
        .filter(Billing.patient_id == patient.id)
        .order_by(Billing.id.desc())
    )
    total = query.count()
    items = query.offset(page.skip).limit(page.limit).all()
    return PagedResponse.create(items, total, page)


@router.get("/{patient_id}", response_model=PagedResponse[BillingResponse])
def get_patient_bills(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "admin", "receptionist"])),
    page: PageParams = Depends(),
):
    """Get billing records for a specific patient, paginated."""
    if current_user["role"] == "patient":
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient or patient.user_id != int(current_user["sub"]):
            raise HTTPException(status_code=403, detail="Access Forbidden")
    query = (
        db.query(Billing)
        .options(joinedload(Billing.line_items))
        .filter(Billing.patient_id == patient_id)
        .order_by(Billing.id.desc())
    )
    total = query.count()
    items = query.offset(page.skip).limit(page.limit).all()
    return PagedResponse.create(items, total, page)


@router.put("/{bill_id}", response_model=BillingResponse)
def update_bill(bill_id: UUID, request: BillingUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin", "receptionist"]))):
    """
    Update an existing billing record: status (validated against the
    allowed transition graph), method, and/or tax/discount (which trigger
    a totals recalculation).
    """
    bill = _get_bill_or_404(db, bill_id)

    updates = request.model_dump(exclude_unset=True)

    if "status" in updates:
        try:
            validate_status_transition(bill.status, updates["status"])
        except InvalidStatusTransition as e:
            raise HTTPException(status_code=400, detail=str(e))

    recompute = "tax_amount" in updates or "discount_amount" in updates
    for key, value in updates.items():
        setattr(bill, key, value)

    if recompute:
        recalculate_totals(bill)

    db.commit()
    log_action(db, current_user["sub"], "UPDATE_BILL", "BILL", str(bill.id), details="bill updated")
    db.refresh(bill)
    return bill


@router.delete("/{bill_id}")
def delete_bill(bill_id: UUID, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    """Delete a billing record."""
    bill = _get_bill_or_404(db, bill_id)
    db.delete(bill)
    db.commit()
    log_action(db, current_user["sub"], "DELETE_BILL", "BILL", str(bill.id), details="bill deleted")
    return {"message": "Billing record deleted successfully"}


@router.post("/{bill_id}/line-items", response_model=BillingResponse)
def add_line_item(bill_id: UUID, request: LineItemCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin", "receptionist"]))):
    """Add a line item to an existing bill and recompute its totals.
    Disallowed once a bill is paid or cancelled."""
    bill = _get_bill_or_404(db, bill_id)
    if bill.status in ("paid", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot add a line item to a '{bill.status}' bill")

    item = BillingLineItem(
        bill_id=bill.id,
        description=request.description,
        quantity=request.quantity,
        unit_price=request.unit_price,
    )
    db.add(item)
    db.flush()
    db.refresh(bill)
    recalculate_totals(bill)
    db.commit()
    log_action(db, current_user["sub"], "ADD_BILL_LINE_ITEM", "BILL", str(bill.id), details=f"added line item: {request.description}")
    db.refresh(bill)
    return bill


@router.delete("/{bill_id}/line-items/{item_id}", response_model=BillingResponse)
def remove_line_item(bill_id: UUID, item_id: UUID, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin", "receptionist"]))):
    """Remove a line item from a bill and recompute its totals."""
    bill = _get_bill_or_404(db, bill_id)
    if bill.status in ("paid", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot modify a '{bill.status}' bill")

    item = next((li for li in bill.line_items if li.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found on this bill")
    if len(bill.line_items) == 1:
        raise HTTPException(status_code=400, detail="A bill must have at least one line item; delete the bill instead")

    db.delete(item)
    db.flush()
    db.refresh(bill)
    recalculate_totals(bill)
    db.commit()
    log_action(db, current_user["sub"], "REMOVE_BILL_LINE_ITEM", "BILL", str(bill.id), details=f"removed line item {item_id}")
    db.refresh(bill)
    return bill
