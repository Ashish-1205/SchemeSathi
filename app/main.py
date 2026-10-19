from fastapi import FastAPI

app = FastAPI(title="SchemeSaathi")

@app.get("/health")
def health():
    return {"status": "ok"}