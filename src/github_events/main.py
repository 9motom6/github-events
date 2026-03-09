from fastapi import FastAPI

app = FastAPI(
    title="GitHub Event Monitor",
    description="An API for streaming and analyzing GitHub events.",
)


@app.get("/", tags=["Health"])
async def read_root():
    return {"status": "ok"}
