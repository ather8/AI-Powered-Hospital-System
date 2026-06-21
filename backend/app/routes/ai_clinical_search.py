from fastapi import APIRouter, Depends, Request
from app.schemas.ai_clinical_search import ClinicalSearchRequest, ClinicalSearchResponse
from app.services.ai_clinical_search import clinical_search
from app.utils.rbac import require_roles
from app.utils.rate_limit import limiter, RATE_AI_CLINICAL

router = APIRouter(prefix="/ai-clinical-search", tags=["ai-clinical-search"])


@router.post("/", response_model=ClinicalSearchResponse)
@limiter.limit(RATE_AI_CLINICAL)
def search_clinical(
    request: Request,
    body: ClinicalSearchRequest,
    current_user: dict = Depends(require_roles(["doctor", "nurse"])),
):
    """Semantic clinical search via RAG pipeline. Rate-limited per user
    because it hits the embeddings API in addition to the chat model.
    """
    result = clinical_search(body.query)
    return result
