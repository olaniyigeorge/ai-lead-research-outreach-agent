from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.schemas import AccessRequestOut, CreateAccessRequestBody, RequestOtpBody, VerifyOtpBody, VerifyOtpResponse
from apps.api.services.access_request_service import create_access_request
from apps.api.services.auth_service import request_otp_for_email, verify_otp_for_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-otp", status_code=202)
def request_otp_endpoint(body: RequestOtpBody, db: Session = Depends(get_db)) -> None:
    request_otp_for_email(db, body.email)


@router.post("/request-access", response_model=AccessRequestOut, status_code=201)
def request_access_endpoint(body: CreateAccessRequestBody, db: Session = Depends(get_db)) -> AccessRequestOut:
    request = create_access_request(db, body.email, body.reason)
    return AccessRequestOut.model_validate(request)


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp_endpoint(body: VerifyOtpBody, db: Session = Depends(get_db)) -> VerifyOtpResponse:
    result = verify_otp_for_email(db, body.email, body.token)
    return VerifyOtpResponse(**result)
