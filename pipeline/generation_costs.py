"""Read provider-reported USD costs from generation traces without extra API calls."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def trace_call_ids(output_root: Path) -> set[str]:
    root = Path(output_root) / 'api_traces'
    return {str(path.parent.relative_to(root)) for name in ('request.json', 'response.json', 'error.json')
            for path in root.glob(f'*/*/{name}')}


def summarize_costs(output_root: Path, call_ids: set[str] | None = None) -> dict:
    if call_ids is None:
        call_ids = trace_call_ids(output_root)
    total = Decimal(0)
    missing = 0
    for call_id in call_ids:
        try:
            path = Path(output_root) / 'api_traces' / call_id / 'response.json'
            response = json.loads(path.read_text(encoding='utf-8'))['response']
            value = response['usage']['cost']
            if value is None or isinstance(value, bool):
                raise ValueError('missing or invalid cost')
            cost = Decimal(str(value))
            if not cost.is_finite() or cost < 0:
                raise ValueError('invalid cost')
            total += cost
        except (OSError, KeyError, TypeError, ValueError, InvalidOperation):
            missing += 1
    return {'cost_usd': float(total), 'calls': len(call_ids), 'missing_cost_calls': missing}
