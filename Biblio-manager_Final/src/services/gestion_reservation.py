"""Gestion des réservations.

Ce service gère la création, l'annulation, la notification et la
confirmation des réservations. Il persiste les réservations et les
files d'attente dans `data/reservations.json` et écrit des
notifications dans `data/notifications.txt`.

Le service dépend optionnellement des gestionnaires suivants :
- `gestion_livre` : pour vérifier la disponibilité des livres
- `gestion_emprunt` : pour créer l'emprunt lors de la confirmation
- `gestion_user` : pour valider l'existence des utilisateurs
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime

from models.reservation import Reservation
from services.journal import enregistrer_action

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DATA_FILE = os.path.join(DATA_DIR, 'reservations.json')
NOTIF_FILE = os.path.join(DATA_DIR, 'notifications.txt')


class GestionReservation:
    """Service pour gérer les réservations et files d'attente."""

    def __init__(self, gestion_livre=None, gestion_emprunt=None, gestion_user=None):
        """Initialise le gestionnaire de réservations.

        Charge les réservations persistées et prépare les structures en
        mémoire pour les opérations ultérieures.
        """
        self._gestion_livre = gestion_livre
        self._gestion_emprunt = gestion_emprunt
        self._gestion_user = gestion_user
        self._reservations: Dict[str, Reservation] = {}
        self._files: Dict[str, List[str]] = {}
        self.__charger()

    def __charger(self) -> None:
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erreur de chargement de {DATA_FILE}: {e}")
            return

        for d in data.get('reservations', []):
            try:
                r = Reservation.from_dict(d)
                self._reservations[r.id] = r
            except Exception as e:
                print(f"Impossible de charger la réservation: {e}")
                continue

        self._files = data.get('files', {}) or {}

    def sauvegarder(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {
            'reservations': [r.data_format() for r in self._reservations.values()],
            'files': self._files,
        }
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur de sauvegarde: {e}")

    def recharger(self) -> None:
        self._reservations.clear()
        self._files.clear()
        self.__charger()

    def _ajouter_a_file(self, isbn: str, id_reservation: str) -> None:
        self._files.setdefault(isbn, []).append(id_reservation)
        enregistrer_action(
            acteur="SYSTEM",
            action="AJOUT_FILE_RESERVATION",
            cible=isbn,
            details=f"Ajout de la réservation {id_reservation} à la file pour le livre {isbn}"  
        )

    def _retirer_de_file(self, isbn: str, id_reservation: str) -> None:
        if isbn in self._files and id_reservation in self._files[isbn]:
            self._files[isbn].remove(id_reservation)

    def _ecrire_notification(self, message: str) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(NOTIF_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")

    def reserver(self, matricule_user: str, isbn: str) -> Reservation:
        """Crée une réservation pour l'utilisateur sur l'ISBN donné.

        Validation effectuées : existence de l'utilisateur et du livre,
        disponibilité du livre (on ne peut pas réserver un livre déjà
        disponible) et absence de double-réservation par le même utilisateur.
        """
        # Vérification utilisateur
        if self._gestion_user:
            user = self._gestion_user.get_utilisateur_par_matricule(matricule_user)
            if not user:
                raise ValueError("Utilisateur introuvable")

        # Vérification livre
        if self._gestion_livre:
            livre = self._gestion_livre.get_livre(isbn)
            if not livre:
                raise ValueError("Livre introuvable")
            if livre.est_disponible():
                raise ValueError("Le livre est déjà disponible — pas besoin de réserver")

        # Vérification double réservation
        for r in self.lister_par_user(matricule_user):
            if r.isbn == isbn and r.statut in (Reservation.STATUT_EN_ATTENTE, Reservation.STATUT_NOTIFIE):
                raise ValueError("Vous avez déjà une réservation en cours pour ce livre")

        r = Reservation(matricule_user=matricule_user, isbn=isbn)
        self._reservations[r.id] = r
        self._ajouter_a_file(isbn, r.id)
        self.sauvegarder()

        enregistrer_action(
            acteur=matricule_user, 
            action="RESERVATION",
            cible=isbn,
            details=f"Création de la réservation {r.id} pour le livre {isbn}"
        )
        return r
    def annuler(self, id_reservation: str) -> bool:
        """Annule une réservation identifiée par `id_reservation`.

        Retourne `True` si l'annulation a réussi, `False` si la
        réservation est introuvable.
        """
        r = self._reservations.get(id_reservation)
        if not r:
            return False
        r.annuler()
        self._retirer_de_file(r.isbn, id_reservation)
        self.sauvegarder()

        enregistrer_action(
            acteur=r.matricule_user,
            action="ANNULATION_RESERVATION",
            cible=r.isbn,
            details=f"Annulation de la réservation {r.id} pour le livre {r.isbn}"

        )

        return True

    def traiter_file(self, isbn: str) -> Optional[str]:
        """Traite la file d'attente pour un ISBN et notifie le premier.

        Si le livre est disponible, la file est nettoyée des réservations
        invalides, le premier en attente est notifié (statut changé) et
        une notification est écrite dans `notifications.txt`.

        Retourne l'ID de la réservation notifiée, ou `None` si aucune
        notification n'a été envoyée.
        """
        if not self._gestion_livre:
            return None

        livre = self._gestion_livre.get_livre(isbn)
        if not livre or not livre.est_disponible():
            return None

        # Nettoyer la file
        file_propre = []
        for rid in self._files.get(isbn, []):
            r = self._reservations.get(rid)
            if r and r.statut == Reservation.STATUT_EN_ATTENTE:
                file_propre.append(rid)
        self._files[isbn] = file_propre

        if not file_propre:
            return None

        first_id = file_propre[0]
        r = self._reservations.get(first_id)
        if not r:
            return None

        try:
            r.notifier()
            message = f"L'utilisateur {r.matricule_user} peut emprunter le livre {r.isbn} (réservation {r.id})."
            print("Notification :", message)
            self._ecrire_notification(message)
            self.sauvegarder()

            enregistrer_action(
                acteur="SYSTEM",
                action="NOTIFICATION_RESERVATION",
                cible=r.isbn,
                details=f"Notification envoyée pour la réservation {r.id} à l'utilisateur {r.matricule_user}"
            )

            return r.id
        except ValueError:
            return None

    def confirmer(self, id_reservation: str) -> bool:
        """Confirme une réservation et crée un emprunt si possible.

        Si `gestion_emprunt` est disponible, un emprunt est créé pour
        l'utilisateur. La réservation est alors marquée confirmée et
        retirée de la file.
        """
        r = self._reservations.get(id_reservation)
        if not r or not r.est_confirmable():
            return False

        if self._gestion_emprunt:
            try:
                emprunt = self._gestion_emprunt.emprunter(r.matricule_user, r.isbn)
                r.confirmer()
                self._retirer_de_file(r.isbn, id_reservation)
                self.sauvegarder()
                print(f"Réservation {r.id} confirmée et emprunt créé (ID: {emprunt.id_emprunt})")
                enregistrer_action(
                    acteur=r.matricule_user,
                    action="CONFIRMATION_RESERVATION",
                    cible=r.isbn,
                    details=f"Confirmation de la réservation {r.id} et création de l'emprunt {emprunt.id_emprunt}" 
                )
                return True
            except Exception as e:
                print(f"Impossible de créer l'emprunt: {e}")
                enregistrer_action(
                    acteur=r.matricule_user,
                    action="ERREUR_CONFIRMATION_RESERVATION",
                    cible=r.isbn,
                    details=f"Erreur lors de la confirmation de la réservation {r.id} : {e}",
                    niveau="ERROR"
                )
                return False
        else:
            r.confirmer()
            self._retirer_de_file(r.isbn, id_reservation)
            self.sauvegarder()
            return True

    def get_reservation(self, id_reservation: str) -> Optional[Reservation]:
        return self._reservations.get(id_reservation)

    def lister_par_user(self, matricule_user: str) -> List[Reservation]:
        return [r for r in self._reservations.values() if r.matricule_user == matricule_user]

    def lister_toutes(self) -> List[Reservation]:
        return list(self._reservations.values())

    def lister_file_pour_isbn(self, isbn: str) -> List[Reservation]:
        ids = self._files.get(isbn, [])
        return [
            self._reservations[i] for i in ids
            if i in self._reservations and self._reservations[i].statut == Reservation.STATUT_EN_ATTENTE
        ]