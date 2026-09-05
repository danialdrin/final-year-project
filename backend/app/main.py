import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.mongo import close_mongo_connection
from app.db.redis_client import close_redis_connection
from app.routers import auth, search, resources, analysis, knowledge_graph, interactive, exams, passport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI-Powered Student Skill Intelligence Platform Backend...")
    yield
    logger.info("Shutting down database & cache connections...")
    await close_mongo_connection()
    await close_redis_connection()

app = FastAPI(
    title="AI-Powered Student Skill Intelligence Platform API",
    description="Backend API for Resource Discovery, Local Medium Analysis, Groq AI Strong Analysis, Dual Knowledge Graphs, Adaptive Exams, and Digital Skill Passport.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(resources.router)
app.include_router(analysis.router)
app.include_router(knowledge_graph.router)
app.include_router(interactive.router)
app.include_router(exams.router)
app.include_router(passport.router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "AI-Powered Student Skill Intelligence Platform Backend",
        "version": "1.0.0"
    }
