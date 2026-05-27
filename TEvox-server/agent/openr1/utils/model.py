import os

from trl import ModelConfig, GRPOConfig
from transformers import AutoTokenizer, PreTrainedTokenizer
from transformers.trainer_utils import get_last_checkpoint


DEFAULT_CHAT_TEMPLATE = "{% for message in messages %}\n{% if message['role'] == 'user' %}\n{{ '<|user|>\n' + message['content'] + eos_token }}\n{% elif message['role'] == 'system' %}\n{{ '<|system|>\n' + message['content'] + eos_token }}\n{% elif message['role'] == 'assistant' %}\n{{ '<|assistant|>\n'  + message['content'] + eos_token }}\n{% endif %}\n{% if loop.last and add_generation_prompt %}\n{{ '<|assistant|>' }}\n{% endif %}\n{% endfor %}"


def get_tokenizer(
    model_args: ModelConfig,
    training_args: GRPOConfig,
    auto_set_chat_template: bool = True,
) -> PreTrainedTokenizer:
    tokenizer = AutoTokenizer.from_pretrained(
        model_args.model_name_or_path,
        revision=model_args.model_revision,
        trust_remote_code=model_args.trust_remote_code,
    )

    if tokenizer.get_chat_template() is None and auto_set_chat_template:
        tokenizer.chat_template = DEFAULT_CHAT_TEMPLATE

    return tokenizer


def get_checkpoint(training_args):
    if training_args.resume_from_checkpoint is not None:
        return training_args.resume_from_checkpoint

    if os.path.isdir(training_args.output_dir):
        return get_last_checkpoint(training_args.output_dir)

    return None
