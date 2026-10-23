from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import UPLOAD_DIR
from .database import Base, SessionLocal, engine
from .routers import auth, categories, favorites, items, messages, orders, users
from .seed import seed

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(
    title="CampusMart API",
    version="1.0.0",
    description=(
        "REST API for CampusMart, a student marketplace. "
        "Log in with POST /auth/login, then click Authorize and paste the access_token."
    ),
    lifespan=lifespan,
)

# Lets the Flutter app (and Flutter web) call the API during development.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """The project guidelines ask for 400 (not FastAPI's default 422) on invalid input."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part not in ("body", "query", "path"))
        errors.append({"field": field, "message": error["msg"]})
    return JSONResponse(status_code=400, content={"detail": "Validation failed", "errors": errors})


app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

for module in (auth, users, categories, items, favorites, orders, messages):
    app.include_router(module.router)


@app.get("/", tags=["Health"])
def root():
    return {"app": "CampusMart API", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
