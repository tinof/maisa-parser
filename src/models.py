from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PatientProfile(BaseModel):
    full_name: str = "Unknown"
    national_id: str = "Unknown"
    gender: str = "Unknown"
    dob: str | None = None
    address: str = ""
    phone: str = ""
    email: str = ""


class Allergy(BaseModel):
    substance: str
    status: str


class Medication(BaseModel):
    name: str
    atc_code: str | None = None
    dosage: str = ""
    start_date: str | None = None
    end_date: str | None = None
    status: str = "Unknown"


class LabResult(BaseModel):
    test_name: str
    result_value: float | None = None
    unit: str | None = None
    interpretation: str | None = None
    reference_range: str | None = None
    timestamp: str | None = None


class Diagnosis(BaseModel):
    code: str | None = None
    code_system: str = ""
    display_name: str
    status: str
    onset_date: str | None = None


class Procedure(BaseModel):
    code: str | None = None
    code_system: str = ""
    name: str
    date: str | None = None
    status: str


class SocialHistory(BaseModel):
    tobacco_smoking: str | None = None
    smokeless_tobacco: str | None = None
    alcohol: str | None = None

    model_config = ConfigDict(extra="allow")


class Immunization(BaseModel):
    vaccine_name: str
    vaccine_code: str | None = None
    date: str | None = None
    status: str


class DocumentSummary(BaseModel):
    date: str | None = None
    type: str = "Clinical Document"
    provider: str = "Unknown"
    notes: str = ""
    source_file: str = ""


class ClinicalSummary(BaseModel):
    allergies: list[Allergy] = Field(default_factory=list)
    active_medications: list[Medication] = Field(default_factory=list)
    medication_history: list[Medication] = Field(default_factory=list)


class HealthRecord(BaseModel):
    patient_profile: PatientProfile = Field(default_factory=lambda: PatientProfile())
    clinical_summary: ClinicalSummary = Field(default_factory=ClinicalSummary)
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    immunizations: list[Immunization] = Field(default_factory=list)
    social_history: SocialHistory = Field(default_factory=SocialHistory)
    lab_results: list[LabResult] = Field(default_factory=list)
    encounters: list[DocumentSummary] = Field(default_factory=list)
