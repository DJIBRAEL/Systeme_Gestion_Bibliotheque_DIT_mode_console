from datetime import datetime
from typing import Optional, Dict, Any
from utils.generateur import generer_id_unique


class Reservation:
    """Représente une réservation d'un utilisateur pour un ISBN.

    Statuts possibles:
      - en_attente: dans la file d'attente
      - notifie: l'utilisateur a été notifié qu'un exemplaire est disponible
      - confirme: l'utilisateur a confirmé la réservation (prêt à emprunter)
      - annule: la réservation a été annulée
    """

    # Constantes pour les statuts
    STATUT_EN_ATTENTE = "en_attente"
    STATUT_NOTIFIE = "notifie"
    STATUT_CONFIRME = "confirme"
    STATUT_ANNULE = "annule"

    STATUTS_VALIDES = {STATUT_EN_ATTENTE, STATUT_NOTIFIE, STATUT_CONFIRME, STATUT_ANNULE}

    def __init__(
        self,
        matricule_user: str,
        isbn: str,
        date_reservation: Optional[datetime] = None,
        statut: str = "en_attente",
        id_reservation: Optional[str] = None,
    ):
        if not matricule_user:
            raise ValueError("Le matricule utilisateur est requis")
        if not isbn:
            raise ValueError("L'ISBN est requis")
        if statut not in self.STATUTS_VALIDES:
            raise ValueError(f"Statut invalide : {statut}")

        self.__id = id_reservation or generer_id_unique("RES")
        self.__matricule_user = matricule_user
        self.__isbn = isbn
        self.__date_reservation = date_reservation or datetime.now()
        self.__statut = statut

    # --- Propriétés (lecture seule) ---

    @property
    def id(self) -> str:
        return self.__id

    @property
    def matricule_user(self) -> str:
        return self.__matricule_user

    @property
    def isbn(self) -> str:
        return self.__isbn

    @property
    def date_reservation(self) -> datetime:
        return self.__date_reservation

    @property
    def statut(self) -> str:
        return self.__statut

    # --- Changer d'état ---

    def notifier(self) -> None:
        """Passe la réservation à l'état 'notifie'."""
        if self.__statut != self.STATUT_EN_ATTENTE:
            raise ValueError("Seules les réservations 'en_attente' peuvent être notifiées")
        self.__statut = self.STATUT_NOTIFIE

    def confirmer(self) -> None:
        """Passe la réservation à l'état 'confirme'."""
        if self.__statut != self.STATUT_NOTIFIE:
            raise ValueError("Seules les réservations 'notifie' peuvent être confirmées")
        self.__statut = self.STATUT_CONFIRME

    def annuler(self) -> None:
        """Passe la réservation à l'état 'annule' (opération irréversible)."""
        if self.__statut == self.STATUT_ANNULE:
            return  # déjà annulé
        self.__statut = self.STATUT_ANNULE

    def est_notifiable(self) -> bool:
        """Indique si la réservation est éligible à une notification."""
        return self.__statut == self.STATUT_EN_ATTENTE

    def est_confirmable(self) -> bool:
        """Indique si la réservation peut être confirmée."""
        return self.__statut == self.STATUT_NOTIFIE

    # --- Sérialisation ---

    def data_format(self) -> Dict[str, Any]:
        """Exporte la réservation au format sérialisable (JSON)."""
        return {
            "id_reservation": self.id,
            "matricule_user": self.matricule_user,
            "isbn": self.isbn,
            "date_reservation": self.date_reservation.isoformat(),
            "statut": self.statut,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reservation":
        """Crée une Reservation à partir d'un dictionnaire (ex: JSON)."""
        date_str = data.get("date_reservation")
        date = None
        if date_str:
            try:
                date = datetime.fromisoformat(date_str)
            except ValueError:
                date = None

        statut = data.get("statut", cls.STATUT_EN_ATTENTE)
        if statut not in cls.STATUTS_VALIDES:
            statut = cls.STATUT_EN_ATTENTE

        return cls(
            matricule_user=data.get("matricule_user", ""),
            isbn=data.get("isbn", ""),
            date_reservation=date,
            statut=statut,
            id_reservation=data.get("id_reservation"),
        )

    # --- Affichage ---

    def __str__(self):
        return f"Reservation(id={self.id}, user={self.matricule_user}, isbn={self.isbn}, statut={self.statut})"

    def __repr__(self):
        return self.__str__()