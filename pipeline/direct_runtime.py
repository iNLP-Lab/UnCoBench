"""Direct-access main loop, embedded in standalone runtimes."""

def run_direct(self, task):
    self._semantic_enabled_roles = set()
    self.empty_observation_count = 0
    self.neglect_policy = NeglectPolicy(self.runtime_config['communication_role_names'],
                                       self.runtime_config.get('neglect_required_followups', 1))
    self.communication_events = self.neglect_policy.events
    self.delivered_messages = []
    if self.incomplete_policy:
        self.incomplete_policy.reset()
        self.followup_resolver.reset()
    for role in self.role_agents.values():
        role.reset_history()
    self.messages = [{'role': 'system', 'content': self.system_message}, {'role': 'user', 'content': task}]
    transcript = []
    consecutive_errors = 0

    def answer(role, question):
        result, _ = self._answer_question(role, question)
        return dict(result, role_agent=role, question=dict(question))

    def publish(replies):
        for reply in replies:
            if reply.pop('authorized_exact', False):
                self._semantic_enabled_roles.add(reply['role_agent'])
        if replies:
            self.messages.append({'role': 'user', 'content': '\n'.join(
                r['role_agent'] + '：' + r['answer'] for r in replies)})

    for turn in range(1, self.max_turns + 1):
        self.current_turn = turn
        event = {'turn': turn, 'role_answers': []}
        try:
            action = self._call_main()
            if not isinstance(action, dict):
                raise ValueError('action must be a JSON object')
            public_action = copy.deepcopy(action)
            kind = action.get('action')
            if kind == 'finalize':
                if action.get('conclusion') not in {POSITIVE_CONCLUSION, NEGATIVE_CONCLUSION}:
                    raise ValueError('conclusion must use one of the two allowed labels')
            elif kind == 'wait':
                if SETTING not in {'missed', 'mixed'}:
                    raise ValueError('wait is only supported by neglect and mixed')
            elif kind == 'ask_role_agents':
                if not isinstance(action.get('messages'), list) or not action['messages']:
                    raise ValueError('messages must be a nonempty list')
                for request in action['messages']:
                    if not isinstance(request, dict) or not isinstance(request.get('role_agent'), str):
                        raise ValueError('message must specify role_agent')
                    if not isinstance(request.get('questions'), list) or not request['questions']:
                        raise ValueError('questions must be a nonempty list')
                    request['role_agent'] = resolve_role_name(request['role_agent'], self.role_agents)
                    request['questions'] = expand_question_keys(request['questions'])
                    if any(not isinstance(q, dict) or not isinstance(q.get('question'), str) or not q['question'].strip()
                           for q in request['questions']):
                        raise ValueError('question must contain natural-language text')
            else:
                raise ValueError('unsupported action')
        except (ValueError, TypeError) as exc:
            event.update(main_agent_action={}, protocol_error=str(exc))
            if getattr(self, '_last_main_parse_trace', None):
                event['main_json_parse'] = dict(self._last_main_parse_trace)
            transcript.append(event)
            self.messages.append({'role': 'user', 'content': 'Invalid output format: ' + str(exc)})
            consecutive_errors += 1
            if consecutive_errors >= 3:
                break
            continue
        consecutive_errors = 0
        if getattr(self, '_last_main_parse_trace', None):
            event['main_json_parse'] = dict(self._last_main_parse_trace)
        event['main_agent_action'] = action
        transcript.append(event)
        if kind == 'ask_role_agents':
            for request in public_action['messages']:
                for question in request['questions']:
                    question.pop('key', None)
        self.messages.append({'role': 'assistant', 'content': json.dumps(public_action, ensure_ascii=False)})
        if kind == 'finalize':
            return self._result({'conclusion': action['conclusion'], 'numeric_result': action.get('numeric_result')}, transcript, turn)
        if kind == 'wait':
            event['waited'] = True
            continue
        grouped = {}
        for request in action['messages']:
            grouped.setdefault(request['role_agent'], []).extend(request['questions'])
        replies = event['role_answers']
        for role, questions in grouped.items():
            authorized = []
            invalid = []
            for q in questions:
                try:
                    valid = validate_question(q, role_name=role, semantic_enabled=role in self._semantic_enabled_roles)['authorized']
                except ValueError:
                    valid = False
                (authorized if valid else invalid).append(q)
            replies.extend(answer(role, q) for q in invalid)
            response = self.neglect_policy.contact(role, authorized, turn)
            if response is None:
                replies.extend(answer(role, q) for q in authorized)
            else:
                event.setdefault('deferred_role_requests', []).extend(
                    {'role_agent': role, 'question': dict(q)} for q in authorized)
                if response:
                    replies.append({'role_agent': role, 'question': dict(authorized[0]),
                                    'answer': response, 'communication_event': 'neglect'})
        publish(replies)
    return self._result({'conclusion': None, 'numeric_result': None}, transcript, None)
