"""Point d'entrée minimal de l'API — sert à vérifier l'environnement.
Le développement CRUD réel débutera en semaine 3."""

from fastapi import FastAPI

app = FastAPI(title="Application d'affectation des livraisons")


@app.get("/")
def racine():
    return {"message": "API d'affectation des livraisons — opérationnelle"}


@app.get("/sante")
def sante():
    return {"statut": "ok"}
