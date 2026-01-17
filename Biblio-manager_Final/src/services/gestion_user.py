"""Service de gestion des utilisateurs.

Fournit les opérations CRUD basiques sur les utilisateurs, la
persistance dans `data/users.json` ainsi que quelques utilitaires
affichage pour la CLI.
"""

from typing import List, Optional
from models.user import User    
from models.enums import TypeUtilisateur
import os
import json
import shutil
from services.journal import enregistrer_action

# Chemins
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DATA_FILE = os.path.join(DATA_DIR, 'users.json')


class GestionUtilisateur:
    def __init__(self):
        self._utilisateurs: List[User] = []
        self.__charger()

    def __charger(self) -> None:
        """Charge les utilisateurs depuis le fichier JSON si présent.

        Les erreurs de parsing sont affichées mais n'empêchent pas
        l'exécution du programme.
        """
        if not os.path.exists(DATA_FILE):
            return

        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Fichier {DATA_FILE} corrompu : {e}")
            return
        except Exception as e:
            print(f"Erreur de lecture du fichier {DATA_FILE} : {e}")
            return

        for d in data:
            try:
                # --- Gestion de type_utilisateur (ancien format = liste, nouveau = chaîne) ---
                type_val = d.get('type_utilisateur', 'ETUDIANT')
                type_enum = TypeUtilisateur.ETUDIANT  # valeur par défaut

                if isinstance(type_val, list):
                    # Ancien format : ["Etudiant", 3] → on regarde le premier élément
                    label = type_val[0] if len(type_val) > 0 else "Etudiant"
                    # Mapper le label vers l'enum
                    if label == "Etudiant":
                        type_enum = TypeUtilisateur.ETUDIANT
                    elif label == "Enseignant":
                        type_enum = TypeUtilisateur.PROFESSEUR
                    elif label == "Personnel administratif":
                        type_enum = TypeUtilisateur.EXTERNE
                    else:
                        print(f" Label inconnu dans type_utilisateur : {label}")
                elif isinstance(type_val, str):
                    # Nouveau format : "ETUDIANT"
                    try:
                        type_enum = TypeUtilisateur[type_val]
                    except KeyError:
                        print(f" Type utilisateur inconnu : {type_val}")
                # sinon, garde ETUDIANT par défaut

                # Création de l'utilisateur
                u = User(
                    nom=d.get('nom', ''),
                    prenom=d.get('prenom', ''),
                    email=d.get('email', ''),
                    telephone=d.get('telephone', ''),
                    type_utilisateur=type_enum
                )

                u.restaurer_etat(d)
                self._utilisateurs.append(u)

            except Exception as e:
                email_debug = d.get('email', 'inconnu')
                print(f"Impossible de charger l'utilisateur (email: {email_debug}) : {e}")
                continue

    def recharger(self) -> None:
        """Relit le fichier JSON et remplace la liste courante."""
        self._utilisateurs.clear()
        self.__charger()

    # ---------------- CREATION ----------------

    def creer_utilisateur(
        self,
        nom: str,
        prenom: str,
        email: str,
        telephone: str,
        type_utilisateur: TypeUtilisateur = TypeUtilisateur.ETUDIANT
    ) -> User:
        """Crée et enregistre un nouvel utilisateur.

        Vérifie que l'email n'est pas déjà utilisé et journalise la
        création. Retourne l'objet `User` créé.
        """
        if self.email_existe(email):
            raise ValueError("Un utilisateur avec cet email existe déjà")

        utilisateur = User(
            nom=nom,
            prenom=prenom,
            email=email,
            telephone=telephone,
            type_utilisateur=type_utilisateur
        )
        self._utilisateurs.append(utilisateur)
        self.sauvegarder()

        enregistrer_action(
            acteur="Admin",
            action="CREATION_UTILISATEUR",
            cible=utilisateur.matricule,
            details=f"Création de l'utilisateur {utilisateur.nom_complet()} - ({utilisateur.email}) - Type: {utilisateur.type_utilisateur.label}"

        )

        return utilisateur

    def supprimer_utilisateur(self, matricule: str) -> bool:
        """Supprime un utilisateur identifié par `matricule`.

        Retourne `True` si la suppression a réussi, `False` si l'utilisateur
        n'a pas été trouvé.
        """
        utilisateur = self.get_utilisateur_par_matricule(matricule)
        if utilisateur is None:
            return False
        self._utilisateurs.remove(utilisateur)
        self.sauvegarder()

        enregistrer_action(
            acteur="Admin",
            action="SUPPRESSION_UTILISATEUR",
            cible=utilisateur.matricule,
            details=f"Suppression de l'utilisateur {utilisateur.nom_complet()} - ({utilisateur.email}) - Type: {utilisateur.type_utilisateur.label}"
        )
        return True

    # ---------------- VERIFICATIONS ----------------

    def email_existe(self, email: str) -> bool:
        return any(u.email == email for u in self._utilisateurs)

    def matricule_existe(self, matricule: str) -> bool:
        return any(u.matricule == matricule for u in self._utilisateurs)

    # ---------------- RECHERCHE ----------------

    def get_utilisateur_par_matricule(self, matricule: str) -> Optional[User]:
        for utilisateur in self._utilisateurs:
            if utilisateur.matricule == matricule:
                return utilisateur
        return None

    def get_utilisateur_par_email(self, email: str) -> Optional[User]:
        for utilisateur in self._utilisateurs:
            if utilisateur.email == email:
                return utilisateur
        return None

    # ---------------- ACTIONS ----------------

    def desactiver_utilisateur(self, matricule: str) -> bool:
        utilisateur = self.get_utilisateur_par_matricule(matricule)
        if utilisateur is None:
            return False
        utilisateur.definir_statut("inactif")  
        self.sauvegarder()

        enregistrer_action(
            acteur="Admin",
            action="DESACTIVATION_UTILISATEUR",
            cible=utilisateur.matricule,
            details=f"Désactivation de l'utilisateur {utilisateur.nom_complet()} - ({utilisateur.email}) - Type: {utilisateur.type_utilisateur.label}"
        )

        return True

    def activer_utilisateur(self, matricule: str) -> bool:
        utilisateur = self.get_utilisateur_par_matricule(matricule)
        if utilisateur is None:
            return False
        utilisateur.definir_statut("actif")    # méthode publique
        self.sauvegarder()

        enregistrer_action(
            acteur="Admin",
            action="ACTIVATION_UTILISATEUR",
            cible=utilisateur.matricule,
            details=f"Activation de l'utilisateur {utilisateur.nom_complet()} - ({utilisateur.email}) - Type: {utilisateur.type_utilisateur.label}"
        )
        return True

    # ---------------- LISTE & EXPORT ----------------

    def lister_utilisateurs(self):
        """Affiche la liste des utilisateurs au format tabulaire pour la CLI.

        La méthode imprime directement sur stdout — elle est conçue pour
        l'usage interactif via `main.py`.
        """
        if not self._utilisateurs:
            print("Aucun utilisateur enregistré.")
            return

        print(f"{'Matricule':<12} | {'Nom Complet':<20} | {'Email':<25} | {'Statut':<10} | {'Type':<10}")
        print("-" * 85)
        for u in self._utilisateurs:
            print(f"{u.matricule:<12} | {u.nom_complet():<20} | {u.email:<25} | {u.statut:<10} | {u.type_utilisateur.label:<10}")

    def data_format(self) -> List[dict]:
        return [u.data_format() for u in self._utilisateurs]
    
    def sauvegarder(self) -> None:
        """Persiste la liste d'utilisateurs sur disque de manière sûre.

        Écrit d'abord dans un fichier temporaire puis déplace le fichier
        pour éviter la corruption en cas d'erreur d'écriture.
        """
        os.makedirs(DATA_DIR, exist_ok=True)
        temp_file = DATA_FILE + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(
                    [u.data_format() for u in self._utilisateurs],
                    f,
                    indent=4,
                    ensure_ascii=False
                )
            shutil.move(temp_file, DATA_FILE)
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            print(f"Erreur lors de la sauvegarde : {e}")