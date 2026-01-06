# CSV Import & Employee Details Update

## New Features

### 1. Branch Admin Face Registration (Already Implemented ✅)
**Status**: Complete and live
**Flow**: Add Branch Admin → Auto-redirects to Face ID capture
**Route**: `/admin/branch_admin_face_register/<username>`

### 2. CSV Import for Employee Payroll Data
**Route**: `/admin/import_employee_data`
**Features**:
- Upload CSV with employee bank/personal details
- Validate data before import
- Update existing employee records
- Show success/error summary

**CSV Format**:
```
Username,Account Number,Account Holder,Bank Name,IFSC Code,Bank Branch,PAN Number,Aadhar Number,DOB,Blood Group,Permanent Address,Current Address,Emergency Contact Name,Emergency Contact Phone
```

### 3. Employee Profile Update Forms
**Routes**:
- `/update_profile` - Universal endpoint for all roles
- POST `/update_bank_details` - Save bank information
- POST `/update_personal_details` - Save personal information

**Accessible By**: All employee roles (Doctor, Receptionist, Pharmacist, Lab Assistant)
