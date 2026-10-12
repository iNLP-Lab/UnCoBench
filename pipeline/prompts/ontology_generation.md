Generate the business-semantic Ontology for a multi-agent collaboration benchmark. Return only one JSON object, with the exact field names and types below. All natural-language values must be English, including names, labels, aliases, problem, units and evidence contexts. Use English conclusion labels such as Exists/Does not exist, Proceed/Do not proceed or Select/Do not select, as appropriate to the decision.

The few-shot example demonstrates JSON fields, types and structural relationships only. Do not copy its domain, objective, candidates, roles, metrics, condition combination or narrative, or merely substitute names, numbers or synonyms. In particular do not reuse the software-release example or the compatibility + response-enabled + repair-time combination. Design a new business meaning for the numeric formula while honoring requested_operation.

scenario_references provides all eight optional inspirations; scenario_suggestion is an optional rotating suggestion. You are actively encouraged to create scenarios beyond the eight references and to explore coherent cross-domain scenarios. Seek fresh business goals, decision objects and operational contexts, especially when familiar themes recur in recent_scenarios. You may also use a reference or the rotating suggestion when it supports a substantively different task. Neither references nor query_hints are a whitelist or mandatory quota. Preserve the structural and business contract while exploring new scenarios. recent_scenarios contains historical domain and brief problem summaries to avoid, not examples to continue. Vary concrete situations, objectives, decision objects, roles, conditions and requested quantities. An empty history is not permission to copy this example.

{
  "title": "Software release assessment",
  "domain": "Release management",
  "problem": "Determine whether exactly one release plan satisfies deployment compatibility, enabled high-risk vulnerability response, average high-risk remediation time of at most 24 h, operational handover readiness, and approved resource budget. If so, report its available release capacity: nominal capacity minus reserved capacity.",
  "positive_label": "Exists",
  "negative_label": "Does not exist",
  "candidate_type": "release plan",
  "candidate_names": [
    "Blue-green deployment",
    "Rolling deployment",
    "Canary deployment"
  ],
  "roles": [
    {
      "role_id": "engineering",
      "name": "Engineering lead",
      "responsibility": "Maintains compatibility and nominal capacity records",
      "role_abbreviation": "ENG",
      "business_abbreviation": "COMP",
      "capabilities": [
        "engineering_review"
      ],
      "secondary_business": {
        "business_abbreviation": "LOAD",
        "title": "Load testing",
        "topic": {
          "label": "Peak burst instance count",
          "value_type": "integer",
          "domain": [
            160,
            180,
            200
          ],
          "unit": "instances",
          "evidence_context": {
            "source": "Load test report",
            "scope": "Candidate short-burst load tests",
            "measurement": "Maximum supported instance count during a short load peak"
          }
        }
      }
    },
    {
      "role_id": "security",
      "name": "Security lead",
      "responsibility": "Maintains response enablement and remediation time records",
      "role_abbreviation": "SEC",
      "business_abbreviation": "AUD",
      "capabilities": [
        "security_review"
      ],
      "secondary_business": {
        "business_abbreviation": "DRILL",
        "title": "Security drills",
        "topic": {
          "label": "Drill coverage",
          "value_type": "integer",
          "domain": [
            60,
            80,
            100
          ],
          "unit": "%",
          "evidence_context": {
            "source": "Security drill report",
            "scope": "Candidate incident-response exercises",
            "measurement": "Completed exercise scenarios as a percentage of planned scenarios"
          }
        }
      }
    },
    {
      "role_id": "finance",
      "name": "Resource budget lead",
      "responsibility": "Maintains mandatory reserved capacity and budget approvals",
      "role_abbreviation": "FIN",
      "business_abbreviation": "CAP",
      "capabilities": [
        "capacity_budget"
      ],
      "secondary_business": {
        "business_abbreviation": "COST",
        "title": "Operating costs",
        "topic": {
          "label": "Monthly operating cost",
          "value_type": "integer",
          "domain": [
            12,
            18,
            24
          ],
          "unit": "USD",
          "evidence_context": {
            "source": "Operations cost estimate",
            "scope": "One standard operating month",
            "measurement": "Total compute and operations expenditure"
          }
        }
      }
    },
    {
      "role_id": "marketing",
      "name": "Marketing lead",
      "responsibility": "Maintains executive pilot support records",
      "role_abbreviation": "MKT",
      "business_abbreviation": "SUP",
      "capabilities": [
        "market_context"
      ],
      "secondary_business": {
        "business_abbreviation": "TRAIN",
        "title": "Rollout training",
        "topic": {
          "label": "Training coverage",
          "value_type": "integer",
          "domain": [
            60,
            80,
            100
          ],
          "unit": "%",
          "evidence_context": {
            "source": "Training attendance register",
            "scope": "Business staff involved in candidate rollout",
            "measurement": "Trained staff as a percentage of required participants"
          }
        }
      }
    },
    {
      "role_id": "operations",
      "name": "Operations lead",
      "responsibility": "Maintains operational handover and staffing records",
      "role_abbreviation": "OPS",
      "business_abbreviation": "READY",
      "capabilities": [
        "operations_readiness"
      ],
      "secondary_business": {
        "business_abbreviation": "LOAD",
        "title": "Load testing",
        "topic": {
          "label": "Peak burst instance count",
          "value_type": "integer",
          "domain": [
            160,
            180,
            200
          ],
          "unit": "instances",
          "evidence_context": {
            "source": "Load test report",
            "scope": "Candidate short-burst load tests",
            "measurement": "Maximum supported instance count during a short load peak"
          }
        }
      }
    }
  ],
  "topics": [
    {
      "topic_id": "compatible",
      "label": "Deployment compatibility",
      "aliases": [
        "Compatibility"
      ],
      "value_type": "boolean",
      "domain": [
        false,
        true
      ],
      "unit": "",
      "owner_capability": "engineering_review",
      "operator": "eq",
      "threshold": true,
      "evidence_context": {
        "source": "Compatibility test report",
        "scope": "Critical production dependencies",
        "measurement": "Whether all critical components passed compatibility testing"
      }
    },
    {
      "topic_id": "response_enabled",
      "label": "High-risk response process enabled",
      "aliases": [
        "Response enablement"
      ],
      "value_type": "boolean",
      "domain": [
        false,
        true
      ],
      "unit": "",
      "owner_capability": "security_review",
      "operator": "eq",
      "threshold": true,
      "evidence_context": {
        "source": "Response configuration register",
        "scope": "The release version",
        "measurement": "The enablement switch for high-risk vulnerability response"
      }
    },
    {
      "topic_id": "high_risk_fix_hours",
      "label": "Average high-risk remediation time",
      "aliases": [
        "High-risk remediation duration"
      ],
      "value_type": "integer",
      "domain": [
        12,
        24,
        36,
        48
      ],
      "unit": "h",
      "owner_capability": "security_review",
      "operator": "lte",
      "threshold": 24,
      "evidence_context": {
        "source": "Remediation timing report",
        "scope": "All high-risk vulnerabilities in the release version",
        "measurement": "Mean time from confirmation to remediation and verified closure"
      }
    },
    {
      "topic_id": "nominal_capacity",
      "label": "Nominal release capacity",
      "aliases": [
        "Nominal capacity"
      ],
      "value_type": "integer",
      "domain": [
        100,
        120,
        140
      ],
      "unit": "instances",
      "owner_capability": "engineering_review",
      "numeric": true,
      "evidence_context": {
        "source": "Capacity load-test report",
        "scope": "Peak release window",
        "measurement": "Maximum stable instance count"
      }
    },
    {
      "topic_id": "reserved_capacity",
      "label": "Reserved capacity",
      "aliases": [
        "Capacity reservation"
      ],
      "value_type": "integer",
      "domain": [
        10,
        20,
        30
      ],
      "unit": "instances",
      "owner_capability": "capacity_budget",
      "numeric": true,
      "evidence_context": {
        "source": "Resource budget register",
        "scope": "This release cycle",
        "measurement": "Instances reserved and unavailable for release"
      }
    },
    {
      "topic_id": "operations_ready",
      "label": "Operational handover ready",
      "aliases": [
        "Handover readiness"
      ],
      "value_type": "boolean",
      "domain": [
        false,
        true
      ],
      "unit": "",
      "owner_capability": "operations_readiness",
      "operator": "eq",
      "threshold": true,
      "evidence_context": {
        "source": "Release readiness checklist",
        "scope": "This release plan",
        "measurement": "Approval of operational handover readiness"
      }
    },
    {
      "topic_id": "budget_approved",
      "label": "Resource budget approved",
      "aliases": [
        "Budget approval"
      ],
      "value_type": "boolean",
      "domain": [
        false,
        true
      ],
      "unit": "",
      "owner_capability": "capacity_budget",
      "operator": "eq",
      "threshold": true,
      "evidence_context": {
        "source": "Release readiness checklist",
        "scope": "This release plan",
        "measurement": "Approval of the resource budget"
      }
    }
  ],
  "numeric_rule": {
    "topic_ids": [
      "nominal_capacity",
      "reserved_capacity"
    ],
    "operation": "difference",
    "precision": 0,
    "unit": "instances"
  },
  "distractor_topics": [
    {
      "topic_id": "executive_support",
      "label": "Executive pilot support",
      "aliases": [
        "Pilot support"
      ],
      "value_type": "integer",
      "domain": [
        35,
        62,
        88
      ],
      "unit": "%",
      "owner_capability": "market_context",
      "preference": "higher",
      "evidence_context": {
        "source": "Project intention survey",
        "scope": "Managers participating in the review",
        "measurement": "Percentage explicitly supporting a pilot"
      }
    }
  ],
  "incomplete_condition": {
    "boolean_topic_id": "response_enabled",
    "threshold_topic_id": "high_risk_fix_hours"
  }
}

Business and structural contract:
- Choose the business objective before metrics and roles. Numeric conditions should measure a relevant business capability, not default to response/recovery time. Other roles' conditions should reflect independent business needs, not gratuitous certificates. Production quality, purchasing, fulfillment, maintenance, training, venue operations and energy management are examples, not limits.
- Do not default to enabled feature + recovery-time threshold + nominal minus reserved capacity. Vary total cost, duration, supply, remaining budget and resources, using the allowed cross-role operations.
- `problem`, `positive_label` and `negative_label` must express the same decision. A question about whether a unique eligible candidate exists uses Exists/Does not exist; action labels require a question about that action. Do not mechanically swap synonyms for diversity. Exactly one candidate meeting all formal conditions gives the positive conclusion; none gives the negative conclusion. For action decisions, explicitly make satisfying these conditions sufficient for action, with no extra approval. Positive results report that candidate's requested numeric value. No ranking, candidate combinations or undefined criteria.
- `candidate_names` contains exactly three distinct meaningful strings, not objects. All three participate. Names must describe distinct real-world plans, entity types or strategies consistent with candidate_type. Do not use invented codenames, brand-like names or proper names that fail to distinguish the options. No A/B/C, 1/2/3, Plan A, Supplier 1 or other ordinal-only labels.
- `roles` contains 5 to 7 business roles. Required fields: role_id, name, responsibility, role_abbreviation, business_abbreviation, capabilities, secondary_business. No candidate-management or routing roles; do not output holds_candidates/routes_candidates. Python publishes the candidate directory directly.
- Responsibilities objectively describe held business information. Do not reveal evaluation relevance with phrases such as distractor, seemingly relevant, unofficial criterion or does not affect the decision.
- role_abbreviation and business_abbreviation are 2–10 uppercase letters. Role abbreviations are unique. Python generates complete keys and random suffixes; never generate them yourself. role_id must be a descriptive English snake_case identifier reflecting the responsibility, never r1, role_01 or agent_2. topic_id also uses lowercase snake_case starting with a letter.
- Every role has an independent secondary_business with a distinct abbreviation, nonempty business title and substantive topic (label, value_type, domain, unit, evidence_context). No empty historical placeholders. Secondary business does not enter formal conditions or numeric_rule. Same-business records share a title/abbreviation and become one information point; distinct businesses have different abbreviations.
- There are 5 to 7 formal atomic condition topics, related by flat AND, across at least four distinct role_ids; multiple capabilities of one role do not count as separate roles. Operand-only and distractor roles do not count toward these four.
- Each topic has topic_id, label, aliases, value_type, domain, unit, owner_capability and evidence_context. value_type is boolean/integer/number; domain is a JSON array with at least two distinct discrete values. All numeric values are finite. Numeric units are nonempty; boolean units are empty.
- evidence_context contains nonempty source, scope and measurement: concise source name, actual applicable objects/time range and necessary measurement definition (average/maximum, gross/net, start/end). No generic placeholders or redundant process narrative. Preserve distinctions that change the meaning of a fact.
- Conditions additionally contain operator and threshold; operators are eq/neq/gt/gte/lt/lte. At least one is a genuine numeric threshold using gt/gte/lt/lte, with satisfying and failing domain values and a nonempty unit. No degenerate count <= 0 or count = 0 existence tests, or all-boolean conditions.
- `incomplete_condition` is required: boolean_topic_id and threshold_topic_id refer to two formal conditions held by the same role/capability. The boolean is eq true and describes existence or enabling only; the numeric condition is an independent real threshold. Do not fold numeric compliance into the boolean. Do not reveal incomplete, hidden information or recovery mechanisms in public names, problem, labels or contexts.
- `numeric_rule.topic_ids` references at least two distinct non-condition numeric topics held by at least two distinct roles and capabilities. Actual values belong to the unique eligible candidate and are assigned by Python. Set numeric=true on operand topics.
- `distractor_topics` contains 1–2 numeric/boolean topics owned by independent roles with no conditions or operands. Include topic_id, label, aliases, value_type, domain, unit, owner_capability and evidence_context; numeric distractions also specify preference=higher/lower. No reused formal IDs and no participation in conditions or numeric_rule. Distractions should plausibly look useful; Python assigns them to favor a non-gold candidate.
- Do not output candidate truth values, Gold, role kind, noisy facts, raw records, routing IDs, complete keys or random suffixes.

Numeric contract (eight operations):
- First identify the unique eligible candidate, then compute its value. Never combine or rank candidates.
- Common fields: ordered distinct topic_ids, operation, precision (integer 0–6), unit. Round only the final result, with ties to even. Values and domains must be finite, not booleans, NaN or Infinity.
- Each operand must have a business meaning and varying different roles' operands must be able to change the rounded answer. No zero weights, constant-zero products or rounding that eliminates collaboration.
- Canonical symbolic units support * and at most one /, e.g. USD/item times item gives USD. Use identical unit names/scales for the same dimension; no implicit conversion of USD to thousands of USD, or min to h. Dimensionless results use 1. Percent inputs use their stated numerical convention; do not implicitly divide by 100.
- Weights, tier boundaries and rates are public constants; explain their business meaning in problem. Do not retain parameters belonging to a different operation. Honor requested_operation when supplied.
1. sum: at least two operands, same units as the result.
2. difference: exactly two operands, first minus second, same units as the result.
3. average: sum divided by operand count, same units; only equally weighted observations with the same basis, not rates with differing sample sizes.
4. ratio: exactly two operands, first divided by second; denominator domain excludes zero. Same-unit ratios use result unit 1; do not multiply by 100 or output percent. Different units cancel algebraically (USD/item).
5. product: at least two operands; result dimensions equal their product, e.g. USD/item times item gives USD.
6. weighted_sum: weights is one finite positive dimensionless value per topic_id. Sum weight[i]*value[i]; do not divide by total weight. Weights need not sum to one. All operands and result share a unit.
7. sum_minus: subtract_count identifies the final operands to subtract from the sum of preceding operands; at least two additions and one subtraction, all same units.
8. piecewise: sum nonnegative same-unit quantities from at least two roles, then charge only the quantity in each tier at that tier's rate, starting from zero. Never charge all units at the highest applicable rate. Additional fields: rate_unit and tiers. At least two tiers, each with exactly upper_bound and rate; positive finite upper bounds strictly increase, final upper_bound is null. Rates are finite and positive with at least two distinct rates. Quantity unit times rate_unit equals result unit. Possible total-domain minimum and maximum must strictly straddle at least one boundary. Example: total 120 kWh with tiers 100 at 2 USD/kWh then unlimited at 3 costs 260 USD; exactly 100 costs 200 USD.


English scenario design and locale conventions:
- Design the scenario directly in natural English. Use recognizable job titles, concrete decision objects and idiomatic business descriptions; do not preserve Chinese sentence order, translated administrative jargon or names that only make sense in a Chinese source text. English does not require a US setting: choose a coherent locale appropriate to the task.
- Keep organizations, locations, currency, dates and measurement conventions consistent with the chosen locale. State the applicable jurisdiction when a condition depends on local practice. Supply any eligibility rule as a self-contained scenario fact; do not require outside knowledge of real regulations.
- Use unambiguous dates (April 2026, 17 September 2026, or YYYY-MM-DD), explicit time zones when relevant, and currency codes such as USD, CNY or EUR instead of an ambiguous dollar sign. Distinguish duration from calendar dates and business days from calendar days. Never silently convert currency or measurement systems.
- Choose one canonical unit spelling and scale for each quantity (for example min, h, kg, USD/item) and use it consistently in the schema. Unit symbols are case-sensitive. English pluralization belongs in prose, not alternative schema unit tokens. A percentage input of 7 means 7 percentage points on its stated scale, not an implicit 0.07 operand.
- Give metrics natural noun-phrase aliases that an English speaker could use in follow-up questions, including useful full forms of abbreviations. Aliases must name the same quantity and preserve its scope and polarity; they must not reveal relevance or the answer. Boolean labels should state an affirmative proposition (for example Backup enabled), with true meaning that proposition holds. Avoid double negatives.
- Candidate names must be distinctive in full, not merely nested extensions such as Harbor Hall and Harbor Hall Annex. Positive and negative conclusion labels must form a clear English pair answering the exact question; avoid lexical double negatives or an unexplained yes/no question.
