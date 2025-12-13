"""Validateur pour les épisodes NEW TEMPS X."""

from typing import Tuple
from .models import Episode


class NarrativeValidator:
    """Valide la cohérence narrative d'un épisode."""
    
    def validate_structure(self, episode: Episode) -> Tuple[bool, str]:
        """Valide la structure de base de l'épisode.
        
        Returns:
            (is_valid, message)
        """
        if not episode.has_all_acts():
            missing = []
            for i in range(1, 8):
                if f"acte_{i}" not in episode.acts:
                    missing.append(f"acte_{i}")
            return False, f"Actes manquants: {', '.join(missing)}"
        
        # Vérifier que chaque acte a un titre et du contenu
        for act_num, act in episode.acts.items():
            if not act.title or not act.title.strip():
                return False, f"{act_num}: titre manquant"
            if not act.content or not act.content.strip():
                return False, f"{act_num}: contenu manquant"
        
        return True, "Structure valide"
    
    def validate_episode(self, episode: Episode) -> Tuple[bool, str]:
        """Valide un épisode complet.
        
        Returns:
            (is_valid, message)
        """
        # Validation structurelle
        is_valid, message = self.validate_structure(episode)
        if not is_valid:
            return False, message
        
        # La validation narrative complète est faite par le Skill narrative-validator
        # via l'orchestrateur
        return True, "Épisode valide"

