# UnCoBench

<p align="center">
  <strong>Beyond perfect teammates: collaboration with unreliable colleagues.</strong>
</p>

<p align="center">
  <a href="https://arxiv.org/abs/2610.16117"><img src="assets/badges/arxiv.svg" alt="arXiv: 2610.16117"></a>
  <a href="https://huggingface.co/datasets/iNLP-Lab/UnCoBench"><img src="assets/badges/huggingface.svg" alt="Hugging Face Dataset"></a>
  <a href="#automated-task-generation-pipeline"><img src="assets/badges/python.svg" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="assets/badges/code-license.svg" alt="Code License: MIT"></a>
  <a href="LICENSE-DATA"><img src="assets/badges/data-license.svg" alt="Data License: CC BY 4.0"></a>
</p>

Multi-agent systems often assume that every teammate provides relevant, complete, and timely information. In practice, a colleague may answer for the wrong context, omit a critical detail, or fail to respond. **UnCoBench (Unreliable Colleagues Benchmark)** evaluates whether a main agent can detect these breakdowns, ask targeted follow-up questions, and recover the evidence needed to complete the task.

This repository includes **1,000 paired task groups across five settings**, the **automated task generation pipeline**, and **evaluation scripts** for API-based and locally hosted main models.

```text
data/         1,000 paired tasks in each of five settings
pipeline/     Generation code, runtime building blocks and prompts
evaluation/   Batch evaluation
```

## Data

The benchmark includes four primary settings: `reliable`, `misaligned`, `incomplete`, and `missed`. These settings support paired comparisons that isolate the effect of each unreliable behavior. The additional `mixed` setting combines all three unreliable behaviors as a further stress test. Task IDs from `task_001` to `task_1000` are shared across all five settings, yielding 1,000 paired task groups and 5,000 setting-specific instances.

Each task retains:

- `tasks/run_one.py`: evaluates model performance on this task.
- `role_agents/*.json`: role descriptions and private information.

## Automated Task Generation Pipeline 

Use Python 3.10+ on macOS or Linux

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in your API key in `.env`, then replace the model placeholders below with your model IDs:

```bash
python pipeline/generate_benchmark.py \
  --count 1000 --workers 20 --seed 2026 \
  --generation-model YOUR_GENERATION_MODEL \
  --qualification-model YOUR_QUALIFICATION_MODEL \
  --output-root outputs/generated
```

Adjust `--count` to generate a different number of groups. Generated tasks are saved under `outputs/generated/generated_tasks/`.

## Closed-Source Model Evaluation

After installing the dependencies and configuring `.env`, run all 1,000 task groups across all five settings:

```bash
python evaluation/run_all_closed_source.py \
  --models YOUR_MAIN_MODEL \
  --role-model YOUR_ROLE_MODEL \
  --workers 20
```

Supply multiple IDs after `--models` to evaluate several main models. Each model runs once per task instance. Use `--settings reliable misaligned incomplete missed` for the four primary settings, or `--settings mixed` for the additional stress test. Use `--start 1 --end 10` for a smaller task range.

## Open-sourced Model Evaluation

After installing the dependencies and [vLLM](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/) in your GPU environment, start a local main model:

```bash
CUDA_VISIBLE_DEVICES=0 bash evaluation/serve_local_model.sh \
  /path/to/model YOUR_MAIN_MODEL
```

In another terminal, configure `OPENROUTER_API_KEY` or `ROLE_AGENT_API_KEY` in `.env` and run all 1,000 task groups across all five settings, keeping DeepSeek as the role model:

```bash
python evaluation/run_all_closed_source.py \
  --local-main \
  --models YOUR_MAIN_MODEL \
  --main-base-url http://127.0.0.1:8000/v1 \
  --role-model deepseek/deepseek-v4-flash-0731 \
  --workers 20
```

Use the same model name in both commands. Set `VLLM_PORT` and `VLLM_TP_SIZE` to change the serving port and tensor parallel size; additional vLLM options can follow the model name. For reasoning models, pass the model's `--reasoning-parser` when serving, or disable thinking with `--main-extra-body '{"chat_template_kwargs":{"enable_thinking":false}}'` when supported. Use `--main-max-tokens` to change the local output limit (default: 8192). The local main model uses a placeholder API key unless `MAIN_AGENT_API_KEY` is set; role credentials remain in the environment or `.env`. Task selection and result formats are shared with closed-source evaluation, with local results saved under `outputs/evaluation/open_source_*`.

## License

Copyright (c) 2026 UnCoBench contributors.

The code, including the generation pipeline and evaluation logic in `run_one.py`, and the accompanying documentation and generation prompts are licensed under the [MIT License](LICENSE).

The benchmark data, including task text, role information and reference answers in `data/`, are licensed under [CC BY 4.0](LICENSE-DATA). This includes task content embedded in `run_one.py`. When sharing the data or adaptations, credit the UnCoBench contributors, link to [this repository](https://github.com/iNLP-Lab/UnCoBench) and the [license](https://creativecommons.org/licenses/by/4.0/), and indicate any changes.
