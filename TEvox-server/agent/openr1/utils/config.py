from dataclasses import dataclass, field
from typing import Optional

import trl


@dataclass
class ScriptArguments(trl.ScriptArguments):
    wandb_entity: Optional[str] = field(
        default=None,
        metadata={"help": ("The entity to store runs under.")},
    )
    wandb_project: Optional[str] = field(
        default=None,
        metadata={"help": ("The project to store runs under.")},
    )
    wandb_run_id: Optional[str] = field(
        default=None,
        metadata={"help": ("The run ID to resume.")},
    )
    wandb_resume: Optional[str] = field(
        default="allow",
        metadata={"help": ("Whether to resume the run.")},
    )
