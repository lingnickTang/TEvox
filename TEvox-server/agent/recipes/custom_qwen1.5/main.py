from datasets import DatasetDict, Dataset

from agent.reward.feedback import (
    feedback_with_prompts_and_completions,
    feedback_with_real_number,
)
from agent.openr1.grpo import GRPO
from agent.openr1.custom_grpo_trainner import CustomGRPOTrainer

if __name__ == "__main__":
    data_loader = DatasetDict(
        {
            "train": Dataset.from_json("agent/dataset/custom.json"),
        }
    )

    GRPO(
        data_loader=data_loader,
        reward_funcs=[feedback_with_prompts_and_completions],
        # reward_funcs=[feedback_with_real_number],
        grpo_trainer=CustomGRPOTrainer,
    )
