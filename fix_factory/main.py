import asyncio
import concurrent.futures
import contextlib
import logging
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fix_factory.routes.fix import router as fix_router


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Each /fix request runs run_with_correction in a thread via asyncio.to_thread.
    # Default pool is min(32, cpu_count+4) = 6 on a 2-CPU Cloud Run instance.
    # With 8 concurrent hit services, 2 would queue. Set to service count headroom.
    loop = asyncio.get_event_loop()
    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=16))
    yield


app = FastAPI(title="Ripple Fix Factory", lifespan=_lifespan)

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
