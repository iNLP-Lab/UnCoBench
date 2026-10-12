from __future__ import annotations

from runtime_settings import apply_budget
import copy
import math
import random
import re
from typing import Any

from task_solver import _evaluate_complete, _matches, gold_assignment, solve


INCOMPLETE_DISCLOSURE_MODES = ('upper_bound', 'interval', 'omission')
INCOMPLETE_DISCLOSURE_LABELS = {
    'omission': 'Omission', 'upper_bound': 'Loose upper bound', 'interval': 'Threshold-crossing interval',
}


def incomplete_mode_for_task(task_id: str) -> str:
    """Cycle by accepted task number, independently of seeds and rejected attempts."""
    match = re.fullmatch(r'task_(\d+)', task_id)
    if not match or int(match[1]) < 1:
        raise ValueError('Incomplete allocation requires a positive task_NNN identifier')
    return INCOMPLETE_DISCLOSURE_MODES[(int(match[1]) - 1) % 3]


def _disclosure_profile(task: dict[str, Any], base: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode not in INCOMPLETE_DISCLOSURE_MODES:
        raise ValueError(f'unsupported Incomplete disclosure mode: {mode}')
    profile = copy.deepcopy(base)
    if mode == 'omission':
        return profile
    predicate = next(p for p in task['predicates'] if p['predicate_id'] == base['hidden_predicate_id'])
    topic_id = task['incomplete_condition']['threshold_topic_id']
    conditions = [c for c in task['constraints'] if c['topic_id'] == topic_id]
    if len(conditions) != 1 or conditions[0]['operator'] not in {'lt', 'lte', 'gt', 'gte'}:
        raise ValueError('Coarse Incomplete disclosures require a numeric threshold condition')
    topic = next(t for t in task['topics'] if t['topic_id'] == topic_id)
    rule = task['numeric_rule']
    if topic.get('value_type') not in {'integer', 'number'} or topic_id in (rule.get('topic_ids') or [rule.get('topic_id')]):
        raise ValueError('Coarse Incomplete disclosures apply only to numeric threshold conditions, not result operands')
    condition = conditions[0]
    threshold = condition['threshold']
    domain = predicate['domain']
    if not domain or any(isinstance(v, bool) or not isinstance(v, (int, float))
                         or not math.isfinite(v) for v in [threshold, *domain]):
        raise ValueError('Incomplete bounds require finite numeric thresholds and domain values')
    # Choose disclosure bounds from the domain, never from the hidden gold value.
    lo, hi = min(threshold, *domain), max(threshold, *domain)
    step = 10 ** math.floor(math.log10(max(abs(lo), abs(hi), 1)))
    lower = (math.floor(lo / step) - 1) * step
    upper = (math.ceil(hi / step) + 1) * step
    if mode == 'interval' and lo > 0:
        scale = 10 ** math.floor(math.log10(lo))
        candidates = [factor * scale for factor in (0.1, 0.2, 0.5, 1, 2, 5)
                      if 0 < factor * scale < lo]
        if not candidates:
            raise ValueError('Cannot represent a nonzero interval lower bound below the domain')
        lower = max(candidates)
    if lo >= 0:
        lower = max(0, lower)
    if topic.get('value_type') == 'integer':
        lower = math.floor(lower)
    if topic.get('unit') in {'%', '％'} and 0 <= lo <= hi <= 100:
        upper = min(100, upper)
    lower = lower if mode == 'interval' else None
    retained = [v for v in domain if v <= upper and (lower is None or v >= lower)]
    if (not math.isfinite(upper) or (lower is not None and not math.isfinite(lower))
            or base['threshold_value'] not in retained
            or {_matches(v, condition['operator'], threshold) for v in retained} != {True, False}):
        raise ValueError('Incomplete disclosure must be true and permit both threshold outcomes')
    restricted = copy.deepcopy(task)
    next(p for p in restricted['predicates'] if p['predicate_id'] == base['hidden_predicate_id'])['domain'] = retained
    partial = gold_assignment(task)
    partial.pop(base['hidden_predicate_id'])
    outputs = solve(restricted, partial)['feasible_outputs']
    if len({(o['conclusion'], o['numeric_result']) for o in outputs}) < 2:
        raise ValueError('Incomplete disclosure must leave the final decision unresolved')
    metric, unit = base['threshold_label'], base['threshold_unit']
    statement = (f'{metric} is at most {upper:g} {unit}.' if mode == 'upper_bound'
                 else f'{metric} is between {lower:g} {unit} and {upper:g} {unit}, inclusive.')
    version = 'truthful_bounds_v3_domain_bounds'
    profile.update(disclosure_mode=mode, disclosure_version=version,
                   disclosure_bounds={'lower': lower, 'upper': upper},
                   coarse_statement=statement)
    return profile


def with_incomplete_disclosure(task: dict[str, Any], mode: str) -> dict[str, Any]:
    """Change only the disclosure of the already selected Incomplete fact."""
    from task_types import validate_task_graph
    if task.get('setting') not in {'incomplete', 'mixed'}:
        raise ValueError('Only Incomplete tasks can change disclosure mode')
    current = task['incomplete_profile']
    base = next((p for p in incomplete_candidates(task)
                 if p['record_id'] == current['record_id']
                 and p['hidden_predicate_id'] == current['hidden_predicate_id']), None)
    if base is None:
        raise ValueError('Incomplete target is not a pivotal threshold record')
    updated = copy.deepcopy(task)
    updated['incomplete_profile'] = _disclosure_profile(task, base, mode)
    return validate_task_graph(updated)


def validate_incomplete_profile(task: dict[str, Any]) -> None:
    profile = task.get('incomplete_profile')
    if not isinstance(profile, dict):
        raise ValueError('Incomplete profile must be an object')
    mode = profile.get('disclosure_mode', 'omission')
    if not any(profile == _disclosure_profile(task, base, mode) for base in incomplete_candidates(task)):
        raise ValueError('Incomplete must incompletely disclose one pivotal threshold from a bool=true downstream record')


def validate_incomplete_ontology(ontology: dict[str, Any], *, required: bool = False) -> None:
    pair = ontology.get('incomplete_condition')
    if pair is None and not required:
        return
    if not isinstance(pair, dict):
        raise ValueError('incomplete_condition must define boolean_topic_id and threshold_topic_id')
    topics = {topic['topic_id']: topic for topic in ontology['topics']}
    boolean = topics.get(pair.get('boolean_topic_id'), {})
    threshold = topics.get(pair.get('threshold_topic_id'), {})
    if not (
        boolean.get('value_type') == 'boolean' and boolean.get('operator') == 'eq'
        and boolean.get('threshold') is True
        and threshold.get('value_type') in {'integer', 'number'}
        and threshold.get('operator') in {'gt', 'gte', 'lt', 'lte'}
        and isinstance(threshold.get('threshold'), (int, float))
        and not isinstance(threshold.get('threshold'), bool)
    ):
        raise ValueError('Incomplete needs a true Boolean condition paired with a genuine numeric threshold condition')
    owners = [{role['role_id'] for role in ontology['roles']
               if topic.get('owner_capability') in role['capabilities']}
              for topic in (boolean, threshold)]
    if len(owners[0]) != 1 or owners[0] != owners[1]:
        raise ValueError('Incomplete Boolean and threshold facts must belong to the same Role')
    # The Boolean must not reveal whether the numeric condition is satisfied.
    boolean_text = ' '.join([boolean['label'], *boolean.get('aliases', []),
                             *boolean.get('evidence_context', {}).values()])
    if threshold['label'] in boolean_text:
        raise ValueError('Incomplete Boolean must not already express the paired numeric threshold')


def _partial_record_text(
    task: dict[str, Any], record: dict[str, Any], hidden_id: str, *,
    include_context: bool = True,
) -> str:
    observations = {item['observation_id']: item for item in task['observations']}
    topics = {item['topic_id']: item for item in task['topics']}
    candidate = next(item['name'] for item in task['candidates'] if item['candidate_id'] == record['candidate_id'])
    key = task['routing']['record_keys'][record['record_id']]
    parts = [f'{key}: {candidate}.']
    context = record.get('context')
    if context and include_context:
        parts.append(f"{context['dimension_label']}: {context['value']}.")
    for observation_id in record['observation_ids']:
        fact = observations[observation_id]
        if fact.get('predicate_id') == hidden_id:
            continue
        topic = topics[fact['topic_id']]
        value = fact['claimed_value']
        text = ('true' if value else 'false') if isinstance(value, bool) else str(value)
        parts.append(f"{candidate}: {topic['label']} = {text} {topic.get('unit', '')}.")
        context = topic.get('evidence_context', {})
        parts.append('; '.join(f'{label}: {context[field]}' for field, label in (
            ('source', 'Source'), ('scope', 'Scope'), ('measurement', 'Measurement'),
        ) if field in context) + '.')
    return ''.join(parts)


def incomplete_candidates(task: dict[str, Any]) -> list[dict[str, Any]]:
    pair = task.get('incomplete_condition')
    if not isinstance(pair, dict):
        return []
    topics = {item['topic_id']: item for item in task['topics']}
    threshold = topics[pair['threshold_topic_id']]
    full = gold_assignment(task)
    gold = _evaluate_complete(task, full)
    required = set(task['routing']['required_record_ids'])
    observations = {item['observation_id']: item for item in task['observations']}
    roles = {item['role_id']: item for item in task['roles']}
    eligible = []
    for record in task['records']:
        if record['record_id'] not in required:
            continue
        role = roles[record['owner_role_id']]
        if role['kind'] in {'candidate_holder', 'router', 'distractor'}:
            continue
        boolean_id = f"{record['candidate_id']}_{pair['boolean_topic_id']}"
        hidden_id = f"{record['candidate_id']}_{pair['threshold_topic_id']}"
        owned = {observations[oid].get('predicate_id') for oid in record['observation_ids']}
        if not {boolean_id, hidden_id} <= owned or full.get(boolean_id) is not True:
            continue
        partial = {key: value for key, value in full.items() if key != hidden_id}
        report = solve(task, partial)
        # An alternative must change the valid answer, not create multiple winners.
        alternatives = [output for output in report['feasible_outputs']
                        if (output['conclusion'], output['numeric_result']) != (gold['conclusion'], gold['numeric_result'])]
        if not alternatives:
            continue
        text = _partial_record_text(task, record, hidden_id)
        labels = [threshold['label'], *threshold.get('aliases', [])]
        # Keep metric context while checking retained facts for hidden-value leakage.
        fact_text = _partial_record_text(task, record, hidden_id, include_context=False)
        if any(label in fact_text for label in labels):
            continue
        eligible.append({
            'record_id': record['record_id'], 'role_id': role['role_id'],
            'candidate_id': record['candidate_id'], 'key': task['routing']['record_keys'][record['record_id']],
            'boolean_predicate_id': boolean_id, 'boolean_label': topics[pair['boolean_topic_id']]['label'],
            'hidden_predicate_id': hidden_id,
            'threshold_label': threshold['label'], 'threshold_aliases': threshold.get('aliases', []),
            'threshold_value': full[hidden_id], 'threshold_unit': threshold.get('unit', ''),
            'partial_record_text': text, 'alternative_outputs': alternatives,
        })
    return eligible


def derive_incomplete_task(reliable: dict[str, Any], *, disclosure_mode: str = 'omission') -> dict[str, Any]:
    from task_types import validate_task_graph

    if reliable.get('setting') != 'reliable':
        raise ValueError('Incomplete must derive directly from Reliable')
    eligible = incomplete_candidates(reliable)
    if reliable.get('intervention_plan'):
        plan = reliable['intervention_plan']
        eligible = [p for p in eligible if p['record_id'] == plan['incomplete_record_id']
                    and p['hidden_predicate_id'] == plan['hidden_predicate_id']]
    if not eligible:
        raise ValueError('Reliable has no pivotal bool=true + threshold record for Incomplete')
    # Preserve seed salts so renaming does not change selected evidence.
    salt = bytes.fromhex('7461636974').decode('ascii')
    rng = random.Random(f"{reliable['task_id']}:{reliable['seed']}:{salt}")
    task = copy.deepcopy(reliable)
    task['setting'] = 'incomplete'
    task['incomplete_profile'] = _disclosure_profile(task, rng.choice(eligible), disclosure_mode)
    return validate_task_graph(apply_budget(task))
