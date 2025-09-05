from fastapi import FastAPI
 
server = FastAPI()
 
@server.get("/")
def read_root():
    return {"message": "Hello from Azure!"}

 

