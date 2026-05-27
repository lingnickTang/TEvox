set -x

ray job submit --address="http://127.0.0.1:8265" \
   --runtime-env-json='{"working_dir": "/home/hlxu/openrlhf"}' \
   -- python3 -m openrlhf.custom.train_grpo_ray \
   --actor_num_nodes 1 \
   --actor_num_gpus_per_node 1 \
   --vllm_num_engines 4 \
   --vllm_tensor_parallel_size 1 \
   --vllm_gpu_memory_utilization 0.7 \
   --init_kl_coef 0 \
   --gamma 1.0 \
   --advantage_estimator group_norm \
   --pretrain Qwen/Qwen2.5-1.5B-Instruct \
   --remote_rm_url /home/hlxu/workspace/evox-ai/evox-server/openrlhf/custom/reward_func.py \
   --save_path /home/hlxu/openrlhf/examples/test_scripts/final/qwen2.5-1.5b-rlhf \
   --ckpt_path /home/hlxu/openrlhf/examples/test_scripts/ckpt/qwen2.5-1.5b-rlhf \
   --save_hf_ckpt \
   --micro_train_batch_size 8 \
   --train_batch_size 8 \
   --micro_rollout_batch_size 8 \
   --rollout_batch_size 4 \
   --n_samples_per_prompt 8 \
   --max_epochs 1 \
   --prompt_max_len 8192 \
   --generate_max_len 1024 \
   --zero_stage 3 \
   --bf16 \
   --actor_learning_rate 5e-7 \
   --normalize_reward \
   --gradient_checkpointing \
   --load_checkpoint \
   --vllm_sync_backend nccl \
   --enforce_eager \
   --flash_attn \
   --adam_offload \
   --enable_prefix_caching \
   --use_liger_kernel \
   --use_wandb fcfeb867ab16519a1e082575b1d118d15daeb3ea \
   --packing_samples \
   # --load_in_4bit \
   # --lora_rank 64 \
   # --lora_alpha 32 \
   # --ring_attn_size 2 \
   # --ring_head_stride 2 \
   # --vllm_enable_sleep \
   # --deepspeed_enable_sleep \
   # --pretrain Qwen/Qwen2.5-7B-Instruct-1M \
   # --use_wandb {wandb_token}