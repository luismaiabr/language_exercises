from typing import Annotated, List, Literal, Union
from pydantic import BaseModel, Field

# ==========================================
# EXERCISE CONTENT SCHEMAS (from base.md)
# ==========================================

class ChoiceOption(BaseModel):
    text: str = Field(..., description="The option text displayed to the user.")
    is_correct: bool = Field(..., description="True if this is the right answer.")
    explanation: str = Field(
        ...,
        description="Pre-calculated explanation of why this specific option is correct or why it is wrong and what the right rule is."
    )

class MultipleChoiceExercise(BaseModel):
    exercise_type: Literal["multiple_choice"] = "multiple_choice"
    question: str = Field(..., description="The German question or fill-in-the-blank prompt.")
    options: List[ChoiceOption] = Field(
        ...,
        min_length=2,
        description="Pre-calculated options with instantaneous feedback."
    )

class WrittenExercise(BaseModel):
    exercise_type: Literal["written"] = "written"
    question: str = Field(
        ...,
        description="The open prompt for the user (e.g., 'Translate into German: ...' or 'Rewrite in Perfekt: ...')."
    )
    # No expected_answer or correct_explanation stored here.
    # Evaluated dynamically by AI at the exact moment the user submits an answer.

Exercise = Annotated[
    Union[MultipleChoiceExercise, WrittenExercise],
    Field(discriminator="exercise_type")
]

class GeneratedLesson(BaseModel):
    """Structured output the backend requires from the AI model."""
    theory_summary: str = Field(..., description="Condensed summary of the grammar and vocabulary concepts.")
    exercises: List[Exercise] = Field(..., min_length=1, description="List of generated exercises.")
