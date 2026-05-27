import warnings
from typing import Any, Union, Optional
from unittest.mock import patch
from collections import defaultdict

import torch
from torch import nn
from datasets import Dataset, IterableDataset

from transformers import (
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    GenerationConfig,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    Trainer,
    TrainerCallback,
    is_wandb_available,
)
from transformers.integrations.deepspeed import is_deepspeed_zero3_enabled
from transformers.utils import is_peft_available
from accelerate.utils import (
    broadcast_object_list,
    gather,
    gather_object,
    is_peft_model,
    set_seed,
)

from trl.trainer.grpo_trainer import GRPOTrainer, RewardFunc
from trl.trainer.grpo_config import GRPOConfig
from trl.models import (
    create_reference_model,
    prepare_deepspeed,
    unwrap_model_for_generation,
)
from trl.trainer.callbacks import SyncRefModelCallback
from trl.trainer.utils import pad
from trl.import_utils import is_vllm_available
from trl.data_utils import (
    apply_chat_template,
    is_conversational,
    maybe_apply_chat_template,
)


if is_peft_available():
    from peft import PeftConfig, get_peft_model

if is_vllm_available():
    from vllm import LLM, SamplingParams

if is_wandb_available():
    import wandb

import logging

logger = logging.getLogger(__name__)


class CustomGRPOTrainer(GRPOTrainer):

    def __init__(
        self,
        model: Union[str, PreTrainedModel],
        reward_funcs: Union[RewardFunc, list[RewardFunc]],
        args: GRPOConfig = None,
        train_dataset: Optional[Union[Dataset, IterableDataset]] = None,
        eval_dataset: Optional[
            Union[Dataset, IterableDataset, dict[str, Union[Dataset, IterableDataset]]]
        ] = None,
        processing_class: Optional[PreTrainedTokenizerBase] = None,
        reward_processing_classes: Optional[
            Union[PreTrainedTokenizerBase, list[PreTrainedTokenizerBase]]
        ] = None,
        callbacks: Optional[list[TrainerCallback]] = None,
        optimizers: tuple[
            Optional[torch.optim.Optimizer], Optional[torch.optim.lr_scheduler.LambdaLR]
        ] = (None, None),
        peft_config: Optional["PeftConfig"] = None,
    ):
        # Args
        if args is None:
            model_name = model if isinstance(model, str) else model.config._name_or_path
            model_name = model_name.split("/")[-1]
            args = GRPOConfig(f"{model_name}-GRPO")

        # Models
        # Trained model
        model_init_kwargs = args.model_init_kwargs or {}
        if isinstance(model, str):
            model_id = model
            torch_dtype = model_init_kwargs.get("torch_dtype")
            if (
                isinstance(torch_dtype, torch.dtype)
                or torch_dtype == "auto"
                or torch_dtype is None
            ):
                pass  # torch_dtype is already a torch.dtype or "auto" or None
            elif isinstance(torch_dtype, str):  # it's a str, but not "auto"
                torch_dtype = getattr(torch, torch_dtype)
                model_init_kwargs["torch_dtype"] = torch_dtype
            else:
                raise ValueError(
                    "Invalid `torch_dtype` passed to `GRPOConfig`. Expected either 'auto' or a string representing "
                    f"a `torch.dtype` (e.g., 'float32'), but got {torch_dtype}."
                )
            # Disable caching if gradient checkpointing is enabled (not supported)
            model_init_kwargs["use_cache"] = (
                False
                if args.gradient_checkpointing
                else model_init_kwargs.get("use_cache")
            )
            model = AutoModelForCausalLM.from_pretrained(model, **model_init_kwargs)
        else:
            model_id = model.config._name_or_path
            if args.model_init_kwargs is not None:
                raise ValueError(
                    "You passed `model_init_kwargs` to the `GRPOConfig`, but your model is already instantiated. "
                    "This argument can only be used when the `model` argument is a string."
                )

        if peft_config is not None:
            model.enable_input_require_grads()  # Fix for PEFT, see https://github.com/huggingface/peft/issues/137
            model = get_peft_model(model, peft_config)

        # Reference model
        if is_deepspeed_zero3_enabled():
            self.ref_model = AutoModelForCausalLM.from_pretrained(
                model_id, **model_init_kwargs
            )
        elif not is_peft_model(model):
            # If PEFT configuration is not provided, create a reference model based on the initial model.
            self.ref_model = create_reference_model(model)
        else:
            # If PEFT is used, the reference model is not needed since the adapter can be disabled
            # to revert to the initial model.
            self.ref_model = None

        # Processing class
        if processing_class is None:
            processing_class = AutoTokenizer.from_pretrained(
                model.config._name_or_path, padding_side="left"
            )

        # Reward functions
        if not isinstance(reward_funcs, list):
            reward_funcs = [reward_funcs]
        for i, reward_func in enumerate(reward_funcs):
            if isinstance(reward_func, str):
                reward_funcs[i] = AutoModelForSequenceClassification.from_pretrained(
                    reward_func, num_labels=1, **model_init_kwargs
                )
        self.reward_funcs = reward_funcs

        # Reward weights
        if args.reward_weights is not None:
            if len(args.reward_weights) != len(reward_funcs):
                raise ValueError(
                    f"Number of reward weights ({len(args.reward_weights)}) must match number of reward "
                    f"functions ({len(reward_funcs)})"
                )
            self.reward_weights = torch.tensor(args.reward_weights, dtype=torch.float32)
        else:
            self.reward_weights = torch.ones(len(reward_funcs), dtype=torch.float32)

        # Reward processing class
        if reward_processing_classes is None:
            reward_processing_classes = [None] * len(reward_funcs)
        elif not isinstance(reward_processing_classes, list):
            reward_processing_classes = [reward_processing_classes]
        else:
            if len(reward_processing_classes) != len(reward_funcs):
                raise ValueError(
                    "The number of reward processing classes must match the number of reward functions."
                )

        for i, (reward_processing_class, reward_func) in enumerate(
            zip(reward_processing_classes, reward_funcs)
        ):
            if isinstance(reward_func, PreTrainedModel):
                if reward_processing_class is None:
                    reward_processing_class = AutoTokenizer.from_pretrained(
                        reward_func.config._name_or_path
                    )
                if reward_processing_class.pad_token_id is None:
                    reward_processing_class.pad_token = (
                        reward_processing_class.eos_token
                    )
                # The reward model computes the reward for the latest non-padded token in the input sequence.
                # So it's important to set the pad token ID to the padding token ID of the processing class.
                reward_func.config.pad_token_id = reward_processing_class.pad_token_id
                reward_processing_classes[i] = reward_processing_class
        self.reward_processing_classes = reward_processing_classes

        # Data collator
        def data_collator(features):  # No data collation is needed in GRPO
            return features

        # Training arguments
        self.max_prompt_length = args.max_prompt_length
        self.max_completion_length = (
            args.max_completion_length
        )  # = |o_i| in the GRPO paper
        self.num_generations = args.num_generations  # = G in the GRPO paper
        self.use_vllm = args.use_vllm

        self.beta = args.beta

        # The trainer estimates the number of FLOPs (floating-point operations) using the number of elements in the
        # input tensor associated with the key "input_ids". However, in GRPO, the sampled data does not include the
        # "input_ids" key. Instead, the available keys is "prompt". As a result, the trainer issues the warning:
        # "Could not estimate the number of tokens of the input, floating-point operations will not be computed." To
        # suppress this warning, we set the "estimate_tokens" key in the model's "warnings_issued" dictionary to True.
        # This acts as a flag to indicate that the warning has already been issued.
        model.warnings_issued["estimate_tokens"] = True

        # Initialize the metrics
        self._metrics = defaultdict(list)
        self.log_completions = args.log_completions

        # Initialize with the grandparent class
        Trainer.__init__(
            self,
            model=model,
            args=args,
            data_collator=data_collator,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=processing_class,
            callbacks=callbacks,
            optimizers=optimizers,
        )

        # Check if the per_device_train/eval_batch_size * num processes can be divided by the number of generations
        num_processes = self.accelerator.num_processes
        global_batch_size = args.per_device_train_batch_size * num_processes
        possible_values = [
            n_gen
            for n_gen in range(2, global_batch_size + 1)
            if (global_batch_size) % n_gen == 0
        ]
        if self.num_generations not in possible_values:
            raise ValueError(
                f"The global train batch size ({num_processes} x {args.per_device_train_batch_size}) must be evenly "
                f"divisible by the number of generations per prompt ({self.num_generations}). Given the current train "
                f"batch size, the valid values for the number of generations are: {possible_values}."
            )
        if self.args.eval_strategy != "no":
            global_batch_size = args.per_device_eval_batch_size * num_processes
            possible_values = [
                n_gen
                for n_gen in range(2, global_batch_size + 1)
                if (global_batch_size) % n_gen == 0
            ]
            if self.num_generations not in possible_values:
                raise ValueError(
                    f"The global eval batch size ({num_processes} x {args.per_device_eval_batch_size}) must be evenly "
                    f"divisible by the number of generations per prompt ({self.num_generations}). Given the current "
                    f"eval batch size, the valid values for the number of generations are: {possible_values}."
                )

        # Ensure each process receives a unique seed to prevent duplicate completions when generating with
        # transformers if num_generations exceeds per_device_train_batch_size. We could skip it if we use vLLM, but
        # it's safer to set it in all cases.
        set_seed(args.seed, device_specific=True)

        if self.use_vllm:
            if not is_vllm_available():
                raise ImportError(
                    "vLLM is not available and `use_vllm` is set to True. Please install vLLM with "
                    "`pip install vllm` to use it."
                )

            if self.accelerator.is_main_process:
                vllm_device = self.args.vllm_device
                if vllm_device == "auto":
                    if torch.cuda.device_count() == 1:
                        vllm_device = "cuda:0"  # particular case when training with onyl 1 GPU: share it
                    else:
                        vllm_device = f"cuda:{self.accelerator.num_processes}"  # take the next GPU idx
                # Check that the requested device is available
                if (
                    vllm_device.split(":")[0] == "cuda"
                    and int(vllm_device.split(":")[1]) >= torch.cuda.device_count()
                ):
                    raise ValueError(
                        f"The requested device for vllm ({vllm_device}) is not available. You are likely using vLLM "
                        "without restricting the number of GPUs for training. Set the `--num_processes` argument to a "
                        "value lower than the number of GPUs available on your machine—typically, reducing it by one "
                        f"is sufficient. In your case: `--num_processes {torch.cuda.device_count() - 1}`."
                    )
                # Check that the requested device is not also used for training
                if vllm_device in {
                    f"cuda:{idx}" for idx in range(self.accelerator.num_processes)
                }:
                    warnings.warn(
                        f"The requested device {vllm_device} is also being used for training. For higher throughput "
                        "and to avoid out-of-memory errors, it is recommended to use a dedicated device for vLLM. "
                        "If this is intentional, you may ignore this warning but should adjust "
                        "`vllm_gpu_memory_utilization` accordingly."
                    )
                # vLLM is not compatible with accelerate. So we need to patch it to make sure we can (1) place the vLLM
                # model on the desired device (world_size_patch) and (2) avoid a test that is not designed for our
                # setting (profiling_patch).
                world_size_patch = patch(
                    "torch.distributed.get_world_size", return_value=1
                )
                profiling_patch = patch(
                    "vllm.worker.worker.Worker._assert_memory_footprint_increased_during_profiling",
                    return_value=None,
                )
                with world_size_patch, profiling_patch:
                    self.llm = LLM(
                        model=model.name_or_path,
                        device=vllm_device,
                        gpu_memory_utilization=self.args.vllm_gpu_memory_utilization,
                        dtype=self.args.vllm_dtype,
                        # Automatic Prefix Caching caches the KV cache of existing queries, so that a new query can
                        # directly reuse the KV cache if it shares the same prefix with one of the existing queries.
                        # This is particularly useful here because we generate completions from the same prompts.
                        enable_prefix_caching=True,
                        max_model_len=self.args.vllm_max_model_len,
                    )
                self.sampling_params = SamplingParams(
                    temperature=args.temperature,
                    max_tokens=self.max_completion_length,
                )

            self._last_loaded_step = (
                0  # tag to avoid useless loading during grad accumulation
            )

            # When using vLLM, the main process is responsible for loading the model weights. This can cause process
            # desynchronization and seems to lead to DeepSpeed hanging during initialization. To prevent this, we
            # synchronize all processes after vLLM has been fully initialized.
            self.accelerator.wait_for_everyone()
        else:
            self.generation_config = GenerationConfig(
                max_new_tokens=self.max_completion_length,
                do_sample=True,
                temperature=args.temperature,
                pad_token_id=processing_class.pad_token_id,
            )

        # Gradient accumulation requires scaled loss. Normally, loss scaling in the parent class depends on whether the
        # model accepts loss-related kwargs. Since we compute our own loss, this check is irrelevant. We set
        # self.model_accepts_loss_kwargs to False to enable scaling.
        self.model_accepts_loss_kwargs = False

        # Add tags to the model
        self.model.add_model_tags(self._tag_names)

        if self.ref_model is not None:
            if self.is_deepspeed_enabled:
                self.ref_model = prepare_deepspeed(self.ref_model, self.accelerator)
            else:
                self.ref_model = self.accelerator.prepare_model(
                    self.ref_model, evaluation_mode=True
                )

        if args.sync_ref_model:
            self.add_callback(
                SyncRefModelCallback(
                    ref_model=self.ref_model, accelerator=self.accelerator
                )
            )

        for i, reward_func in enumerate(self.reward_funcs):
            if isinstance(reward_func, PreTrainedModel):
                self.reward_funcs[i] = self.accelerator.prepare_model(
                    reward_func, evaluation_mode=True
                )

    def _prepare_ref_per_token_logps(self, inputs: dict[str, Union[torch.Tensor, Any]]):
        device = self.accelerator.device
        (
            completion_ids,
            prompt_completion_ids,
            attention_mask,
        ) = (
            inputs["completion_ids"],
            torch.cat([inputs["prompt_ids"], inputs["completion_ids"]], dim=1),
            torch.cat([inputs["prompt_mask"], inputs["completion_mask"]], dim=1),
        )

        logits_to_keep = completion_ids.size(
            1
        )  # we only need to compute the logits for the completion tokens

        with torch.inference_mode():
            if self.ref_model is not None:
                ref_per_token_logps = self._get_per_token_logps(
                    self.ref_model,
                    prompt_completion_ids,
                    attention_mask,
                    logits_to_keep,
                )
            else:
                with self.accelerator.unwrap_model(self.model).disable_adapter():
                    ref_per_token_logps = self._get_per_token_logps(
                        self.model,
                        prompt_completion_ids,
                        attention_mask,
                        logits_to_keep,
                    )

        return ref_per_token_logps

    def _prepare_prompts_and_completions(
        self, inputs: dict[str, Union[torch.Tensor, Any]]
    ) -> dict[str, Union[torch.Tensor, Any]]:
        device = self.accelerator.device
        prompts = [x["prompt"] for x in inputs]
        prompts_text = [
            maybe_apply_chat_template(example, self.processing_class)["prompt"]
            for example in inputs
        ]
        prompt_inputs = self.processing_class(
            prompts_text,
            return_tensors="pt",
            padding=True,
            padding_side="left",
            add_special_tokens=False,
        )
        prompt_inputs = Trainer._prepare_inputs(self, prompt_inputs)
        prompt_ids, prompt_mask = (
            prompt_inputs["input_ids"],
            prompt_inputs["attention_mask"],
        )

        if self.max_prompt_length is not None:
            prompt_ids = prompt_ids[:, -self.max_prompt_length :]
            prompt_mask = prompt_mask[:, -self.max_prompt_length :]

        # Generate completions using either vLLM or regular generation
        if self.args.use_vllm:
            # First, have main process load weights if needed
            if self.state.global_step != self._last_loaded_step:
                self._move_model_to_vllm()
                self._last_loaded_step = self.state.global_step

            # Generate completions using vLLM: gather all prompts and use them in a single call in the main process
            all_prompts_text = gather_object(prompts_text)
            if self.accelerator.is_main_process:
                outputs = self.llm.generate(
                    all_prompts_text,
                    sampling_params=self.sampling_params,
                    use_tqdm=False,
                )
                completion_ids = [
                    out.token_ids
                    for completions in outputs
                    for out in completions.outputs
                ]
            else:
                completion_ids = [None] * len(all_prompts_text)
            # Broadcast the completions from the main process to all processes, ensuring each process receives its
            # corresponding slice.
            completion_ids = broadcast_object_list(completion_ids, from_process=0)
            process_slice = slice(
                self.accelerator.process_index * len(prompts),
                (self.accelerator.process_index + 1) * len(prompts),
            )
            completion_ids = completion_ids[process_slice]

            # Pad the completions, and concatenate them with the prompts
            completion_ids = [
                torch.tensor(ids, device=device) for ids in completion_ids
            ]
            completion_ids = pad(
                completion_ids, padding_value=self.processing_class.pad_token_id
            )
        else:
            # Regular generation path
            with unwrap_model_for_generation(
                self.model, self.accelerator
            ) as unwrapped_model:
                prompt_completion_ids = unwrapped_model.generate(
                    prompt_ids,
                    attention_mask=prompt_mask,
                    generation_config=self.generation_config,
                )

            # Compute prompt length and extract completion ids
            prompt_length = prompt_ids.size(1)
            prompt_ids = prompt_completion_ids[:, :prompt_length]
            completion_ids = prompt_completion_ids[:, prompt_length:]

        # Mask everything after the first EOS token
        is_eos = completion_ids == self.processing_class.eos_token_id
        eos_idx = torch.full(
            (is_eos.size(0),), is_eos.size(1), dtype=torch.long, device=device
        )
        eos_idx[is_eos.any(dim=1)] = is_eos.int().argmax(dim=1)[is_eos.any(dim=1)]
        sequence_indices = torch.arange(is_eos.size(1), device=device).expand(
            is_eos.size(0), -1
        )
        completion_mask = (sequence_indices <= eos_idx.unsqueeze(1)).int()

        # Decode the generated completions
        completions_text = self.processing_class.batch_decode(
            completion_ids, skip_special_tokens=True
        )
        if is_conversational(inputs[0]):
            completions = []
            for prompt, completion in zip(prompts, completions_text):
                bootstrap = (
                    prompt.pop()["content"] if prompt[-1]["role"] == "assistant" else ""
                )
                completions.append(
                    [{"role": "assistant", "content": bootstrap + completion}]
                )
        else:
            completions = completions_text

        return {
            "prompt_ids": prompt_ids,
            "prompt_mask": prompt_mask,
            "prompts": prompts,
            "prompts_text": prompts_text,
            "completion_ids": completion_ids,
            "completion_mask": completion_mask,
            "completions": completions,
            "completions_text": completions_text,
        }

    def _prepare_rewards(self, inputs: dict[str, Union[torch.Tensor, Any]]):
        device = self.accelerator.device
        (inputs, prompts, completions) = (
            inputs["inputs"],
            inputs["prompts"],
            inputs["completions"],
        )

        rewards_per_func = torch.zeros(
            len(prompts), len(self.reward_funcs), device=device
        )

        for i, reward_func in enumerate(self.reward_funcs):
            output_reward_func = reward_func(
                prompts=prompts, completions=completions, inputs=inputs
            )
            rewards = [x["reward"] for x in output_reward_func]
            rewards_per_func[:, i] = torch.tensor(
                rewards, dtype=torch.float32, device=device
            )

        return {
            "rewards": (
                rewards_per_func * self.reward_weights.to(device).unsqueeze(0)
            ).sum(dim=1),
            "feedbacks": [x["feedback"] for x in output_reward_func],
        }

    def _prepare_reflection_samples(
        self, inputs: dict[str, Union[torch.Tensor, Any]], recursive: bool = True
    ):
        prompts_and_completions = self._prepare_prompts_and_completions(inputs)
        rewards = self._prepare_rewards(
            {
                "inputs": inputs,
                "prompts": prompts_and_completions["prompts"],
                "completions": prompts_and_completions["completions"],
            }
        )

        new_inputs = []
        if recursive:
            for i, feedback in enumerate(rewards["feedbacks"]):
                # if feedback:
                new_input = inputs[i].copy()
                new_input["prompt"].extend(feedback)
                new_inputs.append(new_input)

        if new_inputs and recursive:
            return [
                {
                    "rewards": rewards["rewards"],
                    "feedbacks": rewards["feedbacks"],
                    **prompts_and_completions,
                }
            ] + self._prepare_reflection_samples(new_inputs, recursive=False)

        return [
            {
                "rewards": rewards["rewards"],
                "feedbacks": rewards["feedbacks"],
                **prompts_and_completions,
            }
        ]

    def _prepare_inputs(
        self, inputs: dict[str, Union[torch.Tensor, Any]]
    ) -> dict[str, Union[torch.Tensor, Any]]:
        res = self._prepare_reflection_samples(inputs)

        prompts = res[0]["prompts"] + res[0]["prompts"]

        prompt_ids = torch.cat([res[0]["prompt_ids"], res[0]["prompt_ids"]], dim=0)
        prompt_mask = torch.cat(
            [
                res[0]["prompt_mask"],
                res[0]["prompt_mask"],
            ],
            dim=0,
        )

        completion_ids = [item for i in range(2) for item in res[i]["completion_ids"]]
        completion_ids = pad(
            completion_ids, padding_value=self.processing_class.pad_token_id
        )

        completion_mask = [item for i in range(2) for item in res[i]["completion_mask"]]
        completion_mask = pad(completion_mask, padding_value=0)

        prompts_text = res[0]["prompts_text"] + res[0]["prompts_text"]
        completions_text = res[0]["completions_text"] + res[1]["completions_text"]

        rewards = torch.cat([res[0]["rewards"], res[1]["rewards"]], dim=0)
        feedbacks = res[0]["feedbacks"] + res[1]["feedbacks"]

        ref_per_token_logps = self._prepare_ref_per_token_logps(
            {
                "prompt_ids": prompt_ids,
                "prompt_mask": prompt_mask,
                "completion_ids": completion_ids,
                "completion_mask": completion_mask,
            }
        )

        # Gather the reward per function: this part is crucial, because the rewards are normalized per group and the
        # completions may be distributed across processes
        rewards = gather(rewards)

        mean_grouped_rewards = rewards.view(-1, self.num_generations * 2).mean(dim=1)
        std_grouped_rewards = rewards.view(-1, self.num_generations * 2).std(dim=1)

        # Normalize the rewards to compute the advantages
        mean_grouped_rewards = mean_grouped_rewards.repeat_interleave(
            self.num_generations * 2, dim=0
        )
        std_grouped_rewards = std_grouped_rewards.repeat_interleave(
            self.num_generations * 2, dim=0
        )
        advantages = (rewards - mean_grouped_rewards) / (std_grouped_rewards + 1e-4)

        # Slice to keep only the local part of the data
        process_slice = slice(
            self.accelerator.process_index * len(prompts),
            (self.accelerator.process_index + 1) * len(prompts),
        )
        advantages = advantages[process_slice]

        # Log metrics
        self._metrics["reward"].append(rewards.mean().item())
        self._metrics["reward_std"].append(std_grouped_rewards.mean().item())

        if (
            self.log_completions
            and self.state.global_step % self.args.logging_steps == 0
            and "wandb" in self.args.report_to
        ):
            import pandas as pd

            # For logging
            table = {
                "step": [str(self.state.global_step)] * len(rewards),
                "prompt": gather_object(prompts_text),
                "completion": gather_object(completions_text),
                "reward": rewards.tolist(),
                "feedback": gather_object(feedbacks),
            }
            df = pd.DataFrame(table)

            if wandb.run is not None and self.accelerator.is_main_process:
                wandb.log({"completions": wandb.Table(dataframe=df)})
                df.to_csv(f"completions_reflection_count_{self.state.global_step}.csv")

        return {
            "prompt_ids": prompt_ids,
            "prompt_mask": prompt_mask,
            "completion_ids": completion_ids,
            "completion_mask": completion_mask,
            "ref_per_token_logps": ref_per_token_logps,
            "advantages": advantages,
        }

    # def _prepare_inputs(
    #     self, inputs: dict[str, Union[torch.Tensor, Any]]
    # ) -> dict[str, Union[torch.Tensor, Any]]:
    #     device = self.accelerator.device
    #     prompts = [x["prompt"] for x in inputs]
    #     prompts_text = [
    #         maybe_apply_chat_template(example, self.processing_class)["prompt"]
    #         for example in inputs
    #     ]
    #     prompt_inputs = self.processing_class(
    #         prompts_text,
    #         return_tensors="pt",
    #         padding=True,
    #         padding_side="left",
    #         add_special_tokens=False,
    #     )
    #     prompt_inputs = Trainer._prepare_inputs(self, prompt_inputs)
    #     prompt_ids, prompt_mask = (
    #         prompt_inputs["input_ids"],
    #         prompt_inputs["attention_mask"],
    #     )

    #     if self.max_prompt_length is not None:
    #         prompt_ids = prompt_ids[:, -self.max_prompt_length :]
    #         prompt_mask = prompt_mask[:, -self.max_prompt_length :]

    #     # Generate completions using either vLLM or regular generation
    #     if self.args.use_vllm:
    #         # First, have main process load weights if needed
    #         if self.state.global_step != self._last_loaded_step:
    #             self._move_model_to_vllm()
    #             self._last_loaded_step = self.state.global_step

    #         # Generate completions using vLLM: gather all prompts and use them in a single call in the main process
    #         all_prompts_text = gather_object(prompts_text)
    #         if self.accelerator.is_main_process:
    #             outputs = self.llm.generate(
    #                 all_prompts_text,
    #                 sampling_params=self.sampling_params,
    #                 use_tqdm=False,
    #             )
    #             completion_ids = [
    #                 out.token_ids
    #                 for completions in outputs
    #                 for out in completions.outputs
    #             ]
    #         else:
    #             completion_ids = [None] * len(all_prompts_text)
    #         # Broadcast the completions from the main process to all processes, ensuring each process receives its
    #         # corresponding slice.
    #         completion_ids = broadcast_object_list(completion_ids, from_process=0)
    #         process_slice = slice(
    #             self.accelerator.process_index * len(prompts),
    #             (self.accelerator.process_index + 1) * len(prompts),
    #         )
    #         completion_ids = completion_ids[process_slice]

    #         # Pad the completions, and concatenate them with the prompts
    #         completion_ids = [
    #             torch.tensor(ids, device=device) for ids in completion_ids
    #         ]
    #         completion_ids = pad(
    #             completion_ids, padding_value=self.processing_class.pad_token_id
    #         )
    #         prompt_completion_ids = torch.cat([prompt_ids, completion_ids], dim=1)
    #     else:
    #         # Regular generation path
    #         with unwrap_model_for_generation(
    #             self.model, self.accelerator
    #         ) as unwrapped_model:
    #             prompt_completion_ids = unwrapped_model.generate(
    #                 prompt_ids,
    #                 attention_mask=prompt_mask,
    #                 generation_config=self.generation_config,
    #             )

    #         # Compute prompt length and extract completion ids
    #         prompt_length = prompt_ids.size(1)
    #         prompt_ids = prompt_completion_ids[:, :prompt_length]
    #         completion_ids = prompt_completion_ids[:, prompt_length:]

    #     # Mask everything after the first EOS token
    #     is_eos = completion_ids == self.processing_class.eos_token_id
    #     eos_idx = torch.full(
    #         (is_eos.size(0),), is_eos.size(1), dtype=torch.long, device=device
    #     )
    #     eos_idx[is_eos.any(dim=1)] = is_eos.int().argmax(dim=1)[is_eos.any(dim=1)]
    #     sequence_indices = torch.arange(is_eos.size(1), device=device).expand(
    #         is_eos.size(0), -1
    #     )
    #     completion_mask = (sequence_indices <= eos_idx.unsqueeze(1)).int()

    #     # Concatenate prompt_mask with completion_mask for logit computation
    #     attention_mask = torch.cat([prompt_mask, completion_mask], dim=1)  # (B*G, P+C)

    #     logits_to_keep = completion_ids.size(
    #         1
    #     )  # we only need to compute the logits for the completion tokens

    #     with torch.inference_mode():
    #         if self.ref_model is not None:
    #             ref_per_token_logps = self._get_per_token_logps(
    #                 self.ref_model,
    #                 prompt_completion_ids,
    #                 attention_mask,
    #                 logits_to_keep,
    #             )
    #         else:
    #             with self.accelerator.unwrap_model(self.model).disable_adapter():
    #                 ref_per_token_logps = self._get_per_token_logps(
    #                     self.model,
    #                     prompt_completion_ids,
    #                     attention_mask,
    #                     logits_to_keep,
    #                 )

    #     # Decode the generated completions
    #     completions_text = self.processing_class.batch_decode(
    #         completion_ids, skip_special_tokens=True
    #     )
    #     if is_conversational(inputs[0]):
    #         completions = []
    #         for prompt, completion in zip(prompts, completions_text):
    #             bootstrap = (
    #                 prompt.pop()["content"] if prompt[-1]["role"] == "assistant" else ""
    #             )
    #             completions.append(
    #                 [{"role": "assistant", "content": bootstrap + completion}]
    #             )
    #     else:
    #         completions = completions_text

    #     rewards_per_func = torch.zeros(
    #         len(prompts), len(self.reward_funcs), device=device
    #     )
    #     for i, (reward_func, reward_processing_class) in enumerate(
    #         zip(self.reward_funcs, self.reward_processing_classes)
    #     ):
    #         if isinstance(
    #             reward_func, nn.Module
    #         ):  # Module instead of PretrainedModel for compat with compiled models
    #             if is_conversational(inputs[0]):
    #                 messages = [
    #                     {"messages": p + c} for p, c in zip(prompts, completions)
    #                 ]
    #                 texts = [
    #                     apply_chat_template(x, reward_processing_class)["text"]
    #                     for x in messages
    #                 ]
    #             else:
    #                 texts = [p + c for p, c in zip(prompts, completions)]
    #             reward_inputs = reward_processing_class(
    #                 texts,
    #                 return_tensors="pt",
    #                 padding=True,
    #                 padding_side="right",
    #                 add_special_tokens=False,
    #             )
    #             reward_inputs = super()._prepare_inputs(reward_inputs)
    #             with torch.inference_mode():
    #                 rewards_per_func[:, i] = reward_func(**reward_inputs).logits[
    #                     :, 0
    #                 ]  # Shape (B*G,)
    #         else:
    #             # Repeat all input columns (but "prompt" and "completion") to match the number of generations
    #             keys = [key for key in inputs[0] if key not in ["prompt", "completion"]]
    #             reward_kwargs = {
    #                 key: [example[key] for example in inputs] for key in keys
    #             }
    #             output_reward_func = reward_func(
    #                 prompts=prompts, completions=completions, **reward_kwargs
    #             )
    #             rewards_per_func[:, i] = torch.tensor(
    #                 output_reward_func, dtype=torch.float32, device=device
    #             )

    #     # Gather the reward per function: this part is crucial, because the rewards are normalized per group and the
    #     # completions may be distributed across processes
    #     rewards_per_func = gather(rewards_per_func)

    #     # Apply weights to each reward function's output and sum
    #     rewards = (rewards_per_func * self.reward_weights.to(device).unsqueeze(0)).sum(
    #         dim=1
    #     )

    #     # Compute grouped-wise rewards
    #     mean_grouped_rewards = rewards.view(-1, self.num_generations).mean(dim=1)
    #     std_grouped_rewards = rewards.view(-1, self.num_generations).std(dim=1)

    #     # Normalize the rewards to compute the advantages
    #     mean_grouped_rewards = mean_grouped_rewards.repeat_interleave(
    #         self.num_generations, dim=0
    #     )
    #     std_grouped_rewards = std_grouped_rewards.repeat_interleave(
    #         self.num_generations, dim=0
    #     )
    #     advantages = (rewards - mean_grouped_rewards) / (std_grouped_rewards + 1e-4)

    #     # Slice to keep only the local part of the data
    #     process_slice = slice(
    #         self.accelerator.process_index * len(prompts),
    #         (self.accelerator.process_index + 1) * len(prompts),
    #     )
    #     advantages = advantages[process_slice]

    #     # Log the metrics
    #     reward_per_func = rewards_per_func.mean(0)
    #     for i, reward_func in enumerate(self.reward_funcs):
    #         if isinstance(
    #             reward_func, nn.Module
    #         ):  # Module instead of PretrainedModel for compat with compiled models
    #             reward_func_name = reward_func.config._name_or_path.split("/")[-1]
    #         else:
    #             reward_func_name = reward_func.__name__
    #         self._metrics[f"rewards/{reward_func_name}"].append(
    #             reward_per_func[i].item()
    #         )

    #     self._metrics["reward"].append(rewards.mean().item())
    #     self._metrics["reward_std"].append(std_grouped_rewards.mean().item())

    #     if (
    #         self.log_completions
    #         and self.state.global_step % self.args.logging_steps == 0
    #         and "wandb" in self.args.report_to
    #     ):
    #         import pandas as pd

    #         # For logging
    #         table = {
    #             "step": [str(self.state.global_step)] * len(rewards),
    #             "prompt": gather_object(prompts_text),
    #             "completion": gather_object(completions_text),
    #             "reward": rewards.tolist(),
    #         }
    #         df = pd.DataFrame(table)

    #         if wandb.run is not None and self.accelerator.is_main_process:
    #             wandb.log({"completions": wandb.Table(dataframe=df)})
    #             df.to_csv(f"completions_{self.state.global_step}.csv")

    #     return {
    #         "prompt_ids": prompt_ids,
    #         "prompt_mask": prompt_mask,
    #         "completion_ids": completion_ids,
    #         "completion_mask": completion_mask,
    #         "ref_per_token_logps": ref_per_token_logps,
    #         "advantages": advantages,
    #     }
