# Medical Data Model - HIPAA Compliant Database Schema

This database schema is designed for a comprehensive medical records system with full HIPAA compliance features.

## Schema Overview

### Core Tables (01_core_tables.sql)
- **patients** - Patient demographics and contact information
- **healthcare_providers** - Medical staff and provider information
- **medical_facilities** - Hospitals, clinics, and medical facilities
- **medical_encounters** - Patient visits and encounters

### Clinical Data (02_clinical_data.sql)
- **medical_conditions** - Patient diagnoses and medical conditions
- **medications** - Prescription and medication management
- **allergies** - Patient allergies and adverse reactions
- **vital_signs** - Patient vital signs and measurements
- **lab_results** - Laboratory test results and values

### Security & Audit (03_audit_security.sql)
- **users** - System users with HIPAA training tracking
- **roles** - Role-based access control (RBAC)
- **user_roles** - User-role assignments
- **audit_log** - Comprehensive audit trail for all data access
- **patient_access_log** - Specific patient data access tracking
- **security_incidents** - Data breach and security incident tracking

### Procedures & Imaging (04_procedures_imaging.sql)
- **medical_procedures** - Medical procedures and surgeries
- **imaging_studies** - Radiology and imaging studies
- **clinical_documents** - Clinical notes and documentation
- **appointments** - Patient scheduling and appointments

### Views & Functions (05_views_functions.sql)
- **patient_summary** - Comprehensive patient overview
- **active_medications** - Current patient medications
- **critical_lab_results** - Abnormal lab values
- **upcoming_appointments** - Scheduled appointments
- **patient_access_summary** - HIPAA access reporting

## HIPAA Compliance Features

### Technical Safeguards
- **Encryption at Rest**: All sensitive data encrypted using AWS KMS
- **Encryption in Transit**: SSL/TLS enforced for all connections
- **Access Control**: Role-based permissions with principle of least privilege
- **Audit Logging**: Complete audit trail of all data access and modifications
- **User Authentication**: Strong password policies and account lockout
- **Session Management**: Session tracking and timeout controls

### Administrative Safeguards
- **User Training Tracking**: HIPAA training completion and expiry dates
- **Role-Based Access**: Granular permissions based on job functions
- **Incident Management**: Security incident tracking and reporting
- **Access Reviews**: Regular access auditing capabilities

### Physical Safeguards
- **Network Isolation**: Database deployed in private subnets
- **Multi-AZ Deployment**: High availability across multiple zones
- **Backup Encryption**: Automated encrypted backups with retention

## Key Features

### Data Integrity
- **UUID Primary Keys**: Globally unique identifiers
- **Foreign Key Constraints**: Referential integrity enforcement
- **Check Constraints**: Data validation at database level
- **Triggers**: Automatic timestamp updates and calculations

### Performance Optimization
- **Strategic Indexing**: Optimized indexes for common queries
- **Partitioning Ready**: Schema designed for future partitioning
- **Efficient Queries**: Views for common data access patterns

### Clinical Standards
- **ICD-10 Codes**: Diagnosis coding support
- **CPT Codes**: Procedure coding support
- **LOINC Codes**: Laboratory test coding support
- **NDC Codes**: Medication coding support

## Installation Instructions

1. **Create Database**:
   ```sql
   CREATE DATABASE medical_records;
   ```

2. **Install Extensions**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pgcrypto";
   ```

3. **Run Schema Files in Order**:
   ```bash
   psql -d medical_records -f 01_core_tables.sql
   psql -d medical_records -f 02_clinical_data.sql
   psql -d medical_records -f 03_audit_security.sql
   psql -d medical_records -f 04_procedures_imaging.sql
   psql -d medical_records -f 05_views_functions.sql
   psql -d medical_records -f 06_diabetes_specific.sql
   psql -d medical_records -f 07_diabetes_views_functions.sql
   ```

## Default Roles

The schema includes these predefined roles:
- **Physician**: Full patient care access
- **Nurse**: Patient care with limited sensitive data access
- **Medical Assistant**: Basic patient data access
- **Administrator**: User management and system administration
- **Billing**: Financial and insurance data access
- **IT Support**: System access without patient data
- **Auditor**: Read-only access to audit logs

## Security Considerations

### Sensitive Data Handling
- SSN stored encrypted using `encrypt_ssn()` function
- Audit logging required for all PHI access
- Data access must include business justification
- Failed login attempts tracked and locked after threshold

### Compliance Monitoring
- All patient data access logged with user, timestamp, and reason
- Security incidents tracked with resolution status
- Regular access reviews supported through audit views
- HIPAA training compliance tracked per user

## Usage Examples

### Create a New Patient
```sql
INSERT INTO patients (
    medical_record_number, first_name, last_name, date_of_birth, 
    gender, phone_primary, created_by
) VALUES (
    'MRN001234', 'John', 'Doe', '1980-01-15', 
    'Male', '555-123-4567', 'user-uuid-here'
);
```

### Log Patient Data Access
```sql
SELECT log_patient_access(
    'patient-uuid',
    'user-uuid', 
    'VIEW',
    ARRAY['demographics', 'medications'],
    'Treatment planning',
    'session-123',
    '192.168.1.100'::inet
);
```

### Check Drug Interactions
```sql
SELECT * FROM check_drug_interactions('patient-uuid', 'Aspirin 81mg');
```

## Maintenance

### Regular Tasks
- Monitor audit logs for suspicious activity
- Review user access patterns monthly
- Update HIPAA training records
- Backup verification and testing
- Security incident review and resolution

### Performance Monitoring
- Query performance analysis
- Index usage statistics
- Storage growth monitoring
- Connection pool optimization

## Diabetes-Specific Enhancements

### **Additional Tables for Diabetes Management:**
- **blood_glucose_readings** - Comprehensive glucose monitoring with context
- **cgm_readings** - Continuous glucose monitor data integration
- **insulin_administrations** - Detailed insulin dosing and delivery tracking
- **carb_intake** - Carbohydrate counting and meal management
- **diabetes_lab_results** - HbA1c, ketones, and diabetes-specific tests
- **diabetes_complications** - Retinopathy, nephropathy, neuropathy tracking
- **diabetes_education** - Patient education and self-management training

### **Specialized Views and Analytics:**
- **diabetes_patient_dashboard** - Comprehensive diabetes overview per patient
- **glucose_trends** - Time-in-range analysis and glucose patterns
- **insulin_carb_analysis** - Insulin-to-carb ratio optimization
- **hypoglycemic_episodes** - Low glucose event tracking and analysis

### **Advanced Functions:**
- `calculate_time_in_range()` - TIR calculations with customizable targets
- `detect_glucose_patterns()` - Automated pattern recognition (dawn phenomenon, post-meal spikes)
- `calculate_insulin_sensitivity()` - Correction factor optimization
- Automatic glucose unit conversion (mg/dL ↔ mmol/L)

### **Diabetes-Specific Features:**
- **CGM Integration** - Support for continuous glucose monitors
- **Pattern Detection** - Automated identification of glucose patterns
- **Insulin Optimization** - Carb ratio and correction factor analysis
- **Complication Tracking** - Comprehensive diabetes complication management
- **Education Tracking** - Patient education and competency assessment

This enhanced schema provides a comprehensive foundation for diabetes management applications with advanced analytics, pattern recognition, and clinical decision support capabilities while maintaining full HIPAA compliance.