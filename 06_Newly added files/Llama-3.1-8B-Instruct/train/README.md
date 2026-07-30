---
library_name: peft
license: other
base_model: /root/autodl-tmp/modelscope/hub/LLM-Research/Meta-Llama-3.1-8B-Instruct
tags:
- llama-factory
- lora
- generated_from_trainer
model-index:
- name: train_2026-06-22-19-52-55-8b-lora-4lun-6500jieduan-eval0.111
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# train_2026-06-22-19-52-55-8b-lora-4lun-6500jieduan-eval0.111

This model is a fine-tuned version of [/root/autodl-tmp/modelscope/hub/LLM-Research/Meta-Llama-3.1-8B-Instruct](https://huggingface.co//root/autodl-tmp/modelscope/hub/LLM-Research/Meta-Llama-3.1-8B-Instruct) on the train dataset.
It achieves the following results on the evaluation set:
- Loss: 0.0018
- Num Input Tokens Seen: 14761312

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 5e-06
- train_batch_size: 2
- eval_batch_size: 2
- seed: 42
- gradient_accumulation_steps: 2
- total_train_batch_size: 4
- optimizer: Use adamw_torch with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: cosine
- num_epochs: 4.0

### Training results

| Training Loss | Epoch | Step | Validation Loss | Input Tokens Seen |
|:-------------:|:-----:|:----:|:---------------:|:-----------------:|
| 0.002         | 0.5   | 100  | 0.0031          | 1841936           |
| 0.0016        | 1.0   | 200  | 0.0022          | 3688784           |
| 0.0061        | 1.5   | 300  | 0.0020          | 5533824           |
| 0.0022        | 2.0   | 400  | 0.0019          | 7378336           |
| 0.0016        | 2.5   | 500  | 0.0019          | 9225504           |
| 0.0016        | 3.0   | 600  | 0.0018          | 11071536          |
| 0.0017        | 3.5   | 700  | 0.0018          | 12914688          |
| 0.0019        | 4.0   | 800  | 0.0018          | 14761312          |


### Framework versions

- PEFT 0.12.0
- Transformers 4.49.0
- Pytorch 2.1.2+cu121
- Datasets 3.3.2
- Tokenizers 0.21.0