import logging

from transformers import set_seed
from trl import ModelConfig, TrlParser, GRPOTrainer, GRPOConfig, get_peft_config

from agent.openr1.utils import (
    setup_logging,
    init_wandb,
    get_tokenizer,
    get_checkpoint,
    ScriptArguments,
)

logger = logging.getLogger(__name__)


def GRPO(data_loader, reward_funcs, grpo_trainer=GRPOTrainer):
    parser = TrlParser((ScriptArguments, GRPOConfig, ModelConfig))
    script_args, training_args, model_args = parser.parse_args_and_config()

    # Set seed for reproducibility
    set_seed(training_args.seed)

    # Setup logging
    setup_logging(logger, training_args.get_process_log_level())

    # Initialize wandb
    if "wandb" in training_args.report_to:
        init_wandb(script_args)

    # Check for last checkpoint
    checkpoint = get_checkpoint(training_args)

    # Load tokenizer
    tokenizer = get_tokenizer(model_args, training_args)

    # Initializing model kwargs
    training_args.model_init_kwargs = dict(
        revision=model_args.model_revision,
        trust_remote_code=model_args.trust_remote_code,
        attn_implementation=model_args.attn_implementation,
        torch_dtype=model_args.torch_dtype,
    )

    # Initialize the GRPO trainer
    trainer = grpo_trainer(
        model=model_args.model_name_or_path,
        reward_funcs=reward_funcs,
        args=training_args,
        train_dataset=data_loader[script_args.dataset_train_split],
        peft_config=get_peft_config(model_args),
        processing_class=tokenizer,
    )

    # Training loop
    metrics = trainer.train(resume_from_checkpoint=checkpoint).metrics
    trainer.log_metrics("train", metrics)
    trainer.save_metrics("train", metrics)
    trainer.save_state()

    # Save model and create model card
    trainer.save_model(training_args.output_dir)
    logger.info(f"Model saved to {training_args.output_dir}")

    # Save everything else on main process
    if trainer.accelerator.is_main_process:
        # Restore k,v cache for fast inference
        trainer.model.config.use_cache = True
        trainer.model.config.save_pretrained(training_args.output_dir)

    # Evaluate
    if training_args.do_eval:
        metrics = trainer.evaluate(data_loader[script_args.dataset_test_split])
        trainer.log_metrics("eval", metrics)
        trainer.save_metrics("eval", metrics)
