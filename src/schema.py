"""Validated response types shared by extraction, evaluation, and review."""

from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
	COMPLAINT = "COMPLAINT"
	MOTION = "MOTION"
	ORDER = "ORDER"
	BRIEF = "BRIEF"
	NOTICE = "NOTICE"


class PartyRole(str, Enum):
	PLAINTIFF = "PLAINTIFF"
	DEFENDANT = "DEFENDANT"
	PETITIONER = "PETITIONER"
	RESPONDENT = "RESPONDENT"
	INTERVENOR = "INTERVENOR"
	OTHER = "OTHER"


class PartyType(str, Enum):
	INDIVIDUAL = "INDIVIDUAL"
	ORGANIZATION = "ORGANIZATION"


class Confidence(str, Enum):
	HIGH = "HIGH"
	MEDIUM = "MEDIUM"
	LOW = "LOW"


class Party(BaseModel):
	name: str
	role: PartyRole
	party_type: PartyType


class Attorney(BaseModel):
	name: str
	firm: str = ""
	represents_party: str = ""


class FieldConfidence(BaseModel):
	case_name: Confidence
	docket_number: Confidence
	court_name: Confidence
	filing_date: Confidence
	document_type: Confidence
	parties: Confidence
	attorneys: Confidence
	judge_name: Confidence
	filed_by: Confidence
	relief_sought: Confidence


class ExtractionRecord(BaseModel):
	case_name: str = ""
	docket_number: str = ""
	court_name: str = ""
	filing_date: str = ""
	document_type: DocumentType
	parties: list[Party] = Field(default_factory=list)
	attorneys: list[Attorney] = Field(default_factory=list)
	judge_name: str = ""
	filed_by: str = ""
	relief_sought: str = ""
	redaction_present: bool = False
	field_confidence: FieldConfidence
	overall_confidence: Confidence
	extraction_notes: str = ""