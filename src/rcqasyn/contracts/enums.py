from enum import StrEnum


class QualityDimension(StrEnum):
    """Quality dimensions; their scores are not interchangeable.

    Primary scopes are usually field/record for validity and coherence, record/subgroup
    for authenticity/privacy/fairness, and dataset for diversity/distributional fidelity/
    downstream utility. A dimension may be evaluated at another explicitly recorded scope.
    """

    SCHEMA_VALIDITY = "schema_validity"
    CONSTRAINT_VALIDITY = "constraint_validity"
    FACTUAL_VALIDITY = "factual_validity"
    LOGICAL_CONSISTENCY = "logical_consistency"
    SEMANTIC_COHERENCE = "semantic_coherence"
    AUTHENTICITY = "authenticity"
    PRIVACY = "privacy"
    FAIRNESS = "fairness"
    DIVERSITY = "diversity"
    DISTRIBUTIONAL_FIDELITY = "distributional_fidelity"
    DOWNSTREAM_UTILITY = "downstream_utility"


class Verdict(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionAction(StrEnum):
    ACCEPT = "accept"
    REPAIR = "repair"
    REVALIDATE = "revalidate"
    REGENERATE = "regenerate"
    REJECT = "reject"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(StrEnum):
    REFERENCE_DATASET = "reference_dataset"
    KNOWLEDGE_BASE = "knowledge_base"
    DOCUMENT = "document"
    API = "api"
    DETERMINISTIC_RULE = "deterministic_rule"
    HUMAN_ANNOTATION = "human_annotation"
    EXTERNAL_DATABASE = "external_database"
    WEB = "web"
    PAPER = "paper"
    DATASET = "dataset"
    USER = "user"
    SYSTEM = "system"
    OTHER = "other"
