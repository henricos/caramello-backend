from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caramello.api.generated import (
    family_router,
    familyinvitation_router,
    familymember_router,
    user_router,
)
from caramello.core.config import settings

app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include generated routers
app.include_router(user_router.router)
app.include_router(family_router.router)
app.include_router(familymember_router.router)
app.include_router(familyinvitation_router.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Caramello API"}
