from app.routers import station, destination, lot
from fastapi import FastAPI

app = FastAPI(title="Application d'affectation des livraisons")
app.include_router(station.router)
app.include_router(destination.router)
app.include_router(lot.router)


@app.get("/")
def racine():
    return {"message": "API d'affectation des livraisons — opérationnelle"}


@app.get("/sante")
def sante():
    return {"statut": "ok"}
