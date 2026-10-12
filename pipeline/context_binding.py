"""Resolve record-specific evidence contexts without additional model calls."""
from __future__ import annotations

import copy


def validate_context_templates(templates, facts, target, alternate):
    if not isinstance(templates, dict):
        raise ValueError('context_templates must be an object')
    by_topic = {fact['topic_id']: fact for fact in facts}
    for topic_id, fields in templates.items():
        if topic_id not in by_topic or not isinstance(fields, dict) or not fields:
            raise ValueError('context_templates must reference eligible topics')
        for field, template in fields.items():
            if field not in ('scope', 'measurement'):
                raise ValueError('context template field must be scope or measurement')
            if not isinstance(template, str) or template.count('{context}') != 1:
                raise ValueError('context template must contain exactly one {context}')
            remainder = template.replace('{context}', '')
            if '{' in remainder or '}' in remainder or target in remainder or alternate in remainder:
                raise ValueError('context template contains a literal or invalid context')


def resolved_evidence_context(task, record, topic):
    """Keep topic definitions immutable; bind only the current record's context."""
    evidence = copy.deepcopy(topic.get('evidence_context', {}))
    pair = task.get('error_pair', {})
    context = record.get('context')
    if not context or record['owner_role_id'] != pair.get('affected_role_id'):
        return evidence
    value = context['value']
    templates = pair.get('context_templates', {}).get(topic['topic_id'], {})
    for field in ('scope', 'measurement'):
        if field in templates:
            evidence[field] = templates[field].replace('{context}', value)
        elif pair.get('target_context'):
            evidence[field] = evidence.get(field, '').replace(pair['target_context'], value)
    return evidence


def validate_record_context(task, record, text):
    """A lexical guard, not a semantic judge. No inference or model invocation."""
    context = record.get('context')
    pair = task.get('error_pair', {})
    if not context or record['owner_role_id'] != pair.get('affected_role_id'):
        return
    expected = context['value']
    if expected not in text:
        raise ValueError(f"record {record['record_id']} must retain its context: {expected}")
    opposite = pair['alternate_context'] if expected == pair['target_context'] else pair['target_context']
    # Remove the full expected context before checking overlapping scope values.
    if opposite in text.replace(expected, ''):
        raise ValueError(f"record {record['record_id']} contains conflicting context: {opposite}")
