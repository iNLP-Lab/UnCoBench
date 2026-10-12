"""Conservative English evidence rules shared by standalone generated runtimes.

This is attribution of explicit statements, not arbitrary semantic entailment.
Unsupported or conflicting statements remain unknown; no model calls are made.
"""
import re
from decimal import Decimal

_RECOVERY_NUMBER = r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?'
_RECOVERY_UNCERTAIN = r"\b(?:unknown|uncertain|unclear|may(?!\s+\d{1,4}\b)|might|could|should|would|must|expected|possibly|whether|cannot|unable|unconfirmed|approximately|about|around|roughly|estimated|not confirmed|not known|not established)\b"
_RECOVERY_NEGATIVE = r'\b(?:not|no|never|false|invalid|blocked|failed|denied|unavailable|unapproved|revoked|inactive|disabled|noncompliant)\b'


def evidence_text(text):
    text = text.replace('’', "'").replace('−', '-').replace('‑', '-')
    text = re.sub(r"\bcan't\b", 'cannot', text, flags=re.I)
    text = re.sub(r"n't\b", ' not', text, flags=re.I)
    text = re.sub(r'(?<![\w.,])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,]|\.\d)',
                  lambda m: m[0].replace(',', ''), text)
    return text


def evidence_phrase(text, phrase):
    if not phrase:
        return False
    return bool(re.search(r'(?<!\w)' + re.escape(phrase).replace(r'\ ', r'\s+') + r'(?!\w)', text, re.I))


def evidence_nonasserted(text):
    """Questions, hypotheses and unconfirmed claims are not returned facts."""
    return bool('?' in text or re.search(_RECOVERY_UNCERTAIN, text, re.I)
                or re.search(r'\b(?:if|unless|assuming|suppose|supposing|hypothetically)\b', text, re.I)
                or re.search(r'\b(?:do|does|did|has|have|had)\s+not\s+(?:confirm|verify|establish)(?:ed)?\b', text, re.I))


def evidence_clauses(text):
    # Preserve questions and uncertainty when splitting assertions.
    sentences = re.split(r'[。\n]|\.(?!\d)|(?<=[!?])\s+', text)
    clauses = []
    for sentence in sentences:
        if evidence_nonasserted(sentence):
            clauses.append(sentence)
        else:
            # Split conjunctions between assertions, never inside metric labels.
            predicate = r'\b(?:is|are|was|were|has|have|had|holds?|received|maintains?|equals?)\b|[:=]'
            parts = re.split(r'([;；]|,?\s+\b(?:but|and)\b\s+(?![+-]?\d))', sentence, flags=re.I)
            current = parts[0]
            for separator, following in zip(parts[1::2], parts[2::2]):
                continuation = re.match(r'(?:it|its|this|that|(?:the\s+)?status)\b', following, re.I)
                split = not continuation and (not re.search(r'\band\b', separator, re.I) or
                        re.search(predicate, current, re.I) and re.search(predicate, following, re.I))
                if split:
                    clauses.append(current)
                    current = following
                else:
                    current += separator + following
            clauses.append(current)
    return clauses


def evidence_scope(answer, question, profile):
    for target in [profile.get('candidate', ''), profile.get('target_context', '')]:
        if target and re.search(r'\b(?:not|outside|excluding|except)(?:\s+(?:for|the))?\s+' + re.escape(target) + r'(?!\w)', answer, re.I):
            return 'not_returned'
    candidates = profile.get('other_candidates', [])
    contexts = profile.get('other_contexts', [profile.get('alternate_context', '')])
    if any(evidence_phrase(answer, c) for c in [*candidates, *contexts] if c):
        target_also_present = evidence_phrase(answer, profile.get('candidate', '')) and (
            not profile.get('target_context') or evidence_phrase(answer, profile['target_context']))
        return 'unknown' if target_also_present else 'not_returned'
    combined = question.get('question', '') + '\n' + answer
    target_key = profile.get('target_key', '')
    if target_key and (question.get('key') == target_key or evidence_phrase(combined, target_key)):
        return 'eligible'
    if evidence_phrase(combined, profile.get('candidate', '')) and (
            not profile.get('target_context') or evidence_phrase(combined, profile['target_context'])):
        return 'eligible'
    return 'unknown'


def evidence_record_text(answer, profile):
    """Isolate an explicitly keyed record in a multi-record reply.

    A directory can contain facts as well as keys. Only the target key's
    segment is eligible; neighboring records never supply its evidence.
    Unstructured multi-candidate prose remains conservatively unscored.
    """
    keys = list(re.finditer(r'(?<!\w)[A-Z]{2,10}-[A-Z]{2,10}-[A-Z0-9]{3}(?!\w)', answer))
    target = profile.get('target_key')
    if not target or not any(m[0] == target for m in keys):
        return answer
    pieces = []
    for i, match in enumerate(keys):
        if match[0] == target:
            end = keys[i+1].start() if i+1 < len(keys) else len(answer)
            pieces.append(answer[match.start():end])
    return '\n'.join(pieces)


def evidence_key_request_only(answer):
    """An explicit request for a key supplies no factual recovery evidence."""
    return bool(re.fullmatch(r'\s*(?:please\s+(?:provide|supply)|I\s+need)\s+(?:a\s+)?valid\s+key\b[^\n.;]*[.!]?\s*', answer, re.I))


def evidence_unit_pattern(unit):
    # Unit names may inflect; canonical symbols remain case-sensitive.
    # Compose rate units without changing symbol case.
    parts = re.split(r'\s*/\s*|\s+per\s+', unit)
    if len(parts) == 2 and all(parts):
        return evidence_unit_pattern(parts[0]) + r'\s*(?:/|(?i:per))\s*' + evidence_unit_pattern(parts[1])
    groups = [('h', 'hour', 'hours'), ('min', 'minute', 'minutes'), ('s', 'second', 'seconds'),
              ('kg', 'kilogram', 'kilograms'), ('m', 'meter', 'meters', 'metre', 'metres'),
              ('d', 'day', 'days'), ('L', 'liter', 'liters', 'litre', 'litres'),
              ('%', 'percent', 'per cent'), ('instances', 'instance'), ('items', 'item'),
              ('people', 'person', 'persons'), ('days', 'day')]
    for group in groups:
        if unit in group:
            canonical, *words = group
            if canonical in {'instances', 'items', 'people', 'days'}:
                words.append(canonical)
                canonical = None
            parts = ([re.escape(canonical)] if canonical else []) + ['(?i:' + re.escape(w) + ')' for w in words]
            if unit == '%': parts.append('％')
            return '(?:' + '|'.join(sorted(parts, key=len, reverse=True)) + ')'
    if re.fullmatch(r'[a-z]+(?:-[a-z]+)+', unit):
        prefix, suffix = unit.rsplit('-', 1)
        return re.escape(prefix + '-') + evidence_unit_pattern(suffix)
    if re.fullmatch(r'[a-z]{3,}', unit) and unit not in {'mol', 'rad', 'kat', 'lux'}:
        singular = unit
        if unit.endswith('ies'):
            singular = unit[:-3] + 'y'
        elif re.search(r'(?:ch|sh|ss|x|z)es$', unit):
            singular = unit[:-2]
        elif unit.endswith('s') and not unit.endswith(('ss', 'us', 'is')):
            singular = unit[:-1]
        plural = (singular[:-1] + 'ies' if re.search(r'[^aeiou]y$', singular) else
                  singular + 'es' if re.search(r'(?:s|x|z|ch|sh)$', singular) else singular + 's')
        return '(?i:' + '|'.join(re.escape(w) for w in sorted({unit, singular, plural}, key=len, reverse=True)) + ')'
    return re.escape(unit)


def evidence_measurements(text, unit):
    text = evidence_text(text)
    text = re.sub(r'(?<=\d)[-–—](?=\d)', ' to ', text)
    suffix = (r'(?:\s+(?:1|(?i:dimensionless)))?' if unit == '1'
              else r'\s*' + evidence_unit_pattern(unit))
    pattern = r'(?<![A-Za-z0-9_.,+\-])(' + _RECOVERY_NUMBER + r')' + suffix + r'(?![A-Za-z0-9_/%]|\.\d|,\d)'
    return text, list(re.finditer(pattern, text))


def evidence_exact_measurement(text, match):
    before, after = text[max(0, match.start()-60):match.start()], text[match.end():match.end()+45]
    before = re.sub(r'\bamounts?\s+to\s*$', 'equals ', before, flags=re.I)
    if evidence_nonasserted(text):
        return False
    if re.search(r'(?:\b(?:under|over|below|above|less than|more than|at most|at least|up to|between|to|and|not|no more than|no less than)|不超过|不低于|小于等于|大于等于|小于|大于|至少|至多|最多|最少|低于|高于|介于|至|到|[<>≤≥～~–—])\s*$', before, re.I):
        return False
    if re.search(r'\d\s*[-–—]\s*$', before):
        return False
    if re.match(r'\s*(?:\b(?:maximum|minimum|max|min)\b|\bor (?:less|more|lower|higher)\b|\b(?:to|through)\s+[+-]?\d|[-–—~～]\s*\d)', after, re.I):
        return False
    return True


def english_exact_value(answer, value, unit):
    for clause in evidence_clauses(evidence_text(answer)):
        text, matches = evidence_measurements(clause, unit)
        if any(Decimal(m[1]) == Decimal(str(value)) and evidence_exact_measurement(text, m) for m in matches):
            return True
    return False


def numeric_evidence(answer, question, profile, fact):
    if evidence_key_request_only(answer):
        return 'not_returned'
    answer = evidence_text(evidence_record_text(answer, profile))
    scope = evidence_scope(answer, question, profile)
    if scope != 'eligible':
        return scope
    labels = [fact.get('label', ''), *fact.get('aliases', [])]
    states = set()
    for clause in metric_assertions(answer, profile, fact):
        # Bind each value to its asserted metric; nearby numbers are not evidence.
        if not any(evidence_phrase(clause, label) for label in labels if label):
            continue
        if evidence_nonasserted(clause) or re.search(r'\b(?:catalog|directory)\b', clause, re.I):
            continue
        # Leave ambiguous multi-metric clauses unscored.
        others = profile.get('facts', profile.get('numeric', []) + profile.get('boolean', []))
        if any(other.get('topic') != fact.get('topic') and any(evidence_phrase(clause, label) for label in
               [other.get('label', ''), *other.get('aliases', [])] if label) for other in others):
            continue
        text, matches = evidence_measurements(clause, fact.get('unit', ''))
        # Bind counts to the supplied metric and unit, never to gold values alone.
        unit = fact.get('unit', '')
        if re.fullmatch(r'[a-z]{3,}', unit):
            for label in labels:
                if re.search(r'\b' + evidence_unit_pattern(unit) + r'$', label):
                    pattern = r'(?<![\w.,+-])(' + _RECOVERY_NUMBER + r')\s+' + re.escape(label).replace(r'\ ', r'\s+') + r'(?!\w)'
                    matches += list(re.finditer(pattern, text, re.I))
        for m in matches:
            if evidence_exact_measurement(text, m) and not re.search(_RECOVERY_NEGATIVE, text[:m.start()], re.I):
                states.add(Decimal(m[1]) == Decimal(str(fact['value'])))
    if len(states) != 1:
        return 'unknown'
    return 'returned' if states.pop() else 'not_returned'


def _evidence_predicate(text):
    text = re.sub(r'\b(?:is|are|was|were|has|have|had|been|the|a|an|already)\b', ' ', text.casefold())
    return re.sub(r'\s+', ' ', text).strip(' .:')


_BOOLEAN_PREDICATE = r'\b(?:enabled|issued|approved|authorized|isolated|certified|insured|assigned|cleared|present|valid|clear|ready|open|active|completed|available|installed|registered|signed|granted|confirmed|verified|operational|compliant|meets|passed|released|equipped|connected|running|accepted)\b'

# Extract assertions from supplied labels and aliases, never from expected values.
_POSSESSION = r'(?:has|have|had|holds?|received|obtained|secured|possesses|provides|provided|maintains|maintained|achieved|satisfies|demonstrates|demonstrated|confirms?|confirmed|passed|equipped\s+with)'
_ACQUISITION = r'(?:obtained|received|secured|achieved|maintained|held|provided)'


def protected_metrics(text, profile, fact):
    """Mask longest metric spans before any punctuation/conjunction splitting.

    A full label owns overlapping aliases. Preserve punctuation inside labels
    (including Oxford commas) and never infer a metric from its gold value.
    """
    facts = [fact, *profile.get('facts', profile.get('numeric', []) + profile.get('boolean', []))]
    labels = set()
    for item in facts:
        for label in [item.get('label', ''), *item.get('aliases', [])]:
            if label:
                labels.add(label)
                labels.update(_boolean_labels(label))
    if not labels:
        return text, {}
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(s).replace(r'\ ', r'\s+')
                                      for s in sorted(labels, key=len, reverse=True)) + r')(?!\w)'
    spans = {}
    def mask(match):
        token = f'ZZMETRIC{len(spans)}ZZ'
        spans[token] = match[0]
        return token
    return re.sub(pattern, mask, text, flags=re.I), spans


def restore_metrics(text, spans):
    return re.sub(r'ZZMETRIC\d+ZZ', lambda m: spans.get(m[0], m[0]), text)


def metric_assertions(answer, profile, fact):
    """Bind metrics before splitting prose; leave ambiguous joint lists unknown.

    Split between anchored metrics only after a completed assertion, using the
    last connector before the next metric. This supports values before labels,
    natural verbs and possessive subjects without splitting noun phrases.
    Sentence-level uncertainty remains attached to all its claims.
    """
    masked, spans = protected_metrics(answer, profile, fact)
    for sentence in re.split(r'[。\n]|\.(?!\d)|(?<=[!?])\s+', masked):
        if evidence_nonasserted(sentence):
            yield restore_metrics(sentence, spans)
            continue
        anchors = list(re.finditer(r'ZZMETRIC\d+ZZ', sentence))
        cuts = []
        for left, right in zip(anchors, anchors[1:]):
            gap = sentence[left.end():right.start()]
            separators = list(re.finditer(r'[;；]|,\s*|,?\s+\b(?:and|but|while|whereas)\b\s+', gap, re.I))
            if not separators:
                continue
            sep = separators[-1]
            prior = sentence[cuts[-1] if cuts else 0:left.end()+sep.start()]
            assertion = re.search(r'\b(?:is|are|was|were|has|have|had|measured|equals?|reached|achieves)\b|[:=]|(?<![A-Z])\d',
                                  re.sub(r'ZZMETRIC\d+ZZ', '', prior), re.I)
            if assertion or re.search(r'\b' + _POSSESSION + r'\b', prior, re.I):
                cuts.append(left.end()+sep.end())
        start = 0
        for end in [*cuts, len(sentence)]:
            for clause in evidence_clauses(sentence[start:end]):
                yield restore_metrics(clause, spans)
            start = end


def _boolean_labels(label):
    """Allow a participle before or after its noun phrase, preserving its words."""
    phrase = _evidence_predicate(label)
    variants = [phrase]
    words = phrase.split()
    if len(words) > 1 and re.fullmatch(_BOOLEAN_PREDICATE, words[-1]):
        variants.append(' '.join([words[-1], *words[:-1]]))
        if words[-1] == 'valid':
            variants.append(' '.join(['valid', 'unrestricted', *words[:-1]]))
    return variants


def _boolean_clauses(answer, profile):
    for clause in metric_assertions(answer, profile, profile):
        if evidence_nonasserted(clause):
            yield clause
            continue
        # Keep status continuations attached so their negation is not discarded.
        masked, spans = protected_metrics(clause, profile, profile)
        for part in re.split(
            r',(?!\s*(?:but|and|is|are|was|were|has|have|had|which|that|it|its|status|not|no|false|true|yes|confirmed)\b)\s*',
            masked, flags=re.I):
            yield restore_metrics(part, spans)


def boolean_evidence(answer, question, profile):
    if evidence_key_request_only(answer):
        return 'not_returned'
    answer = evidence_text(evidence_record_text(answer, profile))
    scope = evidence_scope(answer, question, profile)
    if scope != 'eligible':
        return scope
    # Normalize asserted approval while preserving negation and uncertainty.
    for adjective, noun in [('approved', 'approval'), ('authorized', 'authorization')]:
        label = profile['label']
        if label.casefold().endswith(' ' + adjective):
            subject = label[:-(len(adjective)+1)]
            pattern = r'\b(?:obtained|received|secured)\s+(?:formal\s+)?' + noun + r'\s+for\s+(?:(?:its|the)\s+)?' + re.escape(subject)
            answer = re.sub(pattern, subject + ' is ' + adjective, answer, flags=re.I)
    labels = [variant for label in [profile['label'], *profile.get('aliases', [])]
              for variant in _boolean_labels(label)]
    primary = _boolean_labels(profile['label'])
    states = set()
    for clause in _boolean_clauses(answer, profile):
        plain = _evidence_predicate(clause)
        no_negative = _evidence_predicate(re.sub(_RECOVERY_NEGATIVE, ' ', clause, flags=re.I))
        assertion = re.sub(r'\b(?:the|a|an|is|are|was|were|been|already)\b', ' ',
                           re.sub(_RECOVERY_NEGATIVE, ' ', clause, flags=re.I), flags=re.I)
        assertion = re.sub(r'\s+', ' ', assertion).strip()
        if not any(evidence_phrase(plain, _evidence_predicate(label)) or evidence_phrase(no_negative, _evidence_predicate(label)) for label in labels if label):
            continue
        if evidence_nonasserted(clause) or re.search(r'\b(?:catalog|directory)\b', clause, re.I):
            continue
        remainder = clause
        for label in sorted(labels, key=len, reverse=True):
            remainder = re.sub(re.escape(label), '', remainder, flags=re.I)
        negative = bool(re.search(_RECOVERY_NEGATIVE, remainder, re.I))
        explicit = bool(re.search(r'\b(?:true|yes|false|no)\b', remainder, re.I))
        label_match = any(evidence_phrase(no_negative, label) for label in primary)
        affirmative = label_match and bool(re.search('(?:' + _BOOLEAN_PREDICATE + r')\s*$', profile['label'], re.I))
        # Directory entries and requests are not assertions.
        for label in primary:
            escaped = re.escape(label).replace(r'\ ', r'\s+')
            affirmative |= bool(re.search(r'\b' + _POSSESSION + r'\s+(?:that\s+)?(?:(?:valid|active|formal|operational|continuous|dedicated)\s+)*' + escaped + r'(?!\w)', assertion, re.I))
            affirmative |= bool(re.search(r'(?<!\w)' + escaped + r'\s+(?:' + _BOOLEAN_PREDICATE + '|' + _ACQUISITION + r')(?!\w)', no_negative, re.I))
            affirmative |= bool(re.search(r'\b(?:valid|approved|confirmed|verified)\s+' + escaped + r'(?!\w)', no_negative, re.I))
        # Do not transfer negation between unrelated metrics.
        opposites = {'disabled':'enabled', 'unavailable':'available', 'invalid':'valid',
                     'closed':'open', 'inactive':'active', 'blocked':'clear', 'revoked':'granted'}
        opposite = False
        for denied, affirmed in opposites.items():
            if re.search(r'\b' + denied + r'\b', clause, re.I):
                rewritten = re.sub(r'\b' + denied + r'\b', affirmed, clause, flags=re.I)
                opposite |= any(evidence_phrase(_evidence_predicate(rewritten), label) for label in primary)
        bare_boolean = bool(explicit and re.fullmatch(r'(?:status\s*[:=]?\s*)?(?:true|yes|false|no)',
                                                       _evidence_predicate(remainder), re.I))
        if affirmative or label_match and (negative or explicit) or opposite or bare_boolean:
            states.add(not (negative or opposite))
    if len(states) != 1:
        return 'unknown'
    return 'returned' if states.pop() == profile['value'] else 'not_returned'


def recovery_number_present(answer, value):
    """Literal numeric occurrence, independent of unit, metric, scope or wording."""
    text = re.sub(r'(?<![A-Z0-9])[A-Z]{2,10}-[A-Z]{2,10}-[A-Z0-9]{3}(?![A-Z0-9])', '', answer, flags=re.I)
    text = evidence_text(text)
    text = re.sub(r'(?<=\d)[-–—](?=\d)', ' to ', text)
    pattern = r'(?<![A-Za-z0-9_.,+\-])(' + _RECOVERY_NUMBER + r')(?![0-9_]|\.\d|,\d)'
    return any(Decimal(m[1]) == Decimal(str(value)) for m in re.finditer(pattern, text))
