import uvicorn
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from src.factory import create_content

app = FastAPI()


class VideoRequest(BaseModel):
    topic: str
    channel: str = "DefaultChannel"


@app.post("/generate")
async def generate_video(req: VideoRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to trigger video generation.
    """
    # Run in background to avoid timeout
    background_tasks.add_task(create_content, req.topic, req.channel)
    return {
        "status": "accepted",
        "message": f"Generation started for topic: {req.topic}",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
