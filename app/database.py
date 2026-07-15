from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --- URL de connexion ---
# Developpement : SQLite, fichier local a la racine du projet.
# Production : remplacer par une URL PostgreSQL, ex. :
#   postgresql+psycopg2://user:motdepasse@localhost:5432/livraison
SQLALCHEMY_DATABASE_URL = "sqlite:///./livraison.db"

# --- Moteur ---
# connect_args={"check_same_thread": False} est specifique a SQLite :
# il autorise l'acces a la connexion depuis plusieurs threads (requis par FastAPI).
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# --- Fabrique de sessions ---
# Chaque requete API ouvrira sa propre session via cette fabrique.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Classe de base des modeles ---
# Les 7 modeles SQLAlchemy heriteront de cette Base.
# Alembic inspecte Base.metadata pour generer les migrations.
Base = declarative_base()


# --- Dependance FastAPI (utilisee a partir du Jour 3) ---
def get_db():
    """Fournit une session de base de donnees, fermee automatiquement apres usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
