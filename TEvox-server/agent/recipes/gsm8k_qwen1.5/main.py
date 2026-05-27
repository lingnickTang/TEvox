from agent.dataset.gsm8k import get_gsm8k_prompts
from agent.reward.r1_reward import accuracy_reward, format_reward, tag_count_reward
from agent.openr1.grpo import GRPO


if __name__ == "__main__":
    data_loader = get_gsm8k_prompts()
    reward_funcs = [accuracy_reward, format_reward, tag_count_reward]
    GRPO(data_loader, reward_funcs)
