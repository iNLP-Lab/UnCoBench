"""Deterministic follow-up routing; metadata contains no hidden values or target flags."""
import re


def build_followup_records(task):
    roles = {r['role_id']: r['name'] for r in task['roles']}
    candidates = {c['candidate_id']: c['name'] for c in task['candidates']}
    topics = {t['topic_id']: t for group in ('topics', 'distractor_topics', 'supplemental_topics')
              for t in task.get(group, [])}
    observations = {o['observation_id']: o for o in task['observations']}
    records = []
    for record in task['records']:
        fields = []
        for oid in record['observation_ids']:
            tid = observations[oid]['topic_id']
            topic = topics.get(tid, {})
            if topic.get('label'):
                fields.append({'id': tid, 'label': topic['label'], 'aliases': topic.get('aliases', [])})
        records.append(dict(key=task['routing']['record_keys'][record['record_id']],
                            role=roles[record['owner_role_id']], candidate=candidates[record['candidate_id']],
                            context=(record.get('context') or {}).get('value', ''), fields=fields))
    return records


class IncompleteFollowupResolver:
    VERSION = 'rule_followup_v2_english'
    CLARIFY = 'The record and metric cannot be uniquely identified. Put the complete record key and the metric to verify in your question.'

    def __init__(self, records):
        self.records = records
        self.reset()

    def reset(self):
        self.seen = {}
        self.events = []

    def observe(self, role, key, turn):
        if key is not None:
            self.seen.setdefault((role, key), turn)

    @staticmethod
    def normalize(text):
        return re.sub(r'\s+', ' ', text).strip().casefold().replace('’', "'").replace('‑', '-').replace('–', '-')

    @classmethod
    def mentions(cls, text, phrase):
        phrase = cls.normalize(phrase)
        if re.search(r'[\u3400-\u9fff]', phrase):
            return phrase.replace(' ', '') in text.replace(' ', '')
        return bool(re.search(r'(?<![\w])' + re.escape(phrase) + r'(?![\w])', text))

    def resolve(self, role, text, turn):
        text = self.normalize(text)
        available = [r for r in self.records if r['role'] == role]
        if re.search(r'目录|索引列表|key列表|\b(?:catalog(?:ue)?s?|director(?:y|ies)|(?:key|index)\s+lists?)\b', text):
            result = dict(status='catalog', key=None, fields=[])
        else:
            # Match the full role catalog before restricting to previously queried records.
            names = {r['candidate'] for r in available if self.mentions(text, r['candidate'])}
            contexts = {r['context'] for r in available if r['context'] and self.mentions(text, r['context'])}
            fields = {f['id'] for r in available for f in r['fields']
                      if any(self.mentions(text, a) for a in [f['label'], *f['aliases']] if a)}
            full = bool(re.search(r'完整(?:资料|信息|内容|记录)|全部(?:资料|信息|内容)|详细资料|\b(?:complete|full|all|detailed)\s+(?:(?:the|your|available)\s+)*(?:records?|information|details|data)\b', text))
            matches = [r for r in available
                       if self.seen.get((role, r['key']), turn) < turn
                       and r['candidate'] in names
                       and (not contexts or r['context'] in contexts)
                       and (fields <= {f['id'] for f in r['fields']} if fields else full)]
            # Ambiguous references require a key; do not infer pronouns or fuzzy matches.
            unique = len(names) == 1 and len(contexts) <= 1 and len(matches) == 1 and (fields or full)
            result = dict(status='resolved' if unique else 'clarify',
                          key=matches[0]['key'] if unique else None, fields=sorted(fields), full=full)
        self.events.append(dict(turn=turn, role_agent=role, question=text, **result))
        return result

    def catalog(self, role):
        return 'Complete record directory (supply a key to obtain facts):\n' + '\n'.join(
            r['key'] + '：' + r['candidate'] + ('；' + r['context'] if r['context'] else '')
            + '; Metrics: ' + '、'.join(f['label'] for f in r['fields'])
            for r in self.records if r['role'] == role)

    def metrics(self):
        return dict(incomplete_followup_protocol=self.VERSION,
                    incomplete_keyless_followup_count=len(self.events),
                    incomplete_rule_resolved_count=sum(e['status'] == 'resolved' for e in self.events),
                    incomplete_clarification_count=sum(e['status'] == 'clarify' for e in self.events),
                    incomplete_followup_routing=list(self.events))
