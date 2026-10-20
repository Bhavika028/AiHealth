-- PostgreSQL reference for EMPTY databases only. Use migrations for existing data.

CREATE TABLE clinics (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	registration_no VARCHAR(128), 
	address TEXT NOT NULL, 
	city VARCHAR(128) NOT NULL, 
	latitude FLOAT, 
	longitude FLOAT, 
	phone VARCHAR(32), 
	email VARCHAR(255), 
	qr_clinic_code VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (registration_no), 
	UNIQUE (qr_clinic_code)
)

;

CREATE TABLE revoked_tokens (
	id VARCHAR(128) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)

;

CREATE TABLE users (
	id VARCHAR(64) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	phone VARCHAR(32), 
	password_hash VARCHAR(255), 
	pin_hash VARCHAR(255), 
	pin_failures INTEGER, 
	pin_locked_until TIMESTAMP WITHOUT TIME ZONE, 
	role VARCHAR(32) NOT NULL, 
	language_preference VARCHAR(16), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)

;
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE hospitals (
	user_id VARCHAR(64), 
	is_active BOOLEAN, 
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	registration_no VARCHAR(128), 
	address TEXT NOT NULL, 
	city VARCHAR(128) NOT NULL, 
	latitude FLOAT, 
	longitude FLOAT, 
	emergency_phone VARCHAR(32), 
	treatments JSON, 
	total_doctors INTEGER, 
	total_wards INTEGER, 
	total_icu_beds INTEGER, 
	total_general_beds INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (registration_no)
)

;

CREATE TABLE patients (
	last_verified_at TIMESTAMP WITHOUT TIME ZONE, 
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	full_name VARCHAR(255) NOT NULL, 
	age INTEGER NOT NULL, 
	dob DATE, 
	gender VARCHAR(32) NOT NULL, 
	blood_group VARCHAR(8), 
	existing_conditions JSON, 
	allergies JSON, 
	current_medications JSON, 
	medical_history JSON, 
	is_child BOOLEAN, 
	parent_guardian_name VARCHAR(255), 
	parent_guardian_phone VARCHAR(32), 
	emergency_contact_name VARCHAR(255), 
	emergency_contact_phone VARCHAR(32), 
	address TEXT, 
	city VARCHAR(128), 
	latitude FLOAT, 
	longitude FLOAT, 
	aadhaar_card_no VARCHAR(32), 
	pan_card_no VARCHAR(32), 
	has_insurance BOOLEAN, 
	insurance_claimed BOOLEAN, 
	insurance_provider VARCHAR(255), 
	insurance_policy_no VARCHAR(128), 
	insurance_is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE TABLE pharmacy_stores (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	store_name VARCHAR(255) NOT NULL, 
	pharmacist_name VARCHAR(255), 
	license_no VARCHAR(128), 
	address TEXT NOT NULL, 
	city VARCHAR(128), 
	latitude FLOAT, 
	longitude FLOAT, 
	is_online BOOLEAN, 
	last_active_at TIMESTAMP WITHOUT TIME ZONE, 
	phone VARCHAR(32), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (license_no)
)

;

CREATE TABLE access_grants (
	id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64), 
	scope VARCHAR(32) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (token_hash)
)

;

CREATE TABLE allergy_records (
	patient_id VARCHAR(64) NOT NULL, 
	substance VARCHAR(255) NOT NULL, 
	reaction TEXT, 
	severity VARCHAR(32), 
	last_verified_at TIMESTAMP WITHOUT TIME ZONE, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE audit_logs (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64), 
	patient_id VARCHAR(64), 
	action VARCHAR(128) NOT NULL, 
	resource VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
)

;
CREATE INDEX ix_audit_logs_patient_id ON audit_logs (patient_id);

CREATE TABLE doctors (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	clinic_id VARCHAR(64), 
	hospital_id VARCHAR(64), 
	full_name VARCHAR(255) NOT NULL, 
	specialization VARCHAR(128) NOT NULL, 
	education VARCHAR(255), 
	license_no VARCHAR(128), 
	clinic_name VARCHAR(255), 
	clinic_address TEXT, 
	patients_checked_count INTEGER, 
	degree_proof_url TEXT, 
	available_hours JSON, 
	is_verified BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE SET NULL, 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id) ON DELETE SET NULL, 
	UNIQUE (license_no)
)

;

CREATE TABLE history_summaries (
	patient_id VARCHAR(64) NOT NULL, 
	content JSON NOT NULL, 
	source_refs JSON, 
	method VARCHAR(64) NOT NULL, 
	review_note TEXT, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE inventory (
	id VARCHAR(64) NOT NULL, 
	pharmacy_id VARCHAR(64) NOT NULL, 
	medicine_name VARCHAR(255) NOT NULL, 
	generic_name VARCHAR(255), 
	dosage_form VARCHAR(64) NOT NULL, 
	stock_quantity INTEGER, 
	low_stock_threshold INTEGER, 
	price FLOAT, 
	last_restocked_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pharmacy_medicine UNIQUE (pharmacy_id, medicine_name), 
	FOREIGN KEY(pharmacy_id) REFERENCES pharmacy_stores (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_inventory_pharmacy_id ON inventory (pharmacy_id);

CREATE TABLE notifications (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64), 
	message TEXT NOT NULL, 
	resource_id VARCHAR(64), 
	status VARCHAR(32), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	dedupe_key VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	UNIQUE (dedupe_key)
)

;
CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE patient_qr_tokens (
	id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64) NOT NULL, 
	qr_type VARCHAR(64) NOT NULL, 
	token_payload TEXT NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE
)

;

CREATE TABLE record_versions (
	id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64) NOT NULL, 
	resource VARCHAR(64) NOT NULL, 
	resource_id VARCHAR(64) NOT NULL, 
	editor_id VARCHAR(64) NOT NULL, 
	before JSON NOT NULL, 
	after JSON NOT NULL, 
	reason TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(editor_id) REFERENCES users (id)
)

;

CREATE TABLE access_requests (
	id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64) NOT NULL, 
	provider_user_id VARCHAR(64) NOT NULL, 
	scope VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	grant_id VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(provider_user_id) REFERENCES users (id), 
	FOREIGN KEY(grant_id) REFERENCES access_grants (id)
)

;
CREATE INDEX ix_access_requests_patient_id ON access_requests (patient_id);
CREATE INDEX ix_access_requests_provider_user_id ON access_requests (provider_user_id);

CREATE TABLE consultations (
	hospital_id VARCHAR(64), 
	referral_id VARCHAR(64), 
	created_by VARCHAR(64), 
	id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64) NOT NULL, 
	clinic_id VARCHAR(64), 
	doctor_id VARCHAR(64), 
	visit_type VARCHAR(32), 
	chief_complaint VARCHAR(128) NOT NULL, 
	symptom_duration_value INTEGER, 
	symptom_duration_unit VARCHAR(32), 
	symptom_severity VARCHAR(32) NOT NULL, 
	is_repeat_visit BOOLEAN, 
	previous_consultation_id VARCHAR(64), 
	medicine_taken BOOLEAN, 
	medicine_taken_name VARCHAR(255), 
	regular_medications_confirmed BOOLEAN, 
	existing_conditions_confirmed BOOLEAN, 
	allergies_confirmed BOOLEAN, 
	warning_symptoms JSON, 
	patient_notes TEXT, 
	branch_responses JSON, 
	seasonal_context VARCHAR(64), 
	status VARCHAR(64), 
	is_urgent BOOLEAN, 
	urgency_reason TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE SET NULL, 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id) ON DELETE SET NULL, 
	FOREIGN KEY(previous_consultation_id) REFERENCES consultations (id) ON DELETE SET NULL
)

;
CREATE INDEX ix_consultations_patient_id ON consultations (patient_id);
CREATE INDEX ix_consultations_doctor_id ON consultations (doctor_id);
CREATE INDEX ix_consultations_is_urgent ON consultations (is_urgent);
CREATE INDEX ix_consultations_status ON consultations (status);

CREATE TABLE wards_and_beds (
	state VARCHAR(32), 
	id VARCHAR(64) NOT NULL, 
	hospital_id VARCHAR(64) NOT NULL, 
	ward_name VARCHAR(128) NOT NULL, 
	ward_type VARCHAR(64) NOT NULL, 
	bed_number VARCHAR(32) NOT NULL, 
	is_occupied BOOLEAN, 
	current_patient_id VARCHAR(64), 
	assigned_doctor_id VARCHAR(64), 
	admission_reason TEXT, 
	admission_date TIMESTAMP WITHOUT TIME ZONE, 
	estimated_discharge_date DATE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_hospital_ward_bed UNIQUE (hospital_id, ward_name, bed_number), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id) ON DELETE CASCADE, 
	FOREIGN KEY(current_patient_id) REFERENCES patients (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_doctor_id) REFERENCES doctors (id) ON DELETE SET NULL
)

;

CREATE TABLE diagnoses (
	patient_id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64) NOT NULL, 
	doctor_id VARCHAR(64), 
	facility_id VARCHAR(64), 
	name VARCHAR(255) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE doctor_notes (
	id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64) NOT NULL, 
	doctor_id VARCHAR(64) NOT NULL, 
	patient_id VARCHAR(64) NOT NULL, 
	vital_bp VARCHAR(32), 
	vital_pulse INTEGER, 
	vital_temperature VARCHAR(32), 
	vital_spo2 INTEGER, 
	vital_glucose VARCHAR(32), 
	ai_generated_summary TEXT, 
	ai_risk_flags JSON, 
	clinical_observations TEXT, 
	confirmed_diagnosis VARCHAR(255) NOT NULL, 
	treatment_plan TEXT, 
	follow_up_instructions TEXT, 
	follow_up_date DATE, 
	is_emergency_transfer BOOLEAN, 
	referral_type VARCHAR(64), 
	referral_hospital_id VARCHAR(64), 
	referral_doctor_name VARCHAR(255), 
	referral_destination_name VARCHAR(255), 
	referral_reason TEXT, 
	transfer_status VARCHAR(64), 
	confirmation_pin VARCHAR(16), 
	is_finalized BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (consultation_id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id) ON DELETE CASCADE, 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id) ON DELETE CASCADE, 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(referral_hospital_id) REFERENCES hospitals (id) ON DELETE SET NULL
)

;

CREATE TABLE follow_ups (
	patient_id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64) NOT NULL, 
	doctor_id VARCHAR(64), 
	hospital_id VARCHAR(64), 
	due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reason TEXT NOT NULL, 
	outcome_consultation_id VARCHAR(64), 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	FOREIGN KEY(outcome_consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE medical_documents (
	patient_id VARCHAR(64) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	stored_name VARCHAR(128) NOT NULL, 
	content_type VARCHAR(128) NOT NULL, 
	consultation_id VARCHAR(64), 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE medical_events (
	patient_id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64), 
	doctor_id VARCHAR(64), 
	facility_id VARCHAR(64), 
	kind VARCHAR(64) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	details JSON, 
	resource_id VARCHAR(64), 
	dedupe_key VARCHAR(255), 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	UNIQUE (dedupe_key), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;
CREATE INDEX ix_medical_events_patient_id ON medical_events (patient_id);

CREATE TABLE referrals (
	patient_id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64) NOT NULL, 
	doctor_id VARCHAR(64), 
	source_facility_id VARCHAR(64), 
	hospital_id VARCHAR(64) NOT NULL, 
	specialty VARCHAR(128) NOT NULL, 
	reason TEXT NOT NULL, 
	clinical_summary TEXT, 
	priority VARCHAR(32), 
	receiving_doctor_id VARCHAR(64), 
	outcome_consultation_id VARCHAR(64), 
	outcome_summary TEXT, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	FOREIGN KEY(receiving_doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(outcome_consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE vitals (
	patient_id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	value VARCHAR(64) NOT NULL, 
	unit VARCHAR(32) NOT NULL, 
	measured_at TIMESTAMP WITHOUT TIME ZONE, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE admissions (
	patient_id VARCHAR(64) NOT NULL, 
	hospital_id VARCHAR(64) NOT NULL, 
	bed_id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64), 
	referral_id VARCHAR(64), 
	doctor_id VARCHAR(64), 
	reason TEXT NOT NULL, 
	discharged_at TIMESTAMP WITHOUT TIME ZONE, 
	discharge_summary TEXT, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	FOREIGN KEY(bed_id) REFERENCES wards_and_beds (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(referral_id) REFERENCES referrals (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;
CREATE UNIQUE INDEX uq_active_admission_patient ON admissions (patient_id) WHERE status = 'ADMITTED';

CREATE TABLE prescriptions (
	id VARCHAR(64) NOT NULL, 
	consultation_id VARCHAR(64), 
	doctor_note_id VARCHAR(64), 
	patient_id VARCHAR(64) NOT NULL, 
	doctor_id VARCHAR(64) NOT NULL, 
	pharmacy_id VARCHAR(64), 
	medicines JSON, 
	status VARCHAR(32), 
	dispense_alert_sent BOOLEAN, 
	dispensed_at TIMESTAMP WITHOUT TIME ZONE, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id) ON DELETE SET NULL, 
	FOREIGN KEY(doctor_note_id) REFERENCES doctor_notes (id) ON DELETE SET NULL, 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id) ON DELETE CASCADE, 
	FOREIGN KEY(pharmacy_id) REFERENCES pharmacy_stores (id) ON DELETE SET NULL
)

;
CREATE INDEX ix_prescriptions_patient_id ON prescriptions (patient_id);
CREATE INDEX ix_prescriptions_status ON prescriptions (status);

CREATE TABLE medications (
	patient_id VARCHAR(64) NOT NULL, 
	prescription_id VARCHAR(64), 
	consultation_id VARCHAR(64), 
	doctor_id VARCHAR(64), 
	name VARCHAR(255) NOT NULL, 
	dosage VARCHAR(128), 
	frequency VARCHAR(255), 
	start_date DATE, 
	duration_days INTEGER, 
	end_date DATE, 
	reason TEXT, 
	id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(64), 
	source VARCHAR(64), 
	status VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id), 
	FOREIGN KEY(consultation_id) REFERENCES consultations (id), 
	FOREIGN KEY(doctor_id) REFERENCES doctors (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;
