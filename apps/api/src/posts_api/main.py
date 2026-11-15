from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, comment, post, session, user, vote

app = FastAPI(title="Posts API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(post.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(vote.router)
app.include_router(comment.router)
app.include_router(session.router)
