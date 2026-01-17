# services/journal.py
"""Journalisation centralisée des actions de l'application.

Fournit une fonction simple `enregistrer_action` pour écrire des
entrées structurées dans un fichier de log situé dans
`data/logs/systeme.log`.
"""

import logging
import os
from datetime import datetime
from typing import Optional

# Dossier de logs
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


LOG_FILE = os.path.join(LOG_DIR, "systeme.log")

# Configuration du logger
logger = logging.getLogger("Bibliotheque")
logger.setLevel(logging.INFO)

# Évite les duplications si le module est rechargé
if not logger.handlers:
    # Handler fichier (avec rotation quotidienne si besoin)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)


def enregistrer_action(
    acteur: str,
    action: str,
    cible: str,
    details: Optional[str] = None,
    niveau: str = "INFO"
):
    """Enregistre une action utilisateur ou système dans le journal.

    Le message est formaté de manière compacte et envoyé au logger
    configuré. `niveau` peut être "INFO", "WARNING" ou "ERROR".
    """
    message = f"{acteur} | {action} | {cible}"
    if details:
        message += f" | {details}"
    
    if niveau == "ERROR":
        logger.error(message)
    elif niveau == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)