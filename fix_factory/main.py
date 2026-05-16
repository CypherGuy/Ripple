from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fix_factory.routes.fix import router as fix_router

app = FastAPI(title="Ripple Fix Factory")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "fix_factory"}


app.include_router(fix_router)
