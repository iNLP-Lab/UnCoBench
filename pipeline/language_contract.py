"""Reject Chinese carry-over in newly generated English model-facing text."""
import re


def require_english(value, path='output'):
    if isinstance(value, str) and re.search(r'[\u3400-\u9fff]', value):
        raise ValueError(f'{path} must be written in English')
    if isinstance(value, dict):
        for key, item in value.items():
            require_english(item, f'{path}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            require_english(item, f'{path}[{index}]')


def validate_english_output_root(root):
    """Validate cached model inputs too: language markers alone are insufficient."""
    import json
    from pathlib import Path
    root = Path(root)
    marked = [*(root / 'candidates').glob('attempt_*/ontology.json'),
              *(root / 'candidates').glob('attempt_*/*task_graph.json'),
              *(root / 'generated_tasks').glob('*/task_*/internal/task_graph.json')]
    for path in marked:
        value = json.loads(path.read_text())
        if value.get('language') != 'en':
            raise ValueError(f'English generation requires a new output directory or --fresh: {path}')
        require_english(value, str(path))
    for pattern in ['candidates/attempt_*/error_spec.json', 'candidates/attempt_*/*rendered_task.json',
                    'generated_tasks/*/task_*/role_agents/*.json']:
        for path in root.glob(pattern):
            require_english(json.loads(path.read_text()), str(path))
