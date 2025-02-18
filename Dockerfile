# Utilisation de l'image de base définie par Home Assistant
ARG BUILD_FROM
FROM $BUILD_FROM

# Installation des dépendances système nécessaires
RUN apk add --no-cache \
    python3 \
    py3-pip

# Création d'un environnement virtuel Python et installation de pip
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir requests paho-mqtt

# Configuration de l'environnement pour utiliser le venv par défaut
ENV PATH="/opt/venv/bin:$PATH"

# Définition du répertoire de travail
WORKDIR /data

# Copie des fichiers nécessaires au fonctionnement de l'add-on
COPY run.sh /
COPY server.py /server.py

# Attribution des permissions d'exécution au script principal
RUN chmod a+x /run.sh

# Exécution du script `run.sh` au démarrage du conteneur
CMD [ "/run.sh" ]