import random
import string
import os

FICHIER_IDS = "ids_book.txt"

def charger_ids() -> set:
    if not os.path.exists(FICHIER_IDS):
        return set()
    with open(FICHIER_IDS, "r") as f:
        return set(line.strip() for line in f.readlines())

def enregistrer_id(nouvel_id: str):
    with open(FICHIER_IDS, "a") as f:
        f.write(nouvel_id + "\n")

def generer_id_unique(prefix: str, longueur: int = 8) -> str:
    existing_ids = charger_ids()
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = ''.join(random.choice(alphabet) for _ in range(longueur))
        new_id = f"{prefix}-{code}"
        if new_id not in existing_ids:
            enregistrer_id(new_id)
            return new_id

