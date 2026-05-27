import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field

TASK_TYPE = "TASK"
TOOL_TYPE = "TOOL"
FEEDBACK_TYPE = "FEEDBACK"


class ActionRecord(BaseModel):
    action_type: str = Field(description="Type of the action")
    action_name: str = Field(description="Name of the action")
    action_desc: Dict[str, Any] = Field(
        default_factory=dict, description="Description of the action"
    )


class Tracer:

    def __init__(
        self, trj_path="./trjectories.txt", exp_path="./experiences.txt"
    ) -> None:
        self._trjectories = []
        self._experiences = []
        self._trjectories_path = trj_path
        self._experiences_path = exp_path
        with open(self._trjectories_path, "a", encoding="utf-8") as f:
            pass
        with open(self._experiences_path, "a", encoding="utf-8") as f:
            pass

    def add_trjectory(self, action: ActionRecord) -> None:
        self._trjectories.append(action)
        with open(self._trjectories_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(self._trjectories[-1].model_dump(), ensure_ascii=False)
                + "\n"
            )

    def get_trjectory(self) -> List[ActionRecord]:
        with open(self._trjectories_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self._trjectories = [json.loads(line) for line in lines]
            self._trjectories = [
                ActionRecord.model_validate(msg) for msg in self._trjectories
            ]
        return self._trjectories

    def add_experience(self, experience: str) -> None:
        self._experiences.append(experience)
        with open(self._experiences_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps({"experience": self._experiences[-1]}, ensure_ascii=False)
                + "\n"
            )

    def get_experience(self) -> List[str]:
        with open(self._experiences_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self._experiences = [json.loads(line)["experience"] for line in lines]
        return self._experiences

    def __len__(self):
        return len(self._trjectories)


if __name__ == "__main__":
    tracer = Tracer()
    tracer.add_trjectory(
        ActionRecord(
            action_type=TASK_TYPE,
            action_name="task1",
            action_desc={"desc": "this is a task"},
        )
    )
    tracer.add_trjectory(
        ActionRecord(
            action_type=TOOL_TYPE,
            action_name="tool1",
            action_desc={"desc": "this is a tool"},
        )
    )
    print(tracer.get_trjectory())
