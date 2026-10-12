from __future__ import annotations

import re
import math
from typing import Any

from key_routing import ABBREVIATION_PATTERN, KEY_PATTERN
from numeric_rules import OPERATIONS, validate_numeric_rule


ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
INTERNAL_KIND_PATTERN = re.compile(r"(?:kind\s*=|candidate_holder|\bdistractor\b|\brouter\b)", re.I)
EVALUATION_RELEVANCE_HINT_PATTERN = re.compile(
    r"(?:干扰(?:项|信息|角色)?|看似(?:相关|影响)|不属于正式|非正式(?:标准|条件|指标)|"
    r"不影响(?:最终)?(?:判断|结论)|不纳入(?:正式)?(?:判断|评估)|(?i:distractor|seemingly relevant|unofficial criteri|does not affect (?:the )?(?:final )?decision))"
)
NUMERIC_TYPES = {"integer", "number"}

NUMERIC_OPERATIONS = set(OPERATIONS)
TASK_SCHEMA_VERSION = "ceg-v10-mixed"
ERROR_TYPES = (
    "temporal", "geographic", "measurement_basis",
    "aggregation_window", "environment_version",
)
GEOGRAPHY_LEVELS = {"country", "province", "city"}
LEGACY_GEOGRAPHY_CATALOG = {
    "country": (
        "中国", "美国", "日本", "德国", "法国", "英国", "加拿大", "澳大利亚",
        "印度", "巴西", "新加坡", "韩国",
    ),
    "province": (
        "浙江省", "广东省", "江苏省", "山东省", "四川省", "湖北省", "福建省",
        "河南省", "河北省", "安徽省", "湖南省", "江西省", "辽宁省", "陕西省",
        "云南省", "贵州省", "山西省", "海南省", "甘肃省", "青海省",
    ),
    "city": (
        "杭州市", "广州市", "南京市", "深圳市", "成都市", "武汉市", "苏州市",
        "宁波市", "厦门市", "青岛市", "长沙市", "郑州市",
    ),
}


GEOGRAPHY_CATALOG = {
    "country": ("China", "United States", "Japan", "Germany", "France", "United Kingdom", "Canada", "Australia", "India", "Brazil", "Singapore", "South Korea"),
    "province": ("Zhejiang", "Guangdong", "Jiangsu", "Shandong", "Sichuan", "Hubei", "Fujian", "Henan", "Hebei", "Anhui", "Hunan", "Jiangxi", "Liaoning", "Shaanxi", "Yunnan", "Guizhou", "Shanxi", "Hainan", "Gansu", "Qinghai"),
    "city": ("Hangzhou", "Guangzhou", "Nanjing", "Shenzhen", "Chengdu", "Wuhan", "Suzhou", "Ningbo", "Xiamen", "Qingdao", "Changsha", "Zhengzhou"),
}
GEOGRAPHY_VALID_VALUES = {level: (*values, *LEGACY_GEOGRAPHY_CATALOG[level])
                         for level, values in GEOGRAPHY_CATALOG.items()}


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_evidence_context(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must define evidence_context")
    for field in ("source", "scope", "measurement"):
        _nonempty(value.get(field), f"{label} evidence_context.{field}")


def _validate_domain(domain: Any, *, topic_id: str, value_type: str) -> None:
    if not isinstance(domain, list) or len(domain) < 2:
        raise ValueError(f"topic {topic_id} must have a finite domain with at least two values")
    if len({repr(value) for value in domain}) != len(domain):
        raise ValueError(f"topic {topic_id} domain contains duplicates")
    if value_type == "boolean" and any(not isinstance(value, bool) for value in domain):
        raise ValueError(f"boolean topic {topic_id} must contain only boolean values")
    if value_type in NUMERIC_TYPES and any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in domain
    ):
        raise ValueError(f"numeric topic {topic_id} must contain only numeric values")


def validate_ontology(ontology: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ontology, dict):
        raise ValueError("ontology must be an object")
    roles = ontology.get("roles")
    if not isinstance(roles, list) or not 5 <= len(roles) <= 7:
        raise ValueError("ontology roles must contain 5 to 7 items")
    role_ids: set[str] = set()
    role_abbreviations: set[str] = set()
    capabilities: set[str] = set()
    capability_roles: dict[str, set[str]] = {}
    for role in roles:
        role_id = _nonempty(role.get("role_id"), "role_id")
        if role_id in role_ids or not ID_PATTERN.fullmatch(role_id):
            raise ValueError(f"invalid or duplicate role_id: {role_id}")
        role_ids.add(role_id)
        _nonempty(role.get("name"), "role name")
        responsibility = _nonempty(role.get("responsibility"), "role responsibility")
        if EVALUATION_RELEVANCE_HINT_PATTERN.search(responsibility):
            raise ValueError("role responsibility must not reveal evaluation relevance")
        role_abbreviation = _nonempty(role.get("role_abbreviation"), f"role {role_id} role_abbreviation")
        business_abbreviation = _nonempty(role.get("business_abbreviation"), f"role {role_id} business_abbreviation")
        if not ABBREVIATION_PATTERN.fullmatch(role_abbreviation) or role_abbreviation in role_abbreviations:
            raise ValueError(f"invalid or duplicate role_abbreviation: {role_abbreviation}")
        if not ABBREVIATION_PATTERN.fullmatch(business_abbreviation):
            raise ValueError(f"invalid business_abbreviation: {business_abbreviation}")
        secondary = role.get("secondary_business")
        if not isinstance(secondary, dict):
            raise ValueError(f"role {role_id} must define secondary_business")
        secondary_code = secondary.get("business_abbreviation", "")
        if not ABBREVIATION_PATTERN.fullmatch(str(secondary_code)) or secondary_code == business_abbreviation:
            raise ValueError("secondary_business must use a different valid business_abbreviation")
        _nonempty(secondary.get("title"), "secondary_business title")
        secondary_topic = secondary.get("topic")
        if not isinstance(secondary_topic, dict):
            raise ValueError("secondary_business must define a substantive topic")
        _nonempty(secondary_topic.get("label"), "secondary_business topic label")
        value_type = secondary_topic.get("value_type")
        if value_type not in NUMERIC_TYPES | {"boolean"}:
            raise ValueError("secondary_business topic must be numeric or boolean")
        _validate_domain(secondary_topic.get("domain"), topic_id=f"secondary_{role_id}", value_type=value_type)
        if value_type in NUMERIC_TYPES:
            _nonempty(secondary_topic.get("unit"), "secondary_business topic unit")
        elif secondary_topic.get("unit", "") != "":
            raise ValueError("secondary_business boolean unit must be empty")
        _validate_evidence_context(secondary_topic.get("evidence_context"), "secondary_business topic")
        role_abbreviations.add(role_abbreviation)
        if "holds_candidates" in role or "routes_candidates" in role or role_id in {"plan_admin", "coordinator", "review_coordinator"}:
            raise ValueError("direct ontology must not define routing roles or flags")
        role_capabilities = role.get("capabilities")
        if not isinstance(role_capabilities, list):
            raise ValueError("role capabilities must be a list")
        capabilities.update(str(item) for item in role_capabilities)
        for capability in role_capabilities:
            capability_roles.setdefault(str(capability), set()).add(role_id)
    candidates = ontology.get("candidate_names")
    if not isinstance(candidates, list) or len(candidates) != 3 or len(set(candidates)) != 3:
        raise ValueError("ontology must define exactly three unique candidate names")
    for field in ("title", "domain", "problem", "positive_label", "negative_label", "candidate_type"):
        _nonempty(ontology.get(field), field)

    topics = ontology.get("topics")
    if not isinstance(topics, list) or len(topics) < 3:
        raise ValueError("ontology must define at least three topics")
    topic_ids: set[str] = set()
    condition_owners: set[str] = set()
    topic_by_id: dict[str, dict[str, Any]] = {}
    for topic in topics:
        topic_id = _nonempty(topic.get("topic_id"), "topic_id")
        if topic_id in topic_ids or not ID_PATTERN.fullmatch(topic_id):
            raise ValueError(f"invalid or duplicate topic_id: {topic_id}")
        topic_ids.add(topic_id)
        topic_by_id[topic_id] = topic
        _nonempty(topic.get("label"), "topic label")
        value_type = _nonempty(topic.get("value_type"), f"topic {topic_id} value_type")
        if value_type not in NUMERIC_TYPES | {"boolean"}:
            raise ValueError(f"formal topic {topic_id} must be numeric or boolean")
        _validate_domain(topic.get("domain"), topic_id=topic_id, value_type=value_type)
        if value_type in NUMERIC_TYPES:
            _nonempty(topic.get("unit"), f"numeric topic {topic_id} unit")
        elif topic.get("unit", "") != "":
            raise ValueError(f"boolean topic {topic_id} unit must be empty")
        _validate_evidence_context(topic.get("evidence_context"), f"topic {topic_id}")
        owner = _nonempty(topic.get("owner_capability"), "owner_capability")
        if owner not in capabilities:
            raise ValueError(f"topic owner capability is unavailable: {owner}")
        if len(capability_roles.get(owner, set())) != 1:
            raise ValueError(f"topic owner capability must map to exactly one Role: {owner}")
        if "operator" in topic:
            condition_owners.add(owner)
            if topic["operator"] not in {"eq", "neq", "gt", "gte", "lt", "lte"}:
                raise ValueError(f"unsupported operator for {topic_id}")
            if "threshold" not in topic:
                raise ValueError(f"condition topic {topic_id} is missing threshold")
        aliases = topic.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
            raise ValueError(f"invalid aliases for {topic_id}")
    condition_roles = {role_id for owner in condition_owners for role_id in capability_roles[owner]}
    if len(condition_roles) < 4:
        raise ValueError("conditions must be distributed across at least four different Roles")
    if not 5 <= sum("operator" in topic for topic in topics) <= 7:
        raise ValueError("ontology must define 5 to 7 atomic conditions")
    numeric_rule = ontology.get("numeric_rule")
    validate_numeric_rule(numeric_rule, topics)
    numeric_topic_ids = numeric_rule["topic_ids"]
    numeric_topics = [topic_by_id[topic_id] for topic_id in numeric_topic_ids]
    numeric_owners = {topic["owner_capability"] for topic in numeric_topics}
    if len(numeric_owners) < 2:
        raise ValueError("numeric_rule topics must belong to different capabilities")
    numeric_owner_roles = {
        role_id
        for owner in numeric_owners
        for role_id in capability_roles.get(owner, set())
    }
    if len(numeric_owner_roles) < 2:
        raise ValueError("numeric_rule topics must belong to different Roles")
    decision_capabilities = condition_owners | numeric_owners
    distractors = ontology.get("distractor_topics", [])
    if not isinstance(distractors, list) or not 1 <= len(distractors) <= 2:
        raise ValueError("ontology must define 1 to 2 distractor topics")
    for topic in distractors:
        topic_id = _nonempty(topic.get("topic_id"), "distractor topic_id")
        if topic_id in topic_ids or not ID_PATTERN.fullmatch(topic_id):
            raise ValueError(f"invalid or duplicate topic_id: {topic_id}")
        topic_ids.add(topic_id)
        _nonempty(topic.get("label"), f"distractor topic {topic_id} label")
        aliases = topic.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
            raise ValueError(f"invalid aliases for {topic_id}")
        owner = topic.get("owner_capability")
        if owner not in capabilities:
            raise ValueError("distractor owner capability is unavailable")
        owner_roles = capability_roles.get(str(owner), set())
        if len(owner_roles) != 1:
            raise ValueError(f"distractor owner capability must map to exactly one Role: {owner}")
        if owner in decision_capabilities:
            raise ValueError("distractor owner capability must not belong to a decision role")
        value_type = topic.get("value_type")
        if value_type not in NUMERIC_TYPES | {"boolean"}:
            raise ValueError("distractor topic must be numeric or boolean")
        _validate_domain(topic.get("domain"), topic_id=topic_id, value_type=value_type)
        if value_type in NUMERIC_TYPES:
            _nonempty(topic.get("unit"), f"numeric distractor {topic_id} unit")
            if topic.get("preference") not in {"higher", "lower"}:
                raise ValueError("numeric distractor preference must be higher or lower")
        elif topic.get("unit", "") != "":
            raise ValueError(f"boolean distractor {topic_id} unit must be empty")
        _validate_evidence_context(topic.get("evidence_context"), f"distractor topic {topic_id}")
    from incomplete_setting import validate_incomplete_ontology
    validate_incomplete_ontology(ontology)
    return ontology


def normalize_topic(ontology: dict[str, Any], text: str) -> str | None:
    normalized = "".join(str(text).lower().split())
    for topic in [*ontology.get("topics", []), *ontology.get("distractor_topics", [])]:
        names = [topic["topic_id"], topic["label"], *topic.get("aliases", [])]
        if normalized in {"".join(str(name).lower().split()) for name in names}:
            return topic["topic_id"]
    return None


def validate_task_graph(task: dict[str, Any]) -> dict[str, Any]:
    from task_solver import derive_gold, validate_p1, validate_p3

    roles = task.get("roles")
    if not isinstance(roles, list) or not 5 <= len(roles) <= 7:
        raise ValueError("task roles must contain 5 to 7 items")
    if task.get("schema_version") != TASK_SCHEMA_VERSION:
        raise ValueError("incompatible task schema; regenerate with v8")
    kinds = [role.get("kind") for role in roles]
    if not set(kinds) <= {"decision", "output", "distractor"} or kinds.count("decision") < 2:
        raise ValueError("direct tasks require business roles and at least two decision roles")
    if not 1 <= kinds.count("distractor") <= 2:
        raise ValueError("task must contain 1 to 2 distractor roles")
    candidates = task.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        raise ValueError("task must contain exactly three candidates")
    candidate_ids = {item.get("candidate_id") for item in candidates}
    if len(candidate_ids) != 3:
        raise ValueError("task candidate IDs must be unique")
    visible_strings = [
        task.get("scenario", {}).get("title", ""),
        task.get("scenario", {}).get("problem", ""),
        task.get("scenario", {}).get("question", ""),
    ]
    visible_strings.extend(str(item.get("rendered_text", "")) for item in task.get("observations", []))
    if any(INTERNAL_KIND_PATTERN.search(text) for text in visible_strings):
        raise ValueError("model-visible text contains internal role kind")
    role_ids = {role["role_id"] for role in roles}
    if any(p.get('owner_role_id') not in role_ids for p in task.get('predicates', [])):
        raise ValueError("predicate references unknown owner Role")
    for observation in task.get("observations", []):
        if observation["reporter_role_id"] not in role_ids:
            raise ValueError("observation references unknown role")
        if observation.get("predicate_id") is None:
            role_kind = next(role["kind"] for role in roles if role["role_id"] == observation["reporter_role_id"])
            if role_kind == "decision" and observation.get("observation_type") == "distractor":
                raise ValueError("distractor observation must not belong to a decision role")
    for topic in task.get("topics", []):
        covered = {
            item["candidate_id"] for item in task.get("predicates", [])
            if item.get("topic_id") == topic["topic_id"]
        }
        if covered != candidate_ids:
            raise ValueError(f"topic {topic['topic_id']} must cover all three candidates")
    condition_ids = {c['topic_id'] for c in task.get('constraints', [])}
    condition_roles = {p['owner_role_id'] for p in task.get('predicates', []) if p['topic_id'] in condition_ids}
    if not 5 <= len(task.get('constraints', [])) <= 7 or len(condition_ids) != len(task.get('constraints', [])):
        raise ValueError("task must define 5 to 7 distinct atomic conditions")
    if len(condition_roles) < 4:
        raise ValueError("conditions must be distributed across at least four different Roles")
    records = task.get("records")
    routing = task.get("routing")
    if not isinstance(records, list) or not records or not isinstance(routing, dict):
        raise ValueError("task must define records and routing")
    record_by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = _nonempty(record.get("record_id"), "record_id")
        if record_id in record_by_id:
            raise ValueError(f"duplicate record_id: {record_id}")
        if record.get("owner_role_id") not in role_ids or record.get("candidate_id") not in candidate_ids:
            raise ValueError(f"record {record_id} references unknown role or candidate")
        if not ABBREVIATION_PATTERN.fullmatch(str(record.get("business_abbreviation", ""))):
            raise ValueError(f"record {record_id} has invalid business_abbreviation")
        if not isinstance(record.get("observation_ids"), list) or "next_record_ids" in record:
            raise ValueError(f"record {record_id} has invalid references")
        record_by_id[record_id] = record
    record_keys = routing.get("record_keys")
    if not isinstance(record_keys, dict) or set(record_keys) != set(record_by_id):
        raise ValueError("routing record_keys must cover every record")
    if len(set(record_keys.values())) != len(record_keys) or any(
        not isinstance(key, str) or not KEY_PATTERN.fullmatch(key) for key in record_keys.values()
    ):
        raise ValueError("routing keys must be unique v2-shaped keys")
    key_suffixes = [key.rsplit("-", 1)[1] for key in record_keys.values()]
    if len(key_suffixes) != len(set(key_suffixes)):
        raise ValueError("routing key suffixes must be globally unique")
    role_by_id = {role["role_id"]: role for role in roles}
    for record_id, key in record_keys.items():
        owner = role_by_id[record_by_id[record_id]["owner_role_id"]]
        if not key.startswith(owner["role_abbreviation"] + "-" + record_by_id[record_id]["business_abbreviation"] + "-"):
            raise ValueError(f"record key owner prefix mismatch: {record_id}")
    for role in roles:
        owned_records = [r for r in records if r["owner_role_id"] == role["role_id"]]
        if len({r["business_abbreviation"] for r in owned_records}) < 2:
            raise ValueError("every Role must have at least two business catalogs")
        business_titles: dict[str, str] = {}
        for record in owned_records:
            title = _nonempty(record.get("business_title"), "business_title")
            business = record["business_abbreviation"]
            if business_titles.setdefault(business, title) != title:
                raise ValueError("one business abbreviation must identify one information-point title")
    if routing.get("mode") != "direct" or any(k in routing for k in (
            "bootstrap_role_id", "router_role_id", "bootstrap_record_ids", "bootstrap_ideal_round", "candidate_routes")):
        raise ValueError("only direct record directories are supported")
    entries = routing.get("candidate_records", [])
    if len(entries) != 3 or {e.get("candidate_id") for e in entries} != candidate_ids:
        raise ValueError("directory must cover each candidate exactly once")
    advertised = set()
    for entry in entries:
        ids = entry.get("record_ids", [])
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("candidate directory must contain distinct records")
        if any(r not in record_by_id or record_by_id[r]["candidate_id"] != entry["candidate_id"] for r in ids):
            raise ValueError("directory records must belong to the candidate")
        decoys = entry.get("distractor_record_ids", [])
        if not decoys or not set(decoys) <= set(ids) or any(
                role_by_id[record_by_id[r]["owner_role_id"]]["kind"] != "distractor" for r in decoys):
            raise ValueError("directory must retain distractor records")
        advertised.update(ids)
    catalog_only_record_ids = routing.get("catalog_only_record_ids", [])
    catalog = set(catalog_only_record_ids)
    if len(catalog) != len(catalog_only_record_ids) or catalog & advertised or catalog | advertised != set(record_by_id):
        raise ValueError("records must partition into public directory and private catalog")
    required_record_ids = routing.get("required_record_ids", [])
    if not required_record_ids or len(required_record_ids) != len(set(required_record_ids)) or not set(required_record_ids) <= advertised:
        raise ValueError("required records must be distinct public records")
    if routing.get("required_key_ideal_rounds") != {record_keys[r]: 1 for r in required_record_ids}:
        raise ValueError("initial direct queries have ideal round 1")
    from runtime_settings import TURN_BUDGETS
    setting = task.get("setting", "reliable")
    if setting not in TURN_BUDGETS:
        raise ValueError("unsupported direct task setting")
    ideal, maximum = TURN_BUDGETS[setting]
    if routing.get("finalize_ideal_round") != ideal or task.get("runtime", {}).get("max_turns") != maximum:
        raise ValueError("task budget does not match setting")
    if setting in {"incomplete", "mixed"}:
        from incomplete_setting import validate_incomplete_profile
        validate_incomplete_profile(task)
    if setting in {"missed", "mixed"}:
        selected = task.get("neglect_profile", {}).get("role_ids", [])
        eligible = {record_by_id[r]["owner_role_id"] for r in required_record_ids
                    if role_by_id[record_by_id[r]["owner_role_id"]]["kind"] != "distractor"}
        if len(selected) != 1 or not set(selected) <= eligible:
            raise ValueError("neglect requires exactly one necessary business role")
    if setting == "mixed":
        if not task.get('intervention_plan'):
            raise ValueError("mixed requires a joint intervention plan")
        affected = [task.get('error_pair', {}).get('affected_role_id'),
                    task['incomplete_profile']['role_id'], *task['neglect_profile']['role_ids']]
        if None in affected or len(set(affected)) != 3:
            raise ValueError("mixed requires three distinct unreliable Roles")
    if task.get('intervention_plan'):
        from mixed_setting import validate_intervention_plan
        validate_intervention_plan(task)
    observation_ids = {
        item["observation_id"] for item in task.get("observations", [])
    }
    record_observation_ids = [item for record in records for item in record["observation_ids"]]
    if set(record_observation_ids) != observation_ids or len(record_observation_ids) != len(set(record_observation_ids)):
        raise ValueError("records must cover every observation exactly once")
    validate_numeric_rule(task.get("numeric_rule"), task["topics"])
    derived = derive_gold(task)
    pair = task.get("error_pair")
    if pair is not None:
        if not isinstance(pair, dict):
            raise ValueError("error_pair must be an object")
        target_id = pair.get("target_record_id")
        alternate_id = pair.get("alternate_record_id")
        if pair.get("error_type") not in ERROR_TYPES:
            raise ValueError("error_pair uses an unsupported error_type")
        if target_id not in record_by_id or alternate_id not in record_by_id:
            raise ValueError("error_pair records must exist")
        target_record, alternate_record = record_by_id[target_id], record_by_id[alternate_id]
        if any(
            target_record[field] != alternate_record[field]
            for field in ("owner_role_id", "candidate_id", "record_family_id")
        ):
            raise ValueError("error_pair records must belong to one Role, candidate, and evidence family")
        mode = pair.get("routing_mode")
        different_business = target_record["business_abbreviation"] != alternate_record["business_abbreviation"]
        if mode not in {"same_business", "cross_business"} or different_business != (mode == "cross_business"):
            raise ValueError("error_pair routing_mode must match its business catalogs")
        target_context = target_record.get("context", {})
        alternate_context = alternate_record.get("context", {})
        if (
            target_context.get("error_type") != pair.get("error_type")
            or alternate_context.get("error_type") != pair.get("error_type")
            or target_context.get("value") == alternate_context.get("value")
        ):
            raise ValueError("error_pair contexts must express one differing dimension")
        if pair.get("error_type") == "geographic":
            target_level = target_context.get("geography_level")
            alternate_level = alternate_context.get("geography_level")
            if (
                target_level not in GEOGRAPHY_LEVELS
                or alternate_level not in GEOGRAPHY_LEVELS
                or target_level != alternate_level
            ):
                raise ValueError("geographic contexts must use the same supported geography level")
            if (
                target_context.get("value") not in GEOGRAPHY_VALID_VALUES[target_level]
                or alternate_context.get("value") not in GEOGRAPHY_VALID_VALUES[alternate_level]
            ):
                raise ValueError("geographic context values must match their declared catalog level")
        expected_catalog = alternate_id if task.get("setting") not in {"misaligned", "mixed"} else target_id
        advertised_sibling = target_id if task.get("setting") not in {"misaligned", "mixed"} else alternate_id
        if expected_catalog not in catalog_only_record_ids or advertised_sibling in catalog_only_record_ids:
            raise ValueError("setting must hide the non-advertised sibling record in the Role catalog")
    distractor_by_id = {item["topic_id"]: item for item in task.get("distractor_topics", [])}
    forbidden_decoy_ids = {
        item["topic_id"] for item in task.get("constraints", [])
    } | set(task.get("numeric_rule", {}).get("topic_ids", [])) | {
        item["topic_id"] for item in task.get("predicates", [])
    }
    overlap = set(distractor_by_id) & forbidden_decoy_ids
    if overlap:
        raise ValueError(f"distractor topics must not affect formal evaluation: {sorted(overlap)}")
    for topic_id, topic in distractor_by_id.items():
        observations = [
            item for item in task.get("observations", [])
            if item.get("observation_type") == "distractor" and item.get("topic_id") == topic_id
        ]
        values = [item["claimed_value"] for item in observations]
        if len(observations) != len(task.get("candidates", [])):
            raise ValueError(f"distractor topic {topic_id} must cover every candidate")
        if any(value not in topic["domain"] for value in values):
            raise ValueError(f"distractor topic {topic_id} contains a value outside its domain")
        if len({repr(value) for value in values}) < 2:
            raise ValueError(f"distractor topic {topic_id} must use at least two distinct values")
        if derived["qualified_candidate_id"] is not None:
            if topic["value_type"] == "boolean":
                preferred = True
            elif topic["preference"] == "higher":
                preferred = max(topic["domain"])
            else:
                preferred = min(topic["domain"])
            if not any(
                item["candidate_id"] != derived["qualified_candidate_id"]
                and item["claimed_value"] == preferred
                for item in observations
            ):
                raise ValueError(f"distractor topic {topic_id} must favor a non-gold candidate")
    if task.get("gold") not in (None, derived):
        raise ValueError("declared gold does not match derived gold")
    task["gold"] = derived
    p1, p3 = validate_p1(task), validate_p3(task)
    task["validation"] = {"p1": p1, "p3": p3}
    return task
