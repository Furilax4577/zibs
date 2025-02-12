# Import des dépendances
import json
import sys

# Variables
CONFIG_PATH = "/data/options.json"

def load_config():
    "Charge la configuration depuis Home Assistant."
    try:
        with open(CONFIG_PATH, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"ERREUR: Lors du chargement de la config : {e}")
        return {}

# Charger la configuration HASS
config = load_config()

ZENDURE_EMAIL = config.get("zendure_email")
ZENDURE_SN = config.get("zendure_snNumber")
ZENDURE_API_URL = config.get("zendure_apiUrl")

print(f"{ZENDURE_EMAIL} {ZENDURE_SN} {ZENDURE_API_URL}")

if not ZENDURE_EMAIL or not ZENDURE_SN:
    print("ERREUR: `zendure_email` et `zendure_snNumber` doivent être définis dans la configuration.")
    sys.exit(1)  # Quitte le script immédiatement