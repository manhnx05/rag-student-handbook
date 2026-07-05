
-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Patients table
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(10),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Examinations table
CREATE TABLE IF NOT EXISTS examinations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    examination_date TIMESTAMP NOT NULL,
    department VARCHAR(255),
    doctor_name VARCHAR(255),
    diagnosis TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Examination details table (for measurements, vitals, etc.)
CREATE TABLE IF NOT EXISTS examination_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    examination_id UUID NOT NULL REFERENCES examinations(id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT,
    unit VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- AI view for retrieval
CREATE OR REPLACE VIEW ai_patient_examinations AS
SELECT 
    p.id AS patient_id,
    p.full_name,
    p.date_of_birth,
    p.gender,
    e.id AS examination_id,
    e.examination_date,
    e.department,
    e.doctor_name,
    e.diagnosis,
    json_agg(
        json_build_object(
            'type', ed.type,
            'key', ed.key,
            'value', ed.value,
            'unit', ed.unit
        )
    ) AS details
FROM patients p
LEFT JOIN examinations e ON p.id = e.patient_id
LEFT JOIN examination_details ed ON e.id = ed.examination_id
GROUP BY p.id, e.id;

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach triggers
CREATE TRIGGER update_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_examinations_updated_at
    BEFORE UPDATE ON examinations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
