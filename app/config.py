from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
print(BASE_DIR)
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

SCHEMES_PATH = DATA_DIR / "schemes.json"
INTENTS_PATH = DATA_DIR / "intents.csv"
OUT_OF_SCOPE_PATH = DATA_DIR / "out_of_scope.csv"
MODEL_PATH = MODEL_DIR / "intent_model.joblib"

CONFIDENCE_THRESHOLD = 0.5

# Order in which the bot asks for missing details in find_schemes
SLOT_ORDER = ["age", "gender", "state", "occupation", "income", "category"]