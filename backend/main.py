from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from capture import capture_screen_base64, get_active_window_title

@app.get("/")
def read_root():
    return {"status": "Thea Backend is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/capture")
def get_screen_capture():
    """Returns a snapshot of the current screen and active window title."""
    return {
        "status": "ok",
        "window": get_active_window_title(),
        "image": capture_screen_base64(scale=0.5) 
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
