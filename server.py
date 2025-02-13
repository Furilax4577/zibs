# Import des dépendances
import json
import sys
import paho.mqtt.client as mqtt
import requests
import re

from typing import TypedDict
from datetime import datetime

class ZendureApiResponseData(TypedDict):
    appKey: str
    secret: str
    mqttUrl: str
    port: int
class ZendureApiResponse(TypedDict):
    code: int
    success: bool
    data: ZendureApiResponseData
    msg: str

now = datetime.now()
formatted = now.strftime("%Y-%m-%d %H:%M:%S")

print(f"Démarrage de l'addon {formatted}")  # Exemple : 2025-02-13 14:35:12

# Variables
CONFIG_PATH = "/data/options.json"
CONFIG_PATH = "data/options.json" # local
TOPIC_STATE_PATTERN = r"([^/]+)/([^/]+)/state"
ZENDURE_DEVICES = []

def load_config():
    "Charge la configuration depuis Home Assistant."
    try:
        with open(CONFIG_PATH, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"ERREUR: Lors du chargement de la config : {e}")
        sys.exit(1)  # Quitte le script immédiatement

# Charger la configuration HASS
config = load_config()
ZENDURE_EMAIL = config.get("zendure_email", "default@example.com")
ZENDURE_SN = config.get("zendure_snNumber", "UNKNOWN_SN")
ZENDURE_API_URL = config.get("zendure_apiUrl", "https://default-api-url.com")

print(f"{ZENDURE_EMAIL} {ZENDURE_SN} {ZENDURE_API_URL}")

if not ZENDURE_EMAIL or not ZENDURE_SN:
    print("ERREUR: `zendure_email` et `zendure_snNumber` doivent être définis dans la configuration.")
    sys.exit(1)  # Quitte le script immédiatement

# Envoi de la requête API
response = requests.post(ZENDURE_API_URL, json={"snNumber": ZENDURE_SN, "account": ZENDURE_EMAIL})

data:ZendureApiResponse = response.json()

if data.get("success"):
    api_data = data.get("data")

    MQTT_BROKER = api_data.get("mqttUrl", "mqtt-eu.zen-iot.com")
    MQTT_PORT = api_data.get("port", 1883)
    MQTT_USER = api_data.get("appKey", "default_user")
    MQTT_PASSWORD = api_data.get("secret", "default_password")
    MAIN_TOPIC = f"{MQTT_USER}/#"

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe(MAIN_TOPIC)

    def on_message(client, userdata, msg):
        match = re.match(TOPIC_STATE_PATTERN, msg.topic)
        if match:
            deviceUUID = match.group(2)
            if deviceUUID not in ZENDURE_DEVICES:
                ZENDURE_DEVICES.append(deviceUUID)
                print(f"Nouveau device ajouté {deviceUUID}")
            print(msg.topic+" "+str(msg.payload))

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()
else:
    print(f"Erreur : Réponse API invalide. Contenu : {data.get('msg')}")