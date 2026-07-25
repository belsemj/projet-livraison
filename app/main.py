from app.routers import (
    station, destination, lot, chauffeur, vehicule,
    tournee, affectation, distances, optimisation,
)
from fastapi import FastAPI

app = FastAPI(title="Application d'affectation des livraisons")
app.include_router(station.router)
app.include_router(destination.router)
app.include_router(lot.router)
app.include_router(chauffeur.router)
app.include_router(vehicule.router)
app.include_router(tournee.router)
app.include_router(affectation.router)
app.include_router(distances.router)
app.include_router(optimisation.router)


@app.get("/")
def racine():
    return {"message": "API d'affectation des livraisons — opérationnelle"}


@app.get("/sante")
def sante():
    return {"statut": "ok"}
