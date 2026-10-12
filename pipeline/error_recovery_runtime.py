"""Pure Error recovery measurement; embedded in generated Error runtimes."""
import re
from decimal import Decimal
from recovery_evidence import numeric_evidence, boolean_evidence

ERROR_RECOVERY_VERSION = 'task_labeled_facts_v8_scoped_assertions'


def build_error_recovery_profile(graph):
    pair = graph['error_pair']
    records = {r['record_id']: r for r in graph['records']}
    obs = {o['observation_id']: o for o in graph['observations']}
    target = [obs[i] for i in records[pair['target_record_id']]['observation_ids']]
    alternate = {obs[i]['topic_id']: obs[i]['claimed_value']
                 for i in records[pair['alternate_record_id']]['observation_ids']}
    changed = [o for o in target if o['claimed_value'] != alternate[o['topic_id']]]
    topics = {t['topic_id']: t for t in graph['topics']}
    def fact(o):
        t = topics[o['topic_id']]
        return dict(topic=o['topic_id'], value=o['claimed_value'], label=t['label'],
                    aliases=t.get('aliases', []), unit=t.get('unit', ''))
    numeric = [fact(o) for o in changed
               if type(o['claimed_value']) in (int, float)]
    # Recovery requires every perturbed fact, including Boolean facts.
    boolean = [fact(o) for o in changed if type(o['claimed_value']) is bool]
    profile = dict(role_name=next(r['name'] for r in graph['roles'] if r['role_id']==pair['affected_role_id']),
                target_key=pair['target_key'], alternate_key=pair['alternate_key'],
                target_context=pair['target_context'], alternate_context=pair['alternate_context'],
                candidate=next(c['name'] for c in graph['candidates'] if c['candidate_id']==pair['affected_candidate_id']),
                other_candidates=[c['name'] for c in graph['candidates'] if c['candidate_id']!=pair['affected_candidate_id']],
                numeric=numeric, boolean=boolean)
    if graph.get('language') == 'en':
        profile['language'] = 'en'
        profile['facts'] = [dict(topic=t['topic_id'],label=t['label'],aliases=t.get('aliases', [])) for t in graph['topics']]
    return profile


def validate_error_recovery_profile(profile):
    """Generation gate: every new English metric must accept canonical truth
    and reject an explicit different value. This is compatibility validation,
    not a claim that every natural-language paraphrase can be interpreted.
    """
    if profile.get('language') != 'en':
        return
    facts = profile['numeric'] + profile['boolean']
    if not facts:
        raise ValueError('Error recovery profile has no perturbed facts')
    question = {'key': profile['target_key']}
    for fact in facts:
        is_bool = type(fact['value']) is bool
        for correct in (True, False):
            value = fact['value'] if correct else (not fact['value'] if is_bool else Decimal(str(fact['value'])) + 1)
            answer = f"{fact['label']} = {str(value).lower()} {fact.get('unit', '')}"
            state = (boolean_evidence(answer, question, dict(profile, **fact)) if is_bool else
                     numeric_evidence(answer, question, profile, fact))
            if state != ('returned' if correct else 'not_returned'):
                raise ValueError(f"Error recovery cannot score canonical metric {fact['topic']!r}: {state}")


def error_numeric_present(answer, value):
    text = re.sub(r'[A-Z]{2,10}-[A-Z]{2,10}-[A-Z0-9]{3}', '', answer, flags=re.I)
    # Treat thousands separators as part of a number, not as value boundaries.
    text = re.sub(r'(?<![\w.,])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,]|\.\d)',
                  lambda m: m[0].replace(',', ''), text)
    return Decimal(str(value)) in [Decimal(x) for x in re.findall(
        r'(?<![A-Za-z0-9.,+-])[+-]?\d+(?:\.\d+)?(?![A-Za-z0-9,]|\.\d)', text)]


def _legacy_boolean_reply(event, profile):
    """Tri-state extraction for certification validity, with scope attribution.

    A clear statement that status cannot be determined means no fact returned.
    Unknown is reserved for text the rules cannot confidently interpret.
    """
    if not event['eligible']:
        return 'not_returned'
    answer = event['answer']
    question = event['question']
    combined = question.get('question', '') + '\n' + answer
    keyed = question.get('key') == profile['target_key']
    if profile['alternate_context'] in answer or any(c in answer for c in profile['other_candidates']):
        return 'not_returned'
    identity = keyed or profile['target_key'] in combined or profile['candidate'] in combined
    scope = keyed or profile['target_context'] in combined
    if profile['target_context'] == '评估日时点':
        scope = scope or bool(re.search(r'评估日(?:当天|时点)?', combined))
    metric = keyed or bool(re.search(r'冷链(?:运输)?(?:认证|资质)', combined))
    if not (identity and scope and metric):
        return 'unknown'
    values = []
    explicit_unavailable = False
    for clause in re.split(r'[；;。\n]', answer):
        # Only validity assertions count; audit-log dates do not.
        if not re.search(r'有效|无效|过期|状态为[是否]', clause):
            continue
        if re.search(r'无法|不能.*(?:确定|判定)|未提供|未给出|未.*确定|不明确|可能|推测|并非每天|至少有一天|是否', clause):
            explicit_unavailable = True
            continue
        negative = bool(re.search(r'无效|已过期|不在有效期|未处于有效期|不处于有效期|状态为否', clause))
        positive = bool(re.search(r'处于有效期内|(?<!不)在有效期内|状态为是|(?:认证|资质)(?:为|是)?有效', clause))
        if negative:
            values.append(False)
        elif positive:
            values.append(True)
    if len(set(values)) > 1:
        return 'unknown'
    if values:
        return 'returned' if values[0] == profile['value'] else 'not_returned'
    return 'not_returned' if explicit_unavailable else 'unknown'



def _plain(text):
    text = text.casefold().replace("n't", ' not')
    text = re.sub(r'\b(?:is|are|was|were|has|have|had|been|the|a|an|already)\b', '', text)
    return re.sub(r'[\s\W_]+', '', text)


def _recovery_mentions(text, phrase):
    if not phrase:
        return False
    if re.search(r'[\u3400-\u9fff]', phrase):
        return phrase in text
    return bool(re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', text, re.I))


def boolean_reply(event, profile):
    """Conservative task-label matching. Unsupported paraphrases remain unknown.

    No decision depends on the spelling of an internal topic ID. Scope/identity
    are established by a target key, or explicitly in a keyless question/reply.
    Chinese support is retained for existing benchmark transcripts.
    """
    if profile.get('language') == 'en':
        return boolean_evidence(event['answer'], event['question'], profile) if event['eligible'] else 'not_returned'
    if not profile.get('label'):
        return _legacy_boolean_reply(event, profile)
    if not event['eligible']:
        return 'not_returned'
    answer = re.sub(r"\bcan['’]t\b", 'cannot', event['answer'], flags=re.I)
    answer = re.sub(r"n['’]t\b", ' not', answer, flags=re.I)
    question = event['question']
    combined = question.get('question', '') + '\n' + answer
    if (profile.get('alternate_context') and _recovery_mentions(answer, profile['alternate_context'])
            or any(_recovery_mentions(answer, c) for c in profile.get('other_candidates', []))):
        return 'not_returned'
    keyed = question.get('key') == profile['target_key']
    referenced = profile['target_key'] in combined
    if not (keyed or referenced or (_recovery_mentions(combined, profile.get('candidate', ''))
                                   and _recovery_mentions(combined, profile.get('target_context', '')))):
        return 'unknown'
    label = profile['label']
    aliases = [label, *profile.get('aliases', [])]
    positive = r'通过|获批|批准|生效|有效|畅通|就绪|下达|启用|开启|完成|达标|达到|具备|已布设|已接入|已签|已验收|无重大|已备案|已投运|是|true|approved|passed|valid|clear|ready|released|enabled|active|completed|available|installed|registered|signed|granted|confirmed|operational|compliant|meets|yes'
    uncertain = r'无法|不能确定|未提供|未给出|不明确|可能|推测|是否|\b(?:unknown|uncertain|unclear|may|might|could|should|would|must|expected|possibly|whether|cannot|unable|unconfirmed|not confirmed)\b'
    negative = r'未|不|没有|无效|受阻|(?<![A-Za-z])(?:not|no|never|false|invalid|blocked|failed|denied|unavailable|unapproved|revoked|inactive|disabled|noncompliant)(?![A-Za-z])|(?:为|是|结果)[：:]?否'
    states = set()
    for clause in re.split(r'[；;。\n]|(?<!\d)[.!?](?!\d)', answer):
        normalized = _plain(clause)
        # Preserve negation across predicate boundaries.
        without_negative = _plain(re.sub(negative, '', clause, flags=re.I))
        matches = [a for a in aliases if _plain(a) in normalized or _plain(a) in without_negative]
        if not matches:
            continue
        if re.search(uncertain, clause, re.I):
            continue
        if re.search(r'目录|\b(?:catalog|directory)\b', clause, re.I):
            continue
        # A directory label alone is not a positive assertion.
        if not re.search(positive, clause, re.I) and not re.search(negative, clause, re.I):
            continue
        remainder = clause
        for a in sorted(matches, key=len, reverse=True):
            remainder = re.sub(re.escape(a), '', remainder, flags=re.I)
        is_negative = bool(re.search(negative, remainder, re.I))
        states.add(not is_negative)
    if len(states) != 1:
        return 'unknown'
    return 'returned' if states.pop() == profile['value'] else 'not_returned'


def recovery_success(metrics, correct):
    """Keep unsupported evidence out of binary recovery-rate denominators."""
    if metrics.get('error_recovery_status') == 'unknown':
        return None
    return bool(metrics.get('error_fact_returned') and correct)

def error_recovery_metrics(profile, transcript):
    """Return fact recovery independently of the final task answer and key echo."""
    omitted = followup = recovered = None
    seen = set()
    evidence = []
    unknown = False
    method = None
    for event in transcript:
        turn = event['turn']
        replies = event.get('role_answers', []) + event.get('delivered_role_answers', [])
        accepted = [a for a in replies if a.get('role_agent') == profile['role_name']
                    and 'role_trace' in a and not a.get('protocol_error')
                    and 'role_validation_trace' not in a]
        if omitted is None and any(a.get('question', {}).get('key') == profile['alternate_key'] for a in accepted):
            omitted = turn
        if omitted is None or turn <= omitted:
            continue
        action = event.get('main_agent_action', {})
        if any(m.get('role_agent') == profile['role_name']
               and any(q.get('key') in (None, profile['target_key']) for q in m.get('questions', []) if isinstance(q, dict))
               for m in action.get('messages', []) if isinstance(m, dict)):
            followup = turn if followup is None else followup
        for answer in accepted:
            question = answer.get('question', {})
            if question.get('key') not in (None, profile['target_key']):
                continue
            followup = turn if followup is None else followup
            event_status = []
            for fact in profile['numeric']:
                state = (numeric_evidence(answer.get('answer', ''), question, profile, fact)
                         if profile.get('language') == 'en' else
                         'returned' if error_numeric_present(answer.get('answer', ''), fact['value']) else 'not_returned')
                event_status.append(dict(topic=fact['topic'], status=state))
                unknown |= state == 'unknown'
                if state == 'returned':
                    seen.add(fact['topic'])
            for fact in profile['boolean']:
                state = boolean_reply(dict(eligible=True, question=question, answer=answer.get('answer', '')),
                                      dict(profile, **fact))
                event_status.append(dict(topic=fact['topic'], status=state))
                unknown |= state == 'unknown'
                if state == 'returned':
                    seen.add(fact['topic'])
            evidence.append(dict(turn=turn, key=question.get('key'), facts=event_status))
            required = {f['topic'] for f in profile['numeric'] + profile['boolean']}
            if required and required <= seen and recovered is None:
                recovered = turn
                method = 'target_key_query' if question.get('key') else 'keyless_query'
    status = 'returned' if recovered is not None else 'unknown' if unknown else 'not_returned'
    finalized = any(t.get('main_agent_action', {}).get('action') == 'finalize' for t in transcript)
    return dict(error_fact_returned=None if status == 'unknown' else recovered is not None, error_recovery_status=status,
                error_recovery_unknown=status == 'unknown', error_recovery_evidence=evidence,
                mismatch_key_queried=omitted is not None, mismatch_key_turn=omitted,
                recovery_query_sent=followup is not None, recovery_query_turn=followup,
                recovery_turn=recovered, recovery_method=method,
                recovery_latency=recovered-omitted if recovered is not None else None,
                finalized_before_recovery=None if status == 'unknown' else bool(finalized and omitted is not None and recovered is None),
                recovery_metrics_version=ERROR_RECOVERY_VERSION)
