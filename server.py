import json
import sys
import os
import re
import requests
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import TypedDict
import sys
import time

SUPERVISOR_TOKEN: str
IS_ADDON : bool = False 

if os.getenv("SUPERVISOR_TOKEN"):
    print("Le script tourne dans Home Assistant Supervisor")
    IS_ADDON = True
elif os.getenv("HASSIO_TOKEN"):
    print("Le script tourne dans un add-on Home Assistant")
else:
    print("Le script tourne en dehors de Home Assistant")

sys.stdout.reconfigure(encoding='utf-8')  # Force l'encodage UTF-8 pour l'affichage
print(f"Encodage utilisé : {sys.stdout.encoding}")  # Vérifier l'encodage actuel

# TYPES
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

class ZendureStatePackData(TypedDict):
    sn: str

class ZendureState(TypedDict):
    outputHomePower: int
    packInputPower: int
    sn: str
    remainOutTime: int
    hyperTmp: int
    packData: ZendureStatePackData
    
class ZendureTopic(TypedDict):
   topic: str
   payload: str
   


# CONSTANTES
TOPIC_STATE_PATTERN = r"([^/]+)/([^/]+)/state"

# Chemin de config (détection auto)
if os.path.exists("/data/options.json"):
    CONFIG_PATH = "/data/options.json"  # Mode Home Assistant
else:
    CONFIG_PATH = "data/options.json"   # Mode local


# FONCTIONS
def load_config(path: str) -> dict:
    """Charge la configuration au format JSON depuis un fichier."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as err:
        print(f"ERREUR: Impossible de charger la config depuis {path} : {err}")
        sys.exit(1)
    except Exception as e:
        print(f"ERREUR INCONNUE lors du chargement de la config : {e}")
        sys.exit(1)


def send_api_request(url: str, payload: dict) -> ZendureApiResponse:
    """Envoie une requête POST à l'API Zendure et renvoie la réponse au format dict typé."""
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()  # Lève une exception en cas de statut HTTP >= 400
        data: ZendureApiResponse = response.json()
        return data
    except requests.exceptions.RequestException as err:
        print(f"ERREUR: Echec de la requête API ({url}): {err}")
        sys.exit(1)


def on_connect(client, userdata, flags, reason_code, properties=None):
    """Callback exécuté lors de la connexion MQTT."""
    print("Connecté au broker MQTT.")
    # On souscrit au topic 'MAIN_TOPIC' stocké dans userdata
    main_topic = userdata.get("main_topic", "#")
    client.subscribe(main_topic)


def on_message(client, userdata, msg):
    """Callback exécuté à la réception d'un message MQTT."""
    match = re.match(TOPIC_STATE_PATTERN, msg.topic)
    if match:
        payload_str = msg.payload.decode('utf-8')
        payload = json.loads(payload_str)  
        device_uuid = match.group(2)
        devices_list = userdata["devices_list"]
        current_time = time.time()
        if device_uuid not in devices_list:
            # devices_list.append(device_uuid)
            devices_list[device_uuid] = {
                "count":0,
                "solar_energy_kwh":0.0,
                "last_solar_input":0,
                "last_solar_update_time":current_time
            }
            print(f"Nouveau device ajouté : {device_uuid}") 

        if payload.get("solarInputPower") and device_uuid in devices_list:
            solar_input_power = payload.get("solarInputPower", 0) 
            delta_time = current_time - devices_list[device_uuid]["last_solar_update_time"]
            if delta_time > 0:
                energy_increment = (devices_list[device_uuid]["last_solar_input"] * delta_time) / (3600*1000)  

                print(f"{device_uuid}: {delta_time} {solar_input_power} {energy_increment} {devices_list[device_uuid]['solar_energy_kwh']}")
                
                devices_list[device_uuid]["solar_energy_kwh"] += energy_increment
                devices_list[device_uuid]["last_solar_input"] = solar_input_power
                devices_list[device_uuid]["last_solar_update_time"] = current_time
                
                if IS_ADDON:
                    print("pousser les données vers HASS ici")
                    # hass.states.set( # type: ignore
                    #     "sensor.zibs",
                    #     energy_increment,
                    #     {
                    #         "unit_of_measurement": "kWh",
                    #         "device_class": "energy",
                    #         "state_class": "total_increasing"
                    #     }
                    # )                

        devices_list[device_uuid]["count"] += 1  

        # print(f"Message reçu : topic={msg.topic}, payload={payload}")
        # print(f"{devices_list}")
    # else:
    #     print(f"Message ignoré (topic ne match pas la regex) : {msg.topic}")


def main():
    """Point d'entrée principal du script."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Démarrage de l'addon {now}")

    print(f"Chargement de la configuration depuis : {CONFIG_PATH}")
    config = load_config(CONFIG_PATH)

    # Lecture des variables config
    zendure_email = config.get("zendure_email")
    zendure_sn = config.get("zendure_snNumber")
    zendure_api_url = config.get("zendure_apiUrl")

    # Validation rapide
    if not zendure_email or not zendure_sn or not zendure_api_url:
        print("ERREUR: `zendure_email`, `zendure_snNumber` et `zendure_apiUrl` doivent être définis.")
        sys.exit(1)

    print(f"Paramètres récupérés : email={zendure_email}, sn={zendure_sn}, api_url={zendure_api_url}")

    # Appel de l'API Zendure
    data = send_api_request(zendure_api_url, {"snNumber": zendure_sn, "account": zendure_email})

    if not data.get("success"):
        print(f"Erreur : Réponse API invalide. Contenu : {data.get('msg')}")
        sys.exit(1)

    # Récupération des informations MQTT
    api_data = data["data"]
    mqtt_broker = api_data.get("mqttUrl", "mqtt-eu.zen-iot.com")
    mqtt_port = api_data.get("port", 1883)
    mqtt_user = api_data.get("appKey", "default_user")
    mqtt_password = api_data.get("secret", "default_password")
    main_topic = f"{mqtt_user}/#"

    # Configuration du client MQTT
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5, userdata={
        "main_topic": main_topic,
        "devices_list": {}  # liste des devices détectés
    })
    client.username_pw_set(mqtt_user, mqtt_password)
    client.on_connect = on_connect
    client.on_message = on_message

    # Connexion et boucle infinie
    try:
        print(f"Connexion au broker MQTT : {mqtt_broker}:{mqtt_port} (user={mqtt_user})")
        client.connect(mqtt_broker, mqtt_port, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur.")
    except Exception as e:
        print(f"ERREUR INCONNUE lors de la connexion ou de la boucle MQTT : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
