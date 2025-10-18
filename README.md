README — training_logs models
# OUT OF DATE - TBD UPDATES
This README documents the Python dataclass models used to represent training session logs and their JSON serialization contract.

Overview
--------
The `src.models` module provides dataclass-based models that map to the NoSQL JSONC training session schema. Key classes:

- `TrainingSession` — top-level session metadata and list of `Exercise` objects.
- `Exercise` — describes a single exercise with `warmupSets` and `workingSets`.
- `WorkingSet` / `WarmupSet` — per-set data; `WorkingSet.repCount` uses `RepCount` with `full` and `partial` values.
- `Goal`, `RepRange` — planned targets for an exercise.
- `FailureTechnique` and detail classes (`MyoRepDetails`, `LLPDetails`, `StaticDetails`, `DropSetDetails`) — advanced techniques used on RPE 10 sets.
- `RepQualityAssessment` — enum for rep quality: `good`, `bad`, `perfect`, `learning`.

Serialization contract
----------------------
- All `to_dict()` implementations return plain Python dictionaries using the canonical JSON key names used in the NoSQL documents (camelCase and some TitleCase where present in the schema).

- Omission rules (compact serializer):
  - Fields with a value of `None` are omitted from the output.
  - Empty lists are omitted from the output.
  - This applies recursively: nested dicts and lists are compacted too.

- Example: if `warmupSets` is an empty list or `None`, it will not appear in the serialized exercise object.

Field mapping highlights
------------------------
- Python attribute -> JSON key examples:
  - `weight_kg` -> `weightKg`
  - `rep_count` (WarmupSet) -> `repCount`
  - `rep_count` (WorkingSet) -> `repCount` (object: `{"full": int, "partial": int}`)
  - `rep_quality_assessment` -> `repQuality` (string, one of `good|bad|perfect|learning`)
  - `failure_technique` -> `failureTechnique` (object with `type` and `details`)

Enums and parsing
-----------------
- `RepQualityAssessment` accepts case-insensitive input and is serialized as a lowercase string.
- `FailureTechnique._parse_type_case_insensitive` accepts several aliases and normalizes to internal `FailureTechniqueType`.

Examples
--------
Below are example JSON outputs produced by `TrainingSession.to_dict()` (after calling `json.dumps(...)` it will be valid JSON). The examples use dummy values.

1) Full example (all optional fields present)

{
  "dataModelVersion": "0.1.0",
  "dataModelType": "training_session_log",
  "_id": "session_123",
  "userId": "user_1",
  "userName": "Apoorva Sharma",
  "date": "2025-10-16T12:00:00Z",
  "phase": 2,
  "week": 5,
  "isDeloadWeek": false,
  "focus": "upper-strength",
  "exercises": [
    {
      "Order": 1,
      "Name": "Barbell Bench Press",
      "targetMuscleGroups": ["chest", "triceps"],
      "warmupSets": [
        {"set": 1, "weightKg": 20, "repCount": 5},
        {"set": 2, "weightKg": 40, "repCount": 3}
      ],
      "workingSets": [
        {
          "set": 1,
          "weightKg": 80,
          "repCount": {"full": 5, "partial": 0},
          "rpe": 8,
          "repQuality": "good"
        },
        {
          "set": 2,
          "weightKg": 82.5,
          "repCount": {"full": 5, "partial": 1},
          "rpe": 10,
          "repQuality": "perfect",
          "failureTechnique": {
            "type": "MyoReps",
            "details": {"miniSets": [{"miniSet": 1, "repCount": {"full": 3}}]}
          }
        }
      ],
      "formCues": ["brace the core"],
      "currentGoal": {"weightKg": 85, "sets": 3, "repRange": {"min": 5, "max": 6}, "restMinutes": 2}
    }
  ],
  "sessionDurationMinutes": 75
}

2) Minimal example (omit empty or None fields)

{
  "dataModelVersion": "0.1.0",
  "dataModelType": "training_session_log",
  "_id": "session_124",
  "userId": "user_1",
  "userName": "Apoorva Sharma",
  "date": "2025-10-16T12:00:00Z",
  "phase": 2,
  "week": 5,
  "isDeloadWeek": false,
  "focus": "upper-strength",
  "exercises": [
    {
      "Order": 1,
      "Name": "Barbell Bench Press",
      "workingSets": [
        {"set": 1, "weightKg": 80, "repCount": {"full": 5}}
      ]
    }
  ],
  "sessionDurationMinutes": 45
}

Notes and guidance
------------------
- If you need to preserve empty lists in the output for downstream systems, we can adjust `_clean_none_and_empty` to keep specific list fields. Right now the implementation omits all empty lists globally.

- Failure technique aliases: we accept multiple alias spellings when parsing input; the output uses the `FailureTechniqueType` enum value (e.g. "MyoReps" or "DropSet"). If you'd prefer a different canonical output label (e.g. "Myo-repCount"), we can map enum -> canonical string on serialization.

- Validation rules are enforced in constructors and from_dict methods. Invalid inputs raise `TrainingLogValidationError`.

If you'd like, I can:
- Add a short `examples/` folder with programmatic snippets that build model objects and print JSON.
- Provide a script to migrate legacy JSON documents into the canonical structure.

