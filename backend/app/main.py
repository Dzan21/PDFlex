from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine
from app.routes_users import router as users_router
from app.routes_billing import router as billing_router
from app.routes_documents import router as documents_router
from app.routes_usage import router as usage_router

app = FastAPI(title="PDFlex API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar_one()
            return {"database_version": version}
    except Exception as e:
        return {"error": str(e)}

# --- routers ---
app.include_router(users_router)
app.include_router(billing_router)
# POZOR: routes_documents už má prefix="/documents" vnútri súboru,
# preto ho NEpridávame znova:
app.include_router(documents_router)
app.include_router(usage_router)
