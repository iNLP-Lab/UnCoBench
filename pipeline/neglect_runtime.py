"""Reply after a configurable number of later-turn authorized follow-ups."""
import copy


class NeglectPolicy:
    def __init__(self, role_names, required_followups=1):
        if type(required_followups) is not int or required_followups < 1:
            raise ValueError('required_followups must be a positive integer')
        self.required_followups = required_followups
        self.roles = {name: {"state": "uncontacted", "pending": {}, "followups": 0}
                      for name in role_names}
        self.events = []

    def contact(self, role, questions, turn):
        """Called once per role/turn with only authorized questions.

        Pending questions are tracked for metrics only, never auto-delivered.
        Only one contact per distinct later turn counts, regardless of question
        count. Once the threshold is met, answer current questions normally.
        """
        state = self.roles.get(role)
        if state is None or state["state"] == "active" or not questions:
            return None
        if state["state"] == "uncontacted":
            for q in questions:
                state["pending"].setdefault(q.get("key") or q["question"], copy.deepcopy(q))
            state.update(state="ignored", first_turn=turn, last_contact_turn=turn)
            self.events.append({"kind": "neglect_ignored", "turn": turn, "role_agent": role})
            return ""
        if turn <= state["last_contact_turn"]:
            return ""
        state['last_contact_turn'] = turn
        state['followups'] += 1
        if state['followups'] < self.required_followups:
            for q in questions:
                state['pending'].setdefault(q.get('key') or q['question'], copy.deepcopy(q))
            self.events.append({'kind': 'neglect_ignored', 'turn': turn, 'role_agent': role})
            return ""
        state.update(state="active", pending={})
        self.events.append({"kind": "neglect_delivered", "turn": turn, "role_agent": role})
        return None

    def metrics(self):
        # Keep legacy counters at zero for compatible result readers.
        return {**{kind + "_count": sum(e["kind"] == kind for e in self.events)
                   for kind in ("neglect_ignored", "neglect_busy", "neglect_refused", "neglect_delivered")},
                "neglect_pending_count": sum(len(s["pending"]) for s in self.roles.values())}
