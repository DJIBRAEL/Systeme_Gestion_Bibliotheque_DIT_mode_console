# validation de  donnees et nettoyage des entrees utilisateur
from datetime import datetime
from typing import Optional
import uuid
import re



def nettoyer_chaine(chaine: Optional[str]) -> Optional[str]:

    if chaine is not None and isinstance(chaine, str):
        return chaine.strip()
    return chaine


def valider_isbn(isbn: str) -> bool:
    
    isbn = isbn.replace("-", "")
    isbn = isbn.replace(" ", "")

    # Verification du format de l'ISBN - 10
    if len(isbn) == 10:
        
        if 'X' in isbn and isbn[-1] != 'X':
            return False
        
        total = 0

        for i in range(10):
            caractere = isbn[i]

            if caractere == 'X':
                valeur = 10
            else:
                
                if not caractere.isdigit():
                    return False
                valeur = int(caractere)

            poids = 10 - i
            total = total + poids * valeur

        return total % 11 == 0

    # Vérification du format de l'ISBN - 13
    elif len(isbn) == 13:
        total = 0

        for i in range(13):
            if not isbn[i].isdigit():
                return False

            chiffre = int(isbn[i])

            if i % 2 == 0:
                poids = 1
            else:
                poids = 3

            total = total + poids * chiffre

        return total % 10 == 0
    else:
        return False

def valider_annee(annee: int) -> bool:
    return 0 < annee <= datetime.now().year

def valider_mots_cles(mots_cles: Optional[list]) -> bool:
    if mots_cles is None:
        return True
    if not isinstance(mots_cles, list):
        return False
    for mot in mots_cles:
        if not isinstance(mot, str):
            return False
    return True

def valider_date(date: datetime) -> bool:
    if not isinstance(date, datetime):
        return False
    if date > datetime.now():
        return False
    return True

def valider_expl_dispo(nombre_exemplaires: int, exemplaires_disponibles: int) -> bool:
    if not isinstance(nombre_exemplaires, int) or not isinstance(exemplaires_disponibles, int):
        return False
    if nombre_exemplaires < 0 or exemplaires_disponibles < 0:
        return False
    if exemplaires_disponibles > nombre_exemplaires:
        return False
    return True

def generer_id_exemplaire() -> str:
    return str(uuid.uuid4())

def valider_statut(statut: str) -> bool:
    statuts_valides = ["disponible", "emprunte", "perdu", "endommage", "reserve"]
    return statut in statuts_valides

def valider_compteur_emprunts(compteur: int) -> bool:
    return isinstance(compteur, int) and compteur >= 0

def valider_liste_chaines(liste: Optional[list]) -> bool:
    if liste is None:
        return True
    if not isinstance(liste, list):
        return False
    for item in liste:
        if not isinstance(item, str):
            return False
    return True

def est_entier(valeur) -> bool:
    return isinstance(valeur, int)

def est_chaine(valeur) -> bool:
    return isinstance(valeur, str)

def est_flottant(valeur) -> bool:
    return isinstance(valeur, float)

def valider_exemplaire(exemplaire) -> bool:
    required_attrs = ['id_exemplaire', 'code_barre', 'etat', 'localisation', 'statut', 'date_acquisition']
    for attr in required_attrs:
        if not hasattr(exemplaire, attr):
            return False
    return True

def valider_livre(livre) -> bool:
    required_attrs = ['isbn', 'titre', 'auteur', 'editeur', 'annee_publication', 'categorie', 'mots_cles', 'exemplaires', 'nombre_exemplaires', 'exemplaires_disponibles', 'statut', 'compteur_emprunts']
    for attr in required_attrs:
        if not hasattr(livre, attr):
            return False
    return True

def valider_code_barre(code_barre: str) -> bool:
    return nettoyer_chaine(code_barre) is not None and len(code_barre) == 5


# ------------------------- Clean user information -------------------------


def valider_email(email: str) -> bool:
    """
    Vérifie si un email est valide.
    - doit contenir un @
    - nom de domaine valide
    """
    if not isinstance(email, str) or not email.strip():
        return False
    
    email = email.strip()
    
    # Regex simple et robuste
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))


def valider_telephone(telephone: str) -> bool:
    """
    Vérifie si un numéro de téléphone est valide.
    - uniquement chiffres
    - longueur 8 à 12 chiffres
    - optionnel : peut commencer par 0 ou 00229 (Bénin)
    """
    if not isinstance(telephone, str) or not telephone.strip():
        return False

    tel = telephone.strip()

    # Supprimer les espaces et tirets
    tel = tel.replace(" ", "").replace("-", "")

    # Vérifier format
    if not tel.isdigit():
        return False

    # Vérifier longueur
    if len(tel) < 8 or len(tel) > 12:
        return False

    return True
