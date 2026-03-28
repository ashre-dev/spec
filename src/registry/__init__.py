from .main import app
import uvicorn


def main():
    uvicorn.run("src.registry.main:app", host="0.0.0.0", port=8010, reload=True)
