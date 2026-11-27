"""Modèles de données pour les épisodes NEW TEMPS X."""

from pydantic import BaseModel, Field


class Reference(BaseModel):
    """Représente une référence/lien vers une source web."""

    title: str = Field(..., description="Titre de la référence")
    url: str = Field(..., description="URL de la référence")
    description: str | None = Field(None, description="Description optionnelle de la référence")


class Act(BaseModel):
    """Représente un acte narratif."""

    title: str = Field(..., description="Titre de l'acte")
    content: str = Field(..., description="Contenu narratif de l'acte")
    narrator: str = Field(default="narrator_1", description="Narrateur qui lit cet acte (narrator_1 ou narrator_2)")
    references: list[Reference] = Field(
        default_factory=list, description="Liste des références/liens vers des sources web pertinentes"
    )
    image_prompts: list[str] = Field(
        default_factory=list, description="Liste des prompts DALL-E pour générer des images illustrant cet acte"
    )


class TwilightZoneStory(BaseModel):
    """Représente une histoire complète style Twilight Zone."""

    title: str = Field(..., description="Titre de l'histoire")
    story: str = Field(..., description="Histoire complète en plusieurs paragraphes")
    theme: str = Field(..., description="Thème principal exploré")
    image_prompts: list[str] = Field(
        default_factory=list, description="Liste des prompts DALL-E pour générer des images illustrant cette histoire"
    )


class Episode(BaseModel):
    """Représente un épisode complet NEW TEMPS X."""

    episode_title: str = Field(..., description="Titre de l'épisode")
    scenario_input: str = Field(..., description="Scénario d'entrée original")
    narrative_arc: str = Field(..., description="Arc narratif défini par le NarrativeConductor")
    acts: dict[str, Act] = Field(..., description="Les 7 actes de l'épisode (acte_1 à acte_7)")
    twilight_zone_story: TwilightZoneStory | None = Field(
        None, description="Histoire bonus style Twilight Zone (optionnelle)"
    )

    def get_act(self, act_number: int) -> Act:
        """Récupère un acte par son numéro (1-7)."""
        return self.acts[f"acte_{act_number}"]

    def has_all_acts(self) -> bool:
        """Vérifie que tous les 7 actes sont présents."""
        return len(self.acts) == 7 and all(f"acte_{i}" in self.acts for i in range(1, 8))


# --- Schémas des sorties structurées demandées au SDK (output_format) -------


class NarrativeThemes(BaseModel):
    acte_1: str
    acte_2: str
    acte_3: str
    acte_4: str
    acte_5: str
    acte_6: str
    acte_7: str


class ArcOutput(BaseModel):
    episode_title: str
    narrative_arc: str
    themes: NarrativeThemes


class ActOutput(BaseModel):
    """Un acte tel que retourné par un Skill."""

    title: str
    content: str
    references: list[Reference] = Field(default_factory=list)
    image_prompts: list[str] = Field(default_factory=list)


class ActsOneToThreeOutput(BaseModel):
    acte_1: ActOutput
    acte_2: ActOutput
    acte_3: ActOutput


class ValidationOutput(BaseModel):
    validated: bool
    message: str = ""
    issues: list[str] = Field(default_factory=list)
