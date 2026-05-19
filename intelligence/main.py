import logging
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from intelligence.routes.analyze import router as analyze_router

app = FastAPI(title="Ripple Intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "intelligence"}


app.include_router(analyze_router)
