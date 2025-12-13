"""Modèles de données pour les épisodes NEW TEMPS X."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class Reference(BaseModel):
    """Représente une référence/lien vers une source web."""
    title: str = Field(..., description="Titre de la référence")
    url: str = Field(..., description="URL de la référence")
    description: Optional[str] = Field(None, description="Description optionnelle de la référence")


class Act(BaseModel):
    """Représente un acte narratif."""
    title: str = Field(..., description="Titre de l'acte")
    content: str = Field(..., description="Contenu narratif de l'acte")
    narrator: str = Field(
        default="narrator_1",
        description="Narrateur qui lit cet acte (narrator_1 ou narrator_2)"
    )
    references: List[Reference] = Field(
        default_factory=list,
        description="Liste des références/liens vers des sources web pertinentes"
    )
    image_prompts: List[str] = Field(
        default_factory=list,
        description="Liste des prompts DALL-E pour générer des images illustrant cet acte"
    )


class TwilightZoneStory(BaseModel):
    """Représente une histoire complète style Twilight Zone."""
    title: str = Field(..., description="Titre de l'histoire")
    story: str = Field(..., description="Histoire complète en plusieurs paragraphes")
    theme: str = Field(..., description="Thème principal exploré")
    image_prompts: List[str] = Field(
        default_factory=list,
        description="Liste des prompts DALL-E pour générer des images illustrant cette histoire"
    )


class Episode(BaseModel):
    """Représente un épisode complet NEW TEMPS X."""
    episode_title: str = Field(..., description="Titre de l'épisode")
    scenario_input: str = Field(..., description="Scénario d'entrée original")
    narrative_arc: str = Field(..., description="Arc narratif défini par le NarrativeConductor")
    acts: Dict[str, Act] = Field(
        ...,
        description="Les 7 actes de l'épisode (acte_1 à acte_7)"
    )
    twilight_zone_story: Optional[TwilightZoneStory] = Field(
        None,
        description="Histoire bonus style Twilight Zone (optionnelle)"
    )

    def get_act(self, act_number: int) -> Act:
        """Récupère un acte par son numéro (1-7)."""
        return self.acts[f"acte_{act_number}"]

    def has_all_acts(self) -> bool:
        """Vérifie que tous les 7 actes sont présents."""
        return len(self.acts) == 7 and all(
            f"acte_{i}" in self.acts for i in range(1, 8)
        )

