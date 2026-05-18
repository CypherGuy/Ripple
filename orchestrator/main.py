from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from orchestrator.routes.health import router as health_router
from orchestrator.routes.webhook import router as webhook_router
from orchestrator.routes.ws import router as ws_router
from orchestrator.routes.internal import router as internal_router
from orchestrator.routes.admin import router as admin_router
from orchestrator.routes.demo import router as demo_router
from orchestrator.routes.feedback import router as feedback_router

app = FastAPI(title="Ripple Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(ws_router)
app.include_router(internal_router)
app.include_router(admin_router)
app.include_router(demo_router)
app.include_router(feedback_router)
