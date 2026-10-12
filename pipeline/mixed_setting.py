"""Choose paired interventions once, then compose them without new model calls."""
import copy
import random


def select_interventions(task):
    from error_pair import has_consequential_alternate
    from incomplete_setting import incomplete_candidates
    from task_types import validate_task_graph

    required = set(task['routing']['required_record_ids'])
    eligible = sorted({r['owner_role_id'] for r in task['records'] if r['record_id'] in required})
    errors = [r for r in task['records'] if r['record_id'] in required
              and has_consequential_alternate(task, r, seed=task['seed'])]
    combinations = [dict(error_role_id=error['owner_role_id'], error_record_id=error['record_id'],
                         incomplete_role_id=partial['role_id'], incomplete_record_id=partial['record_id'],
                         hidden_predicate_id=partial['hidden_predicate_id'], neglect_role_id=neglect)
                    for partial in incomplete_candidates(task) for error in errors for neglect in eligible
                    if len({partial['role_id'], error['owner_role_id'], neglect}) == 3]
    if not combinations:
        raise ValueError('no eligible combination of three distinct intervention Roles')
    result = copy.deepcopy(task)
    result['intervention_plan'] = random.Random(f"{task['task_id']}:{task['seed']}:mixed").choice(combinations)
    return validate_task_graph(result)


def validate_intervention_plan(task):
    plan = task['intervention_plan']
    records = {r['record_id']: r for r in task['records']}
    roles = {r['role_id']: r for r in task['roles']}
    affected = [plan.get(k) for k in ('error_role_id', 'incomplete_role_id', 'neglect_role_id')]
    if len(set(affected)) != 3 or any(r not in roles or roles[r]['kind'] == 'distractor' for r in affected):
        raise ValueError('intervention plan requires three distinct necessary Roles')
    for kind in ('error', 'incomplete'):
        record = records.get(plan.get(kind + '_record_id'))
        if record is None or record['owner_role_id'] != plan[kind + '_role_id']:
            raise ValueError('intervention plan record ownership mismatch')
    required = set(task['routing']['required_record_ids'])
    if task.get('setting') in {'misaligned', 'mixed'}:
        required.discard(task['error_pair']['alternate_record_id'])
        required.add(task['error_pair']['target_record_id'])
    if (not {plan['error_record_id'], plan['incomplete_record_id']} <= required
            or not any(records[r]['owner_role_id'] == plan['neglect_role_id'] for r in required)):
        raise ValueError('intervention plan must target necessary business records')
    hidden = next((p for p in task['predicates'] if p['predicate_id'] == plan.get('hidden_predicate_id')), None)
    if hidden is None or hidden['owner_role_id'] != plan['incomplete_role_id']:
        raise ValueError('intervention plan hidden fact ownership mismatch')
    observations = {o['observation_id']: o for o in task['observations']}
    if not any(observations[o].get('predicate_id') == hidden['predicate_id']
               for o in records[plan['incomplete_record_id']]['observation_ids']):
        raise ValueError('intervention plan hidden fact must belong to its selected record')
    pair = task.get('error_pair')
    if pair and (pair['target_record_id'] != plan['error_record_id'] or pair['affected_role_id'] != plan['error_role_id']):
        raise ValueError('Error profile must match intervention plan')
    partial = task.get('incomplete_profile')
    if partial and any(partial[field] != plan[key] for field, key in (
            ('record_id', 'incomplete_record_id'), ('role_id', 'incomplete_role_id'),
            ('hidden_predicate_id', 'hidden_predicate_id'))):
        raise ValueError('Incomplete profile must match intervention plan')
    if task.get('neglect_profile') and task['neglect_profile']['role_ids'] != [plan['neglect_role_id']]:
        raise ValueError('Neglect profile must match intervention plan')


def derive_mixed_task(reliable, *, disclosure_mode='omission'):
    from error_pair import derive_error_task
    from incomplete_setting import derive_incomplete_task
    from communication_setting import derive_neglect_task
    from runtime_settings import apply_budget
    from task_types import validate_task_graph

    if reliable.get('setting') != 'reliable' or not reliable.get('intervention_plan'):
        raise ValueError('Mixed requires a Reliable task with a joint intervention plan')
    task = derive_error_task(reliable)
    task['incomplete_profile'] = derive_incomplete_task(reliable, disclosure_mode=disclosure_mode)['incomplete_profile']
    task['neglect_profile'] = derive_neglect_task(reliable)['neglect_profile']
    task['setting'] = 'mixed'
    return validate_task_graph(apply_budget(task))
