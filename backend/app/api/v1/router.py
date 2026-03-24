from fastapi import APIRouter

from app.api.v1 import auth, videos, jobs, payments

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(videos.router, prefix="/videos", tags=["Videos"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"])
