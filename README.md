# UnCoBench

This directory contains **1,000 groups of paired English benchmark tasks** for evaluating the performance of multi-agent systems under unreliable collaboration, along with the **automated pipeline** used to generate them.

```text
data/         1,000 paired tasks in each of five settings
pipeline/     Generation code, runtime building blocks and prompts
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

## License

Copyright (c) 2026 UnCoBench contributors.

The code, including the generation pipeline and evaluation logic in `run_one.py`, and the accompanying documentation and generation prompts are licensed under the [MIT License](LICENSE).

The benchmark data, including task text, role information and reference answers in `data/`, are licensed under [CC BY 4.0](LICENSE-DATA). This includes task content embedded in `run_one.py`. When sharing the data or adaptations, credit the UnCoBench contributors, link to [this repository](https://github.com/iNLP-Lab/UnCoBench) and the [license](https://creativecommons.org/licenses/by/4.0/), and indicate any changes.
