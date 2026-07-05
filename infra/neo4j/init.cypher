
-- Create unique constraints
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Patient) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Examination) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (doc:Doctor) REQUIRE doc.name IS UNIQUE;

-- Create indexes
CREATE INDEX IF NOT EXISTS FOR (p:Patient) ON (p.full_name);
CREATE INDEX IF NOT EXISTS FOR (e:Examination) ON (e.examination_date);
