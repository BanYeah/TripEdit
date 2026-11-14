from fastapi import FastAPI

from api import router

app = FastAPI(title="TripEdit API")
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
