from enum import Enum

class TypeUtilisateur(Enum):
    ETUDIANT = ("Etudiant", 3)
    PROFESSEUR = ("Enseignant", 10)
    EXTERNE = ("Personnel administratif", 5)

    def __init__(self, label: str, limite_emprunt: int):
        self.label = label
        self.limite_emprunt = limite_emprunt

    def __str__(self):
        return self.label


class StatutLivre(Enum):
    DISPONIBLE = "disponible"
    EMPRUNTE = "emprunte"
    RESERVE = "reserve"
    PERDU = "perdu"
    ENDOMMAGE = "endommage"
    INDISPONIBLE = "indisponible"

    @property
    def label(self) -> str:
        """Retourne une version lisible pour l'utilisateur."""
        labels = {
            "disponible": "Disponible",
            "emprunte": "Emprunté",
            "reserve": "Réservé",
            "perdu": "Perdu",
            "endommage": "Endommagé",
            "indisponible": "Indisponible"
        }
        return labels.get(self.value, self.value.capitalize())

    def __str__(self):
        return self.label


class CategorieLivre(Enum):
    SCIENCE = "Science"
    LITTERATURE = "Littérature"
    INFORMATIQUE = "Informatique"
    TECHNOLOGIE = "Technologie"
    IA = "Intelligence Artificielle"
    AUTRE = "Autre"

    @property
    def label(self) -> str:
        return self.value

    def __str__(self):
        return self.value