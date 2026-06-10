from typing import Optional
from pydantic import BaseModel, Field

insurance_desc = """
    The insurance information related to the patient. This could include the name of the insurance provider or the type of plan.
    If the 'insurance' is molina or molina healthcare, your format will be "MOLINA HEALTHCARE OF CALIFORNIA PARTNER PLAN".
    If the 'insurance' is blue cross or blue shield or blue cross blue shield or blue anthem or anthem or anthem blue cross blue shield your format will be "ANTHEM BLUE CROSS PARTNERSHIP PLAN".
    If the 'insurance' is health or health net or health net community, your format will be "HEALTH NET COMMUNITY SOLUTIONS INC.".
    If the 'insurance' is kaiser or permanente or kaiser permanente, your format will be "KAISER PERMANENTE".
    If no insurance provider is mentioned, leave the 'insurance' section empty.
"""

specialty_desc = """
    The medical specialty that the user needs.
    This value should be ALWAYS in uppercase.
    In determining the 'specialty', prioritize the following:
        1. **Explicit mentions of medical professionals or specialties:** If the query directly states the type of doctor or medical field needed (e.g., "cardiologist", "dermatology"), use that as the 'specialty'.
        2. **Procedures or treatments:** If the query mentions specific procedures or treatments, infer the most likely specialty associated with them (e.g., "root canal" -> "dentist", "mammogram" -> "radiologist").
        3. **Symptoms or conditions:** If the query describes symptoms or conditions, deduce the most relevant specialty that typically handles such cases (e.g., "chest pain" -> "cardiologist", "rash" -> "dermatologist").
    Make sure that you associate the specialty needed from the user query and the doctor specialization that you find in the list down below without altering the capital:  
    INTERNAL MEDICINE,HOSPITALIST,DIAGNOSTIC RADIOLOGY,PHYSICAL MEDICINE AND REHABILITATION,ANESTHESIOLOGY,PODIATRY,PLASTIC AND RECONSTRUCTIVE SURGERY,CARDIOVASCULAR DISEASE (CARDIOLOGY),PHYSICAL THERAPY,UROLOGY,INFECTIOUS DISEASE,NURSE PRACTITIONER,PHYSICIAN ASSISTANT,EMERGENCY MEDICINE,OBSTETRICS/GYNECOLOGY,GENERAL SURGERY,NEPHROLOGY,FAMILY PRACTICE,OTOLARYNGOLOGY,PSYCHIATRY,DERMATOLOGY,CERTIFIED REGISTERED NURSE ANESTHETIST (CRNA),CARDIAC ELECTROPHYSIOLOGY,INTERVENTIONAL CARDIOLOGY,NEUROLOGY,OSTEOPATHIC MANIPULATIVE MEDICINE,PATHOLOGY,MARRIAGE AND FAMILY THERAPIST,OCCUPATIONAL THERAPY,HEMATOLOGY/ONCOLOGY,PULMONARY DISEASE,OPHTHALMOLOGY,PEDIATRIC MEDICINE,CRITICAL CARE (INTENSIVISTS),GENERAL PRACTICE,ENDOCRINOLOGY,ORTHOPEDIC SURGERY,VASCULAR SURGERY,CARDIAC SURGERY,INTERVENTIONAL RADIOLOGY,GYNECOLOGICAL ONCOLOGY,GASTROENTEROLOGY,HAND SURGERY,RADIATION ONCOLOGY,MENTAL HEALTH COUNSELOR,ALLERGY/IMMUNOLOGY,COLORECTAL SURGERY (PROCTOLOGY),MEDICAL GENETICS AND GENOMICS,NEUROSURGERY,CLINICAL PSYCHOLOGIST,CHIROPRACTIC,PAIN MANAGEMENT,ORAL SURGERY,OPTOMETRY,CLINICAL SOCIAL WORKER,MEDICAL ONCOLOGY,SURGICAL ONCOLOGY,QUALIFIED SPEECH LANGUAGE PATHOLOGIST,NUCLEAR MEDICINE,THORACIC SURGERY,INTERVENTIONAL PAIN MANAGEMENT,PREVENTIVE MEDICINE,CERTIFIED NURSE MIDWIFE (CNM),RHEUMATOLOGY,PERIPHERAL VASCULAR DISEASE,MAXILLOFACIAL SURGERY,HEMATOLOGY,QUALIFIED AUDIOLOGIST,SPORTS MEDICINE,UNDEFINED PHYSICIAN TYPE (SPECIFY),GERIATRIC MEDICINE,ADVANCED HEART FAILURE AND TRANSPLANT CARDIOLOGY,SLEEP MEDICINE
"""


class MedicalSupportRequest(BaseModel):
    """This class captures user requests related to medical support information, including relevant details such as the patient's insurance and required specialty."""

    insurance: Optional[str] = Field(
        default=None, description=insurance_desc)
    specialty: Optional[str] = Field(
        default=None, description=specialty_desc)