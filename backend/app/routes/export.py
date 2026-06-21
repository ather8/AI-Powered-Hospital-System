from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.emr import EMR
from app.models.billing import Billing
from app.models.audit_log import AuditLog
from app.utils.export import export_to_csv, export_to_pdf
from app.utils.rbac import require_roles
from app.services.audit import log_action
import io

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/emr/csv")
def export_emr_csv(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin", "doctor"])),
):
    """Export all EMR records as CSV. Restricted to admin and doctor.
    Previously nurses were also excluded (correct — nurses create records
    but bulk-export of all patients' EMRs is a clinical governance action).
    Audit-logged so bulk data exports are traceable — previously exports
    left no audit trail at all.
    """
    records = db.query(EMR).all()
    data = [r.__dict__ for r in records]
    headers = ["id", "patient_id", "doctor_id", "diagnosis", "created_at"]
    csv_bytes = export_to_csv(data, headers)
    log_action(
        db, current_user["sub"], "EXPORT_EMR_CSV", "EMR", "bulk",
        details=f"Exported {len(records)} EMR records as CSV",
    )
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=emr.csv"},
    )


@router.get("/billing/pdf")
def export_billing_pdf(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"])),
):
    """Export all billing records as PDF. Admin-only."""
    records = db.query(Billing).all()
    data = [r.__dict__ for r in records]
    # Headers extended with the subtotal/tax/discount breakdown introduced
    # alongside line items -- previously this only showed the final
    # `amount`, with no visibility into how it was composed.
    headers = ["id", "patient_id", "subtotal", "discount_amount", "tax_amount", "amount", "status", "created_at"]
    pdf_bytes = export_to_pdf(data, headers, title="Billing Report")
    log_action(
        db, current_user["sub"], "EXPORT_BILLING_PDF", "Billing", "bulk",
        details=f"Exported {len(records)} billing records as PDF",
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=billing.pdf"},
    )


@router.get("/audit/csv")
def export_audit_csv(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"])),
):
    """Export all audit log entries as CSV. Admin-only.
    Note: exporting the audit log is itself audit-logged so the action is
    traceable even after a potential log purge.
    """
    records = db.query(AuditLog).all()
    data = [r.__dict__ for r in records]
    headers = ["id", "user_id", "action", "entity", "entity_id", "timestamp", "details"]
    csv_bytes = export_to_csv(data, headers)
    log_action(
        db, current_user["sub"], "EXPORT_AUDIT_CSV", "AuditLog", "bulk",
        details=f"Exported {len(records)} audit log entries as CSV",
    )
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
