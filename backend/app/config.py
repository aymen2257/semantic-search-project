from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    chroma_path: str
    collection_name: str
    embedding_model: str
    n_results_chunks: int = 30
    top_pages: int = 5

    model_config = {"env_file": ".env"}

settings = Settings()

COUNTRY_MAP = {
    "france":        "France",
    "qatar":         "Qatar",
    "uk":            "Royaume uni",
    "royaume uni":   "Royaume uni",
    "algerie":       "Algérie",
    "algérie":       "Algérie",
    "maroc":         "Maroc",
    "tunisie":       "Tunisie",
    "egypte":        "Égypte",
    "égypte":        "Égypte",
    "arabie":        "Arabie Saoudite",
    "italie":        "Italie",
    "espagne":       "Espagne",
    "allemagne":     "Allemagne",
    "turquie":       "Turquie",
    "dubai":         "Émirats Arabes Unis",
    "uae":           "Émirats Arabes Unis",
    "senegal":       "Sénégal",
    "sénégal":       "Sénégal",
    "cameroun":      "Cameroun",
    "libye":         "Libye",
    "mauritanie":    "Mauritanie",
}