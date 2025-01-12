from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests

from app.accounts.routes import router as accounts_router
from app.products.routes import router as products_router
from app.orders.routes import router as orders_router
from app.core.database import init_db
from app.core import settings

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app = FastAPI(docs_url="/swagger", title="Foodnest")
# app.mount("/static", StaticFiles(directory="/static"), name="static")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await init_db()


@app.get("/send-email")
def send_simple_message():
    return requests.post(
        "https://api.mailgun.net/v3/sandbox21403a81f8834248b0e09db371e795d3.mailgun.org/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": "Excited User <mailgun@sandbox21403a81f8834248b0e09db371e795d3.mailgun.org>",
            "to": ["sumbodi21@gmail.com"],
            "subject": "Welcome to Foodnest.",
            "text": "We are happy to have you here",
        },
    )
