from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class StartScenarioSchema(BaseModel):
    scenario_key: str  # built-in SBL_SCENARIOS key, or "custom:<id>"


class ScenarioTurnSchema(BaseModel):
    message: str = Field(default="", max_length=4000)


class CustomScenarioSchema(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    category: str  # Work | Social | Travel | Daily Life
    persona: str = Field(min_length=1, max_length=120)
    intent: str = Field(min_length=10, max_length=300)  # shown on the learner's pre-scenario screen
    system_prompt: str = Field(min_length=10)
    opening_line: Optional[str] = None
    target_vocab: List[str]
    goal_type: str = "roleplay"  # roleplay | negotiation
    safety_mode: bool = False  # breaks character on a medical-emergency phrase
    corporate_tone: bool = True

    @field_validator("target_vocab")
    @classmethod
    def min_three_words(cls, v: List[str]) -> List[str]:
        cleaned = [w.strip() for w in v if w.strip()]
        if len(cleaned) < 3:
            raise ValueError("At least 3 target vocabulary words are required.")
        return cleaned

    @field_validator("goal_type")
    @classmethod
    def valid_goal_type(cls, v: str) -> str:
        if v not in ("roleplay", "negotiation"):
            raise ValueError('goal_type must be "roleplay" or "negotiation"')
        return v


class ScenarioPreviewTurnSchema(BaseModel):
    role: str
    content: str


class ScenarioPreviewSchema(BaseModel):
    """SBL-US-06 E-01 sandbox tester: try a scenario's prompt against a persona
    before publishing it, with no DB row and no learner-facing side effects."""

    persona: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=10)
    opening_line: Optional[str] = None
    target_vocab: List[str] = Field(default_factory=list)
    goal_type: str = "roleplay"
    safety_mode: bool = False
    corporate_tone: bool = True
    turns: List[ScenarioPreviewTurnSchema] = Field(default_factory=list)
    message: Optional[str] = None  # omit to just fetch the opening line
