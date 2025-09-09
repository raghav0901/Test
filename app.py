from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
def read_root():
    return "Hello App!"


if __name__ == "__main__":
    uvicorn.run(app, host="10.30.0.184", port=8000)


