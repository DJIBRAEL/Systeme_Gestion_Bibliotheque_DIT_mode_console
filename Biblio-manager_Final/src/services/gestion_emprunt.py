"""Service de gestion des emprunts.

Ce module contient `GestionEmprunt` qui permet d'enregistrer des
emprunts, de traiter les retours, de renouveler des prêts et
d'appliquer des suspensions aux utilisateurs en retard. Les emprunts
et les suspensions sont persistés dans `data/emprunts.json`.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING

from models.emprunt import Emprunt
from models.livre import Livre
from models.exemplaire import Exemplaire
from models.user import User
from models.enums import StatutLivre
from services.journal import enregistrer_action

if TYPE_CHECKING:
    from services.gestion_livre import GestionLivre
    from services.gestion_user import GestionUtilisateur
    from services.gestion_reservation import GestionReservation


def get_data_file(filename: str) -> str:
    """Retourne le chemin absolu du fichier de données `data/<filename>`.

    Gère le cas où `__file__` ne serait pas défini (par ex. lors de
    certains tests ou environnements atypiques).
    """
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    except NameError:
        # Cas où __file__ n'est pas défini 
        base_dir = os.path.abspath(os.getcwd())
    data_dir = os.path.join(base_dir, 'data')
    return os.path.join(data_dir, filename)


DATA_FILE = get_data_file('emprunts.json')


class EmpruntError(Exception):
    """Classe de base pour les erreurs liées aux emprunts."""
    pass


class ExemplaireIndisponible(EmpruntError):
    """Levée lorsqu'aucun exemplaire disponible n'a été trouvé."""
    pass


class LimiteAtteinte(EmpruntError):
    """Levée lorsque l'utilisateur a atteint sa limite d'emprunts."""
    pass


class EmpruntNonTrouve(EmpruntError):
    """Levée lorsqu'un emprunt demandé n'existe pas."""
    pass


class GestionEmprunt:
    """Service pour gérer les emprunts : emprunter, retourner, renouveler et appliquer les suspensions."""

    FACTEUR_SUSPENSION = 3  # multiplier le nombre de jours de retard pour la suspension

    def __init__(self, gestion_livre: 'GestionLivre', gestion_user: 'GestionUtilisateur', gestion_reservation: 'GestionReservation'):
        """Initialise les structures en mémoire et charge les emprunts persistés."""
        self._gestion_livre = gestion_livre
        self._gestion_user = gestion_user
        self._gestion_reservation = gestion_reservation
        self.__emprunts: Dict[str, Emprunt] = {}
        self.__suspensions: Dict[str, str] = {}
        self.__charger()

    # ---------------- PERSISTANCE ----------------

    def __nettoyer_suspensions(self):
        """Supprime les suspensions expirées."""
        now = datetime.now()
        self.__suspensions = {
            matricule: iso for matricule, iso in self.__suspensions.items()
            if datetime.fromisoformat(iso) > now
        }

    def __charger(self):
        if not os.path.exists(DATA_FILE):
            return

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erreur de chargement de {DATA_FILE}: {e}")
            return

        # Chargement des emprunts
        for d in data.get("emprunts", []):
            try:
                emprunt = Emprunt.from_dict(d)
                self.__emprunts[emprunt.id_emprunt] = emprunt
            except Exception as ex:
                id_emprunt = d.get('id_emprunt', 'inconnu')
                print(f"Impossible de charger l'emprunt {id_emprunt}: {ex}")
                continue

        # Chargement et nettoyage des suspensions
        raw_suspensions = data.get("suspensions", {}) or {}
        self.__suspensions = {k: v for k, v in raw_suspensions.items() if isinstance(v, str)}
        self.__nettoyer_suspensions()

    def recharger(self) -> None:
        """Relit le fichier des emprunts et remplace les données courantes."""
        self.__emprunts.clear()
        self.__suspensions.clear()
        self.__charger()

    def __sauvegarder(self):
        """Sauvegarde les emprunts et suspensions dans le fichier JSON."""
        self.__nettoyer_suspensions()
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "emprunts": [e.data_format() for e in self.__emprunts.values()],
                    "suspensions": self.__suspensions
                }, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des emprunts: {e}")
            enregistrer_action(
                acteur="SYSTEM",
                action="ERREUR_SAUVEGARDE_EMPRUNTS",
                cible="N/A",
                details=f"Erreur lors de la sauvegarde des emprunts : {e}",
                niveau="ERROR"
            )

    # ---------------- OUTILS INTERNES ----------------

    def __is_suspended(self, matricule: str) -> Optional[str]:
        """Vérifie si un utilisateur est suspendu. Nettoie automatiquement les suspensions expirées."""
        iso = self.__suspensions.get(matricule)
        if not iso:
            return None
        try:
            end = datetime.fromisoformat(iso)
        except ValueError:
            # Date invalide : nettoyer
            del self.__suspensions[matricule]
            self.__sauvegarder()
            enregistrer_action(
                acteur="SYSTEM",
                action="ERREUR_FORMAT_SUSPENSION",
                cible=matricule,
                details=f"Format de date invalide pour la suspension de l'utilisateur {matricule}",
                niveau="ERROR"
            )
            return None
        if datetime.now() < end:
            return iso
        # Suspension expirée : supprimer
        del self.__suspensions[matricule]
        self.__sauvegarder()
        return None

    def __trouver_exemplaire(self, livre: Livre, code_barre: Optional[str] = None) -> Optional[Exemplaire]:
        """Trouve un exemplaire disponible, soit par code-barres, soit le premier disponible."""
        if code_barre:
            for ex in livre.exemplaires:
                if ex.code_barre == code_barre:
                    return ex
            return None
        for ex in livre.exemplaires:
            if ex.statut == "disponible":
                return ex
        return None

    # ---------------- ACTIONS PRINCIPALES ----------------

    def emprunter(self, matricule: str, isbn: str, code_barre: Optional[str] = None, duree_jours: int = 14) -> Emprunt:
        """Enregistre un nouvel emprunt."""
        user = self._gestion_user.get_utilisateur_par_matricule(matricule)
        if not user:
            raise ValueError("Utilisateur introuvable")
        if self.__is_suspended(matricule):
            raise EmpruntError("Utilisateur suspendu")
        if not user.peut_emprunter():
            raise LimiteAtteinte("Limite d'emprunts atteinte ou statut invalide")

        livre = self._gestion_livre.get_livre(isbn)
        if not livre:
            raise ValueError("Livre introuvable")

        exemplaire = self.__trouver_exemplaire(livre, code_barre)
        if not exemplaire or exemplaire.statut != "disponible":
            raise ExemplaireIndisponible("Aucun exemplaire disponible")

        now = datetime.now()
        emprunt = Emprunt(
            matricule_user=matricule,
            isbn=isbn,
            code_barre=exemplaire.code_barre,
            date_emprunt=now,
            date_echeance=now + timedelta(days=duree_jours)
        )

        # Mise à jour des objets métier
        exemplaire.statut = "emprunte"
        livre.incrementer_compteur()
        livre.mettre_a_jour_statut()
        user.enregistrer_emprunt(isbn, exemplaire.code_barre)

        # Enregistrement dans le gestionnaire
        self.__emprunts[emprunt.id_emprunt] = emprunt
        self.__sauvegarder()

        enregistrer_action(
            acteur=matricule,
            action="emprunt",
            cible=isbn,
            details={"code_barre": exemplaire.code_barre}
        )
        return emprunt

    def retourner(self, id_emprunt: str) -> Emprunt:
        """Enregistre le retour d'un emprunt."""
        emprunt = self.__emprunts.get(id_emprunt)
        if not emprunt:
            raise EmpruntNonTrouve("Emprunt non trouvé")
        if emprunt.date_retour:
            return emprunt

        emprunt.retourner()

        # Mise à jour de l'exemplaire
        livre = self._gestion_livre.get_livre(emprunt.isbn)
        if livre:
            for ex in livre.exemplaires:
                if ex.code_barre == emprunt.code_barre:
                    ex.statut = StatutLivre.DISPONIBLE
                    break
            livre.mettre_a_jour_statut()
        else:
            print(f"Avertissement : livre non trouvé lors du retour (ISBN: {emprunt.isbn})")

        # Mise à jour de l'utilisateur
        user = self._gestion_user.get_utilisateur_par_matricule(emprunt.matricule_user)
        if user:
            user.enregistrer_retour(emprunt.isbn, emprunt.code_barre)
        else:
            print(f"Avertissement : utilisateur non trouvé lors du retour (matricule: {emprunt.matricule_user})")

        # Application de la suspension si en retard
        if emprunt.statut == "en_retard":
            # Calculer les jours de retard réels
            jours_retard = (emprunt.date_retour - emprunt.date_echeance).days
            if jours_retard <= 0:
                jours_retard = 1  # sécurité minimale            
            jours_suspension = jours_retard * self.FACTEUR_SUSPENSION

            suspend_until = datetime.now() + timedelta(days=jours_suspension)
            self.__suspensions[emprunt.matricule_user] = suspend_until.isoformat()
        
        if self._gestion_reservation: # Notification dans la file d'attente 
            self._gestion_reservation.traiter_file(emprunt.isbn)

        self.__sauvegarder()



        return emprunt

    def renouveler(self, id_emprunt: str, jours: int = 7) -> bool:
        """Renouvelle un emprunt si possible."""
        emprunt = self.__emprunts.get(id_emprunt)
        if not emprunt:
            raise EmpruntNonTrouve("Emprunt non trouvé")
            enregistrer_action(
                acteur="SYSTEM",
                action="ERREUR_RENOUVELLEMENT",
                cible=id_emprunt,
                details="Erreur lors du renouvellement de l'emprunt"
            )
        result = emprunt.renouveler(jours)
        if result:
            self.__sauvegarder()
        return result

    # ---------------- REQUÊTES ----------------

    def get_emprunt(self, id_emprunt: str) -> Optional[Emprunt]:
        return self.__emprunts.get(id_emprunt)

    def lister_par_user(self, matricule: str) -> List[Emprunt]:
        return [e for e in self.__emprunts.values() if e.matricule_user == matricule]
    
    def lister_emprunts_en_cours_par_user(self, matricule: str) -> List[Emprunt]:
        return [
            e for e in self.__emprunts.values()
            if e.matricule_user == matricule and e.date_retour is None
        ]

    def lister_en_cours(self) -> List[Emprunt]:
        return [e for e in self.__emprunts.values() if not e.date_retour]

    def lister_en_retard(self) -> List[Emprunt]:
        now = datetime.now()
        return [e for e in self.lister_en_cours() if e.date_echeance < now]

    def appliquer_penalites(self) -> None:
        """Parcourt les emprunts en cours et applique des suspensions.

        Pour chaque emprunt en retard, calcule la durée de suspension
        en multipliant les jours de retard par `FACTEUR_SUSPENSION` et
        enregistre la suspension dans la table interne.
        """
        now = datetime.now()
        for emprunt in self.lister_en_cours():
            if emprunt.date_echeance < now:
                jours_retard = (now - emprunt.date_echeance).days
                if jours_retard > 0:
                    jours_suspension = jours_retard * self.FACTEUR_SUSPENSION
                    suspend_until = now + timedelta(days=jours_suspension)
                    self.__suspensions[emprunt.matricule_user] = suspend_until.isoformat()

        self.__sauvegarder()

        enregistrer_action(
            acteur="SYSTEM",
            action="APPLIQUER_PENALTES",
            cible="N/A",
            details="Pénalités appliquées pour les emprunts en retard"

        )
        
    # ---------------- UTILITAIRES POUR L'INTERFACE ----------------

    def lister_tous(self) -> List[Emprunt]:
        """Retourne tous les emprunts (y compris ceux déjà retournés)."""
        return list(self.__emprunts.values())

    def lister_suspensions(self) -> Dict[str, str]:
        """Retourne une copie des suspensions actives."""
        self.__nettoyer_suspensions()
        return dict(self.__suspensions)