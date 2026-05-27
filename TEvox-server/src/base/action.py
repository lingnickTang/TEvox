from typing import Literal, Any, Optional
from pydantic import BaseModel, Field
from src.base.tool import ToolCall


class Action(BaseModel):
    tool_call: ToolCall
    tool_output: Any = None
    tool_summary: str


class ContinueOrTerminate(BaseModel):
    reason: str = Field(
        description="Explain why the decision is prioritized for task completion."
    )
    decision: Literal["continue", "terminate"]

    def value(self):
        if self.decision == "continue":
            return True
        elif self.decision == "terminate":
            return False
        raise ValueError(f"Invalid decision: {self.decision}")


class ContinueOrBacktrack(BaseModel):
    reason: str = Field(
        description="Explain why the decision is prioritized for task completion."
    )
    decision: Literal["continue", "backtrack"]

    def value(self):
        if self.decision == "continue":
            return True
        elif self.decision == "backtrack":
            return False
        raise ValueError(f"Invalid decision: {self.decision}")


class BreakdownOrExecution(BaseModel):
    reason: str = Field(
        description="Explain why the decision is prioritized for task completion."
    )
    decision: Literal["breakdown", "execution"]

    def value(self):
        if self.decision == "breakdown":
            return True
        elif self.decision == "execution":
            return False
        raise ValueError(f"Invalid decision: {self.decision}")


class Evaluation(BaseModel):
    reason: Optional[str] = Field(
        default="",
        description="Explain why the decision is prioritized for task completion.",
    )
    decision: Literal["YES", "NO"]

    def value(self):
        if self.decision == "YES":
            return True
        elif self.decision == "NO":
            return False
        raise ValueError(f"Invalid decision: {self.decision}")
