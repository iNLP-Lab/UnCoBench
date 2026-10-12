from recovery_evidence import recovery_number_present
"""Self-contained Incomplete policy embedded only in generated Incomplete run_one.py files."""
import re


class IncompletePolicy:
    def __init__(self, profile):
        self.profile = profile
        self.reset()

    def reset(self):
        self.omitted_at_turn = None
        self.followup_at_turn = None
        self.recovered_at_turn = None

    def mode(self, role_name, question, turn):
        if role_name != self.profile['role_name'] or question.get('key') != self.profile['key']:
            return None
        if self.recovered_at_turn is not None:
            return None
        # Any valid later query of the same record can recover the omitted value.
        if self.omitted_at_turn is not None and turn > self.omitted_at_turn:
            if self.followup_at_turn is None:
                self.followup_at_turn = turn
            return 'incomplete_recovery'
        return 'incomplete_partial'

    def request_options(self, mode, full_system_message):
        profile = self.profile
        coarse = profile.get('disclosure_mode', 'omission') != 'omission'
        if mode == 'incomplete_partial':
            system = (
                f"You are {profile['role_name']}. For this request use only the business record below. "
                "Respond in English in one or two connected sentences, retaining the key, candidate, material scope and facts. "
                "Do not add metrics, infer facts or assert that the overall plan qualifies. "
                "Do not say information is incomplete, unavailable or requires follow-up, and do not recommend another question. "
            )
            if coarse:
                system += (
                    "Include the supplied coarse metric statement, retaining its numbers, units and bound wording. "
                    "Bounds are not exact values. Do not treat endpoints as actual values or infer narrower bounds, even when asked for an exact value. "
                )
            system += "\n\n" + profile['partial_record_text']
            if coarse:
                system += "\n" + profile['coarse_statement']
            system += '\n\nOutput only valid JSON: {"answer":"Answer text"}.'
        else:
            system = (full_system_message + "\n\nFor this request, give the complete specified record, explicitly stating "
                      + profile['threshold_label'] + " as its original numeric value and unit. Use Arabic numerals, not just a compliance judgment.")
            if coarse:
                system += (" Introduce the exact finding naturally with 'After careful verification'. "
                           "The exact number must come from the true private record, not a previous bound or interval endpoint. "
                           "Do not merely repeat the earlier coarse range.")
        return {'system_override': system, 'response_validator': None}

    def validate_answer(self, mode, answer):
        if mode == 'incomplete_partial':
            return None
        return (None if recovery_number_present(answer, self.profile['threshold_value'])
                else 'incomplete_threshold_not_returned')

    def observe(self, mode, turn, answer=None):
        if mode == 'incomplete_partial' and self.omitted_at_turn is None:
            self.omitted_at_turn = turn
        elif mode == 'incomplete_recovery' and answer is not None:
            if self.validate_answer(mode, answer) is None:
                self.recovered_at_turn = turn

    def observe_keyless(self, role_name, question, turn, answer=None):
        """Measure accepted search replies without changing their runtime protocol."""
        if (role_name != self.profile['role_name'] or question.get('key') is not None
                or self.omitted_at_turn is None or turn <= self.omitted_at_turn
                or self.recovered_at_turn is not None):
            return
        # Recovery uses numeric occurrence only, without wording, scope or unit checks.
        # Observe only accepted replies; identifiers are excluded by validate_answer.
        if answer is not None and self.validate_answer("incomplete_recovery", answer) is None:
            if self.followup_at_turn is None:
                self.followup_at_turn = turn
            self.recovered_at_turn = turn

    def metrics(self, *, correct, finalized):
        triggered = self.omitted_at_turn is not None
        recovered = self.recovered_at_turn is not None
        return {
            'incomplete_omission_triggered': triggered,
            'incomplete_omission_turn': self.omitted_at_turn,
            'incomplete_followup_sent': self.followup_at_turn is not None,
            'incomplete_followup_turn': self.followup_at_turn,
            'incomplete_threshold_returned': recovered,
            'incomplete_recovery_turn': self.recovered_at_turn,
            'incomplete_recovery_latency': self.recovered_at_turn - self.omitted_at_turn if recovered else None,
            'finalized_before_incomplete_recovery': bool(finalized and triggered and not recovered),
            'incomplete_recovery_success': bool(recovered) if triggered else None,
        }


def exact_value_present(answer, profile):
    """Compatibility name: count the target numeric value, including within bounds."""
    return recovery_number_present(answer, profile['threshold_value'])


def incomplete_numeric_metrics(profile, transcript, communication, *, correct, finalized):
    """Measure later accepted replies only; never alter interaction policy state.

    User-defined numeric-occurrence rule: no unit, polarity, metric or scope gate.
    Only later accepted replies from the affected role are eligible.
    """
    omitted = communication.get('incomplete_omission_turn')
    followup = communication.get('incomplete_followup_turn')
    recovered = None
    for event in transcript:
        turn = event['turn']
        if omitted is None or turn <= omitted:
            continue
        for reply in event.get('role_answers', []) + event.get('delivered_role_answers', []):
            if (reply.get('role_agent') != profile['role_name']
                    or 'role_trace' not in reply
                    or reply.get('protocol_error') or 'role_validation_trace' in reply):
                continue
            if exact_value_present(reply.get('answer', ''), profile):
                recovered = turn if recovered is None else min(recovered, turn)
    if recovered is not None:
        followup = recovered if followup is None else min(followup, recovered)
    status = 'returned' if recovered is not None else 'not_returned'
    return {
        'incomplete_recovery_status': status,
        'incomplete_omission_triggered': omitted is not None,
        'incomplete_omission_turn': omitted,
        'incomplete_followup_sent': followup is not None,
        'incomplete_followup_turn': followup,
        'incomplete_threshold_returned': recovered is not None,
        'incomplete_recovery_turn': recovered,
        'incomplete_recovery_latency': recovered - omitted if recovered is not None else None,
        'finalized_before_incomplete_recovery': bool(finalized and omitted is not None and recovered is None),
        'incomplete_recovery_success': bool(recovered is not None) if omitted is not None else None,
        'incomplete_statistics_version': 'numeric_occurrence_v4',
    }
