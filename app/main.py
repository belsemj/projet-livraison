from app.routers import run
from app.routers import (
    station, destination, lot, chauffeur, vehicule,
    tournee, affectation, distances, optimisation, vague,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Application d'affectation des livraisons")

# --- CORS : autorise le front Vite (dev) à appeler l'API ---
# Le front tourne sur localhost:5173, l'API sur localhost:8000.
# Ports différents = origines différentes → le navigateur bloque
# les appels fetch sans cette autorisation explicite.
origines_autorisees = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origines_autorisees,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(station.router)
app.include_router(destination.router)
app.include_router(lot.router)
app.include_router(chauffeur.router)
app.include_router(vehicule.router)
app.include_router(tournee.router)
app.include_router(affectation.router)
app.include_router(distances.router)
app.include_router(optimisation.router)
app.include_router(vague.router)
app.include_router(run.router)


@app.get("/")
def racine():
    return {"message": "API d'affectation des livraisons — opérationnelle"}


@app.get("/sante")
def sante():
    return {"statut": "ok"}
