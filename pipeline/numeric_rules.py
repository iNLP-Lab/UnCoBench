"""Numeric contracts shared by ontology validation and public query construction."""
from __future__ import annotations

from collections import Counter
import math
import random

OPERATIONS = ('sum', 'difference', 'average', 'ratio', 'product',
              'weighted_sum', 'sum_minus', 'piecewise')


def select_operation(recent_scenarios, seed):
    """Prefer the least represented operation; seeded ties are reproducible."""
    counts = Counter(s.get('numeric_rule', {}).get('operation') for s in recent_scenarios)
    least = min(counts[op] for op in OPERATIONS)
    return random.Random(seed).choice([op for op in OPERATIONS if counts[op] == least])


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _unit_dimensions(unit):
    # Simplify explicit symbolic units only; do not infer unit conversions.
    if not isinstance(unit, str) or not unit.strip() or unit != unit.strip():
        raise ValueError('numeric units must be non-empty canonical strings')
    if unit in {'1', '倍'}:
        return {}
    parts = unit.replace('·', '*').split('/')
    if len(parts) > 2:
        raise ValueError('units support products and at most one denominator')
    dimensions = Counter()
    for i, part in enumerate(parts):
        for atom in part.split('*'):
            if not atom or any(c in atom for c in '()^ '):
                raise ValueError('invalid unit expression')
            if atom != '1':
                dimensions[atom] += 1 if i == 0 else -1
    return {k: v for k, v in dimensions.items() if v}


def _combine_units(units, signs):
    dimensions = Counter()
    for unit, sign in zip(units, signs):
        for key, value in _unit_dimensions(unit).items():
            dimensions[key] += sign * value
    return {k: v for k, v in dimensions.items() if v}


def validate_numeric_rule(rule, topics):
    if not isinstance(rule, dict):
        raise ValueError('numeric_rule must be an object')
    operation = rule.get('operation')
    if operation not in OPERATIONS:
        raise ValueError('numeric_rule must use a supported composite numeric operation')
    ids = rule.get('topic_ids')
    if not isinstance(ids, list) or len(ids) < 2 or any(not isinstance(t, str) for t in ids):
        raise ValueError('numeric_rule must reference at least two topic_ids')
    by_id = {t['topic_id']: t for t in topics}
    if len(set(ids)) != len(ids) or any(t not in by_id for t in ids):
        raise ValueError('numeric_rule must reference distinct existing topics')
    operands = [by_id[t] for t in ids]
    if any(t.get('value_type') not in {'integer', 'number'} for t in operands):
        raise ValueError('numeric_rule topics must be numeric')
    if any('operator' in t for t in operands):
        raise ValueError('numeric_rule topics must not be formal conditions')
    for topic in operands:
        domain = topic.get('domain')
        if not isinstance(domain, list) or len(domain) < 2 or any(not _finite(v) for v in domain):
            raise ValueError('numeric operand domains must contain finite numbers')
    precision = rule.get('precision', 0)
    if type(precision) is not int or not 0 <= precision <= 6:
        raise ValueError('numeric precision must be an integer from 0 to 6')
    units = [t.get('unit') for t in operands]
    output_dimensions = _unit_dimensions(rule.get('unit'))
    for unit in units:
        _unit_dimensions(unit)
    if operation in {'difference', 'ratio'} and len(ids) != 2:
        raise ValueError(f'numeric operation {operation} requires exactly two topics')
    if operation in {'sum', 'difference', 'average', 'weighted_sum', 'sum_minus'}:
        if any(unit != rule['unit'] for unit in units):
            raise ValueError('numeric_rule topics must use the same unit as numeric_rule')
    elif operation in {'product', 'ratio'}:
        signs = [1] * len(ids) if operation == 'product' else [1, -1]
        if _combine_units(units, signs) != output_dimensions:
            raise ValueError('numeric_rule result unit does not match operand dimensions')
        if operation == 'ratio':
            if 0 in operands[1]['domain']:
                raise ValueError('ratio denominator domain cannot contain zero')
            if units[0] == units[1] and rule['unit'] not in {'倍', '1'}:
                raise ValueError('same-unit ratio must use dimensionless unit 1, not percent')
    if operation == 'weighted_sum':
        weights = rule.get('weights')
        if not isinstance(weights, list) or len(weights) != len(ids) or any(not _finite(w) or w <= 0 for w in weights):
            raise ValueError('weighted_sum requires one finite positive weight per topic')
    if operation == 'sum_minus':
        count = rule.get('subtract_count')
        if type(count) is not int or not 1 <= count <= len(ids) - 2:
            raise ValueError('sum_minus requires at least two additions and one subtraction')
    if operation == 'piecewise':
        if len(set(units)) != 1 or any(v < 0 for t in operands for v in t['domain']):
            raise ValueError('piecewise quantities must be nonnegative and use the same unit')
        rate_unit = rule.get('rate_unit')
        if _combine_units([units[0], rate_unit], [1, 1]) != output_dimensions:
            raise ValueError('piecewise rate_unit must convert quantity to output unit')
        tiers = rule.get('tiers')
        if not isinstance(tiers, list) or len(tiers) < 2:
            raise ValueError('piecewise requires at least two progressive tiers')
        previous = 0
        for i, tier in enumerate(tiers):
            if not isinstance(tier, dict) or set(tier) != {'upper_bound', 'rate'}:
                raise ValueError('each tier requires upper_bound and rate')
            if not _finite(tier['rate']) or tier['rate'] <= 0:
                raise ValueError('tier rates must be finite and positive')
            upper = tier['upper_bound']
            if i == len(tiers) - 1:
                if upper is not None:
                    raise ValueError('last tier upper_bound must be null')
            elif not _finite(upper) or upper <= previous:
                raise ValueError('tier bounds must strictly increase from zero')
            else:
                previous = upper
        if len({t['rate'] for t in tiers}) < 2:
            raise ValueError('piecewise must use distinct rates')
        low = sum(min(t['domain']) for t in operands)
        high = sum(max(t['domain']) for t in operands)
        if not any(low < t['upper_bound'] < high for t in tiers[:-1]):
            raise ValueError('piecewise domains must span at least one tier boundary')
    optional = {'weights', 'subtract_count', 'tiers', 'rate_unit'}
    allowed = {'weighted_sum': {'weights'}, 'sum_minus': {'subtract_count'},
               'piecewise': {'tiers', 'rate_unit'}}.get(operation, set())
    if (optional & rule.keys()) - allowed:
        raise ValueError('numeric_rule contains parameters for another operation')


def describe_numeric_rule(rule, topics):
    """Public English formula; values remain private to their owning roles."""
    labels = {t['topic_id']: t['label'] for t in topics}
    names = [f"[{labels[t]}]" for t in rule['topic_ids']]
    op = rule['operation']
    if op == 'sum': formula = ' + '.join(names)
    elif op == 'difference': formula = ' - '.join(names)
    elif op == 'average': formula = '(' + ' + '.join(names) + f') / {len(names)} (arithmetic mean)'
    elif op == 'ratio': formula = names[0] + ' / ' + names[1] + ' (direct ratio; do not multiply by 100; denominator must not be zero)'
    elif op == 'product': formula = ' * '.join(names)
    elif op == 'weighted_sum':
        formula = ' + '.join(f'{w} * {n}' for w, n in zip(rule['weights'], names))
        formula += ' (sum directly; do not divide by the sum of weights)'
    elif op == 'sum_minus':
        split = len(names) - rule['subtract_count']
        formula = '(' + ' + '.join(names[:split]) + ') - (' + ' + '.join(names[split:]) + ')'
    elif op == 'piecewise':
        unit = next(t['unit'] for t in topics if t['topic_id'] == rule['topic_ids'][0])
        parts = ['total = ' + ' + '.join(names),
                 'Apply marginal rates progressively from zero and add the tier charges; do not apply the highest rate to the entire total']
        lower = 0
        for tier in rule['tiers']:
            upper = tier['upper_bound']
            interval = f'quantity above {lower} {unit}' if upper is None else f'quantity from {lower} to {upper} {unit}'
            parts.append(f"{interval} at {tier['rate']} {rule['rate_unit']}")
            lower = upper
        formula = '; '.join(parts)
    else: raise ValueError(f'unsupported numeric operation: {op}')
    return (f"Compute only for the unique eligible candidate: {formula}. Result unit: {rule['unit']}. "
            f"Round only the final result to {rule.get('precision', 0)} decimal places (ties to even). "
            'If no candidate qualifies, numeric_result is null.')
