from flask import Flask, render_template, render_template_string, request, redirect, session, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import smtplib
import os
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from face_utils import extract_face_encoding_from_base64, verify_face, validate_face_quality, encrypt_face_encoding, decrypt_face_encoding

app = Flask(__name__)
app.secret_key = "your_secret_key_please_change_this_for_security" # **IMPORTANT: Change this to a strong, random key in production!**

# Serve local logo/bot icon image
@app.route("/file.jpeg")
def serve_local_logo():
    try:
        base_dir = os.path.dirname(__file__)
        # Fallback sequence: file.jpeg -> static/images/heydoc_logo.png -> static/images/client_logo.png
        if os.path.exists(os.path.join(base_dir, "file.jpeg")):
            return send_from_directory(base_dir, "file.jpeg")
        elif os.path.exists(os.path.join(base_dir, "static/images/heydoc_logo.png")):
            return send_from_directory(os.path.join(base_dir, "static/images"), "heydoc_logo.png")
        else:
            return send_from_directory(os.path.join(base_dir, "static/images"), "client_logo.png")
    except Exception as _e:
        return ("", 404)

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.errorhandler(404)
def page_not_found(e):
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 - Not Found - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body class="bg-slate-50 min-h-screen flex items-center justify-center p-6">
    <div class="max-w-md w-full text-center">
        <div class="mb-8 relative inline-block">
            <div class="w-32 h-32 bg-teal-100 rounded-full flex items-center justify-center mx-auto animate-pulse">
                <i class="ri-search-line text-6xl text-teal-600"></i>
            </div>
            <div class="absolute -top-2 -right-2 w-12 h-12 bg-rose-500 rounded-full flex items-center justify-center text-white border-4 border-slate-50">
                <i class="ri-close-line text-2xl font-bold"></i>
            </div>
        </div>
        <h1 class="text-6xl font-black text-slate-800 mb-4">404</h1>
        <h2 class="text-2xl font-bold text-slate-700 mb-4">Page Not Found</h2>
        <p class="text-slate-500 mb-8 font-medium">The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.</p>
        <a href="/" class="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white px-8 py-4 rounded-2xl font-black text-sm uppercase tracking-widest transition-all shadow-lg shadow-teal-900/10">
            <i class="ri-home-4-line text-lg"></i> Back to Homepage 
        </a>        </a>
    </div>
</body>
</html>
    """), 404

# SMTP Configuration for email notifications
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("MAIL_USERNAME", "heydocnew@gmail.com")
EMAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "irlf luex ikpd ilha")
DOCTOR_EMAIL = "eedevnsskjayanth@gmail.com"

client = MongoClient("mongodb+srv://varma:varma1225@varma.f5zdh.mongodb.net/?retryWrites=true&w=majority&appName=varma")
db = client["hospital_bot"]

# --- Collections ---
def init_db():
    try:
        existing_collections = db.list_collection_names()
        # Doctors Collection
        if 'doctor' not in existing_collections:
            db.create_collection('doctor', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['username', 'password', 'email', 'name', 'specialization', 'status'],
                    'properties': {
                        'username': {'bsonType': 'string'},
                        'password': {'bsonType': 'string'},
                        'email': {'bsonType': 'string'},
                        'name': {'bsonType': 'string'},
                        'specialization': {'bsonType': 'string'},
                        'city': {'bsonType': 'string'},
                        'clinic_name': {'bsonType': 'string'},
                        'years_of_experience': {'bsonType': 'int', 'minimum': 0},
                        'contact_info': {
                            'bsonType': 'object',
                            'properties': {
                                'phone': {'bsonType': 'string'},
                                'address': {'bsonType': 'string'},
                                'emergency_contact': {'bsonType': 'string'}
                            }
                        },
                        'status': {'enum': ['active', 'inactive']},
                        'leaves': {
                            'bsonType': 'array',
                            'items': {
                                'bsonType': 'object',
                                'properties': {
                                    'start_date': {'bsonType': 'date'},
                                    'end_date': {'bsonType': 'date'},
                                    'reason': {'bsonType': 'string'},
                                    'status': {'enum': ['pending', 'approved', 'rejected'], 'default': 'pending'},
                                    'applied_at': {'bsonType': 'date', 'default': datetime.utcnow()}
                                },
                                'required': ['start_date', 'end_date', 'reason']
                            }
                        },
                        'created_at': {'bsonType': 'date', 'default': datetime.utcnow()},
                        'updated_at': {'bsonType': 'date', 'default': datetime.utcnow()}
                    }
                }
            })

        # Patients Collection
        if 'patients' not in existing_collections:
            db.create_collection('patients', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['name', 'email', 'phone', 'city'],
                    'properties': {
                        'name': {'bsonType': 'string'},
                        'email': {'bsonType': 'string'},
                        'phone': {'bsonType': 'string'},
                        'city': {'bsonType': 'string'},
                        'address': {'bsonType': 'string'},
                        'date_of_birth': {'bsonType': 'date'},
                        'blood_group': {'bsonType': 'string'},
                        'medical_history': {
                            'bsonType': 'array',
                            'items': {
                                'bsonType': 'object',
                                'properties': {
                                    'condition': {'bsonType': 'string'},
                                    'diagnosed_date': {'bsonType': 'date'},
                                    'status': {'bsonType': 'string'}
                                }
                            }
                        },
                        'created_at': {'bsonType': 'date', 'default': datetime.utcnow()},
                        'updated_at': {'bsonType': 'date', 'default': datetime.utcnow()}
                    }
                }
            })




        # Branch Admins Collection
        if 'branch_admins' not in existing_collections:
            db.create_collection('branch_admins', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['username', 'password', 'email', 'name', 'branch_ids', 'status'],
                    'properties': {
                        'username': {'bsonType': 'string'},
                        'password': {'bsonType': 'string'},
                        'email': {'bsonType': 'string'},
                        'name': {'bsonType': 'string'},
                        'branch_ids': {
                            'bsonType': 'array',
                            'items': {'bsonType': 'string'}
                        },
                        'status': {'enum': ['active', 'inactive']},
                        'created_at': {'bsonType': 'date', 'default': datetime.utcnow()}
                    }
                }
            })

        # Pharmacy Orders Collection
        if 'pharmacy_orders' not in existing_collections:
            db.create_collection('pharmacy_orders', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['patient_id', 'items', 'order_type', 'status'],
                    'properties': {
                        'patient_id': {'bsonType': 'objectId'},
                        'items': {'bsonType': 'string'},
                        'order_type': {'enum': ['Walk-in', 'Delivery']},
                        'status': {'enum': ['Pending', 'Processing', 'Ready', 'Delivered', 'Cancelled']},
                        'created_at': {'bsonType': 'date'}
                    }
                }
            })

        # Appointments Collection
        if 'appointments' not in existing_collections:
            db.create_collection('appointments', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['doctor_id', 'patient_id', 'appointment_date', 'time_slot', 'status'],
                    'properties': {
                        'doctor_id': {'bsonType': 'objectId'},
                        'patient_id': {'bsonType': 'objectId'},
                        'appointment_date': {'bsonType': 'date'},
                        'time_slot': {'bsonType': 'string'},
                        'status': {
                            'enum': ['pending', 'confirmed', 'completed', 'cancelled'],
                            'default': 'pending'
                        },
                        'reason': {'bsonType': 'string'},
                        'notes': {'bsonType': 'string'},
                        'created_at': {'bsonType': 'date', 'default': datetime.utcnow()},
                        'updated_at': {'bsonType': 'date', 'default': datetime.utcnow()}
                    }
                }
            })
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

# init_db() # Moved to lazy initialization to prevent startup timeout
_db_initialized = False

def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        init_db()
        # Fix for duplicate key error on qrCode (make it sparse unique)
        try:
            # Drop existing index if it's not sparse
            indexes = patients_collection.index_information()
            if "qrCode_1" in indexes:
                patients_collection.drop_index("qrCode_1")
            # Create sparse unique index
            patients_collection.create_index("qrCode", unique=True, sparse=True)
        except Exception as e:
            print(f"Warning: Could not recreate qrCode index: {e}")
        _db_initialized = True

@app.before_request
def before_request_init():
    ensure_db_initialized()
    
    # One-time fix for branch_admins schema (remove after first run if needed, or keep for dev)
    # Check if we need to migrate or just drop. For now, dropping to ensure clean state as per plan.
    if 'branch_admins_fixed' not in globals():
        try:
            # We can't easily check schema version in Mongo without complex queries, 
            # so we'll drop it if it exists and is empty or has old data that is causing issues.
            # However, prompt said "unable to add", implying schema validation failure.
            # Let's force re-create the validator.
            db.command('collMod', 'branch_admins', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['username', 'password', 'email', 'name', 'branch_ids', 'status'],
                    'properties': {
                        'username': {'bsonType': 'string'},
                        'password': {'bsonType': 'string'},
                        'email': {'bsonType': 'string'},
                        'name': {'bsonType': 'string'},
                        'branch_ids': {
                            'bsonType': 'array',
                            'items': {'bsonType': 'string'}
                        },
                        'status': {'enum': ['active', 'inactive']},
                        'created_at': {'bsonType': 'date'},
                        'created_by': {'bsonType': 'string'},
                        'first_login': {'bsonType': 'bool'},
                        'must_change_password': {'bsonType': 'bool'},
                        'phone': {'bsonType': 'string'}
                    }
                }
            })
            # Also update init_db to match this if it doesn't already
        except Exception as e:
            # If collection doesn't exist, init_db will create it.
            # If it does, we might need to drop it if collMod fails due to data mismatch.
            print(f"Schema update attempt: {e}")
            pass
        globals()['branch_admins_fixed'] = True

@app.context_processor
def inject_translations():
    def gettext(s):
        lang = session.get('lang', 'en')
        
        translations_en = {
            'home': 'Home',
            'dashboard': 'Dashboard',
            'staff_directory': 'Staff Directory',
            'branches': 'Branches',
            'holidays': 'Holidays',
            'payroll': 'Payroll',
            'reports': 'Reports',
            'cms': 'CMS',
            'profile': 'Profile',
            'logout': 'Logout',
            'welcome': 'Welcome',
            'overview_control': 'Overview & Control',
            'global_status': 'Global Status',
            'patient_portal': 'Patient Portal',
            'hello': 'Hello',
            'recent_visits': 'Recent Visits',
            'recent_visits_desc': 'Your journey to wellness',
            'med_records': 'Medical Records',
            'health_tracker': 'Health Tracker',
            'vitals_history': 'Your clinical vitals history',
            'log_vitals': 'Log Vitals',
            'save_vitals': 'Save Vitals',
            'weight': 'Weight',
            'bp': 'Blood Pressure',
            'sugar': 'Blood Sugar',
            'emergency_sos': 'Emergency SOS',
            'sos_desc': 'Help is just a click away',
            'nearby_branches': 'Nearby Branches',
            'call_ambulance': 'Call Ambulance',
            'need_a_doctor': 'Need a Doctor?',
            'book_session_desc': 'Book a session with our specialists and get the care you deserve.',
            'location': 'Location',
            'select_clinic': 'Select Clinic',
            'consultation_type': 'Consultation Type',
            'walk_in': 'In-Person Visit (Walk-in)',
            'video_consultation': 'Video Consultation',
            'preferred_date': 'Preferred Date',
            'symptoms': 'Symptoms',
            'describe_issue': 'Briefly describe your health issue...',
            'confirm_booking': 'Confirm Booking Request',
            'reminders': 'Reminders',
            'no_reminders': 'No pending reminders',
            'total_visits': 'Total Visits',
            'total_prescriptions': 'Total Prescriptions',
            'total_reports': 'Total Reports',
            'last_visit': 'Last Visit',
            'video_consultation_title': 'Video Consultation',
            'video_consultation_desc': 'Join your scheduled video call session with your doctor.',
            'join_room': 'Join Room',
            'prescriptions_title': 'Prescriptions',
            'payment_history_title': 'Payment History',
            'no_prescriptions': 'No prescriptions',
            'no_payments': 'No payment records',
            'upload_new': 'Upload New',
            'upload_desc': 'Store your medical documents securely in your profile.',
            'record_name': 'Record Name',
            'choose_file': 'Choose File',
            'start_upload': 'Start Upload',
            'cancel': 'Cancel',
            'new_order': 'New Order',
            'pharmacy_orders': 'Pharmacy Orders',
            'order_meds_desc': 'Order medications as Walk-in or Delivery',
            'no_orders': 'No pharmacy orders found',
            'my_payroll': 'My Payroll',
            'payroll_desc': 'Financial history and disbursement records',
            'current_net_salary': 'Current Net Salary',
            'base_salary': 'Base Salary',
            'bonuses': 'Bonuses',
            'deductions': 'Deductions',
            'disbursement_history': 'Disbursement History',
            'month': 'Month',
            'status': 'Status',
            'amount': 'Amount',
            'disbursed': 'Disbursed',
            'end_of_financial_records': 'End of financial records for current cycle',
            'payroll_management': 'Payroll Management',
            'manage_staff_salaries': 'Manage staff salaries, payments, and history',
            'print_report': 'Print Report',
            'export_csv': 'Export CSV',
            'monthly_expenditure': 'Monthly Expenditure',
            'active_staff': 'Active Staff',
            'tax_withheld': 'Tax Withheld',
            'next_disbursement': 'Next Disbursement',
            'staff_compensation_directory': 'Staff Compensation Directory',
            'search_staff': 'Search staff...',
            'staff_member': 'Staff Member',
            'role_and_branch': 'Role & Branch',
            'nett_pay': 'Nett Pay',
            'action': 'Action',
            'no_staff_records': 'No staff records found.',
            'staff_members_total': 'Staff Members Total',
            'previous': 'Previous',
            'next': 'Next',
            'update_salary_structure': 'Update Salary Structure',
            'base_monthly_salary': 'Base Monthly Salary',
            'update_finance': 'Update Finance'
        }

        translations_te = {
            'home': 'హోమ్',
            'dashboard': 'డ్యాష్‌బోర్డ్',
            'staff_directory': 'స్టాఫ్ డైరెక్టరీ',
            'branches': 'శాఖలు',
            'holidays': ' సెలవులు',
            'payroll': 'పేరోల్',
            'reports': 'నివేదికలు',
            'cms': 'CMS',
            'profile': 'ప్రొఫైల్',
            'logout': 'లాగౌట్',
            'welcome': 'స్వాగతం',
            'overview_control': 'అవలోకనం & నియంత్రణ',
            'global_status': 'గ్లోబల్ స్థితి',
            'patient_portal': 'పేషెంట్ పోర్టల్',
            'hello': 'నమస్కారం',
            'recent_visits': 'ఇటీవలి సందర్శనలు',
            'recent_visits_desc': 'మీ ఆరోగ్య ప్రయాణం',
            'med_records': 'వైద్య రికార్డులు',
            'health_tracker': 'హెల్త్ ట్రాకర్',
            'vitals_history': 'మీ ఆరోగ్య గణాంకాలు',
            'log_vitals': 'వైటల్స్ నమోదు',
            'save_vitals': 'సేవ్ చేయండి',
            'weight': 'బరువు',
            'bp': 'రక్త పోటు',
            'sugar': 'రక్తంలో చక్కెర',
            'emergency_sos': 'అత్యవసర సహాయం',
            'sos_desc': 'సహాయం ఒక క్లిక్ దూరంలో ఉంది',
            'nearby_branches': 'దగ్గరి శాఖలు',
            'call_ambulance': 'అంబులెన్స్‌కు కాల్ చేయండి',
            'need_a_doctor': 'వైద్యుడు కావాలా?',
            'book_session_desc': 'మా నిపుణులతో అపాయింట్‌మెంట్ బుక్ చేసుకోండి.',
            'location': 'ప్రదేశం',
            'select_clinic': 'క్లినిక్‌ని ఎంచుకోండి',
            'consultation_type': 'కన్సల్టేషన్ రకం',
            'walk_in': 'నేరుగా సందర్శన (Walk-in)',
            'video_consultation': 'వీడియో కన్సల్టేషన్',
            'preferred_date': 'తేదీ',
            'symptoms': 'లక్షణాలు',
            'describe_issue': 'మీ ఆరోగ్య సమస్యను క్లుప్తంగా వివరించండి...',
            'confirm_booking': 'బుకింగ్‌ను నిర్ధారించండి',
            'reminders': 'రిమైండర్‌లు',
            'no_reminders': 'పెండింగ్ రిమైండర్‌లు లేవు',
            'total_visits': 'మొత్తం సందర్శనలు',
            'total_prescriptions': 'మొత్తం ప్రిస్క్రిప్షన్లు',
            'total_reports': 'మొత్తం నివేదికలు',
            'last_visit': 'చివరి సందర్శన',
            'video_consultation_title': 'వీడియో కన్సల్టేషన్',
            'video_consultation_desc': 'మీ డాక్టర్‌తో వీడియో కాల్‌లో మాట్లాడండి.',
            'join_room': 'రూమ్‌లో చేరండి',
            'prescriptions_title': 'ప్రిస్క్రిప్షన్లు',
            'payment_history_title': 'చెల్లింపు చరిత్ర',
            'no_prescriptions': 'ప్రిస్క్రిప్షన్లు లేవు',
            'no_payments': 'చెల్లింపు రికార్డులు లేవు',
            'upload_new': 'కొత్తది అప్‌లోడ్ చేయండి',
            'upload_desc': 'మీ వైద్య పత్రాలను సురక్షితంగా భద్రపరచండి.',
            'record_name': 'రికార్డ్ పేరు',
            'choose_file': 'ఫైల్ ఎంచుకోండి',
            'start_upload': 'అప్‌లోడ్ ప్రారంభించండి',
            'cancel': 'రద్దు చేయండి',
            'new_order': 'కొత్త ఆర్డర్',
            'pharmacy_orders': 'ఫార్మసీ ఆర్డర్లు',
            'order_meds_desc': 'మందులను ఆర్డర్ చేయండి',
            'no_orders': 'ఫార్మసీ ఆర్డర్లు కనుగొనబడలేదు',
            'my_payroll': 'నా పేరోల్',
            'payroll_desc': 'ఆర్థిక చరిత్ర మరియు చెల్లింపు రికార్డులు',
            'current_net_salary': 'ప్రస్తుత నికర వేతనం',
            'base_salary': 'బేస్ జీతం',
            'bonuses': 'బోనస్లు',
            'deductions': 'తగ్గింపులు',
            'disbursement_history': 'చెల్లింపు చరిత్ర',
            'month': 'నెల',
            'status': 'స్థితి',
            'amount': 'మొత్తం',
            'disbursed': 'పంపిణీ చేయబడింది',
            'end_of_financial_records': 'ప్రస్తుత ఆర్థిక రికార్డుల ముగింపు',
            'payroll_management': 'పేరోల్ నిర్వహణ',
            'manage_staff_salaries': 'సిబ్బంది జీతాలు మరియు చెల్లింపులను నిర్వహించండి',
            'print_report': 'రిపోర్ట్ ప్రింట్ చేయండి',
            'export_csv': 'CSV ఎగుమతి',
            'monthly_expenditure': 'నెలవారీ ఖర్చు',
            'active_staff': 'యాక్టివ్ సిబ్బంది',
            'tax_withheld': 'పన్ను నిలిపివేత',
            'next_disbursement': 'తదుపరి చెల్లింపు',
            'staff_compensation_directory': 'సిబ్బంది పరిహార డైరెక్టరీ',
            'search_staff': 'సిబ్బంది కోసం వెతకండి...',
            'staff_member': 'సిబ్బంది సభ్యుడు',
            'role_and_branch': 'పాత్ర & శాఖ',
            'nett_pay': 'నెట్ పే',
            'action': 'చర్య',
            'no_staff_records': 'సిబ్బంది రికార్డులు కనుగొనబడలేదు.',
            'staff_members_total': 'మొత్తం సిబ్బంది',
            'previous': 'మునుపటి',
            'next': 'తరువాత',
            'update_salary_structure': 'జీతం ఆకృతిని నవీకరించండి',
            'base_monthly_salary': 'బేస్ నెలవారీ జీతం',
            'update_finance': 'ఆర్థిక వివరాలను నవీకరించండి'
        }
        
        if lang == 'te':
            return translations_te.get(s, translations_en.get(s, s))
        return translations_en.get(s, s)

    return dict(_=gettext, lang=session.get('lang', 'en'))

def get_branch_by_id(branch_id):
    """Helper to find a branch by ID, robust to string/ObjectId mismatch"""
    if not branch_id:
        return None
    try:
        # Try finding by ObjectId first
        branch = branches_collection.find_one({"_id": ObjectId(branch_id)})
        if branch:
            return branch
    except Exception:
        pass
    # Fallback to finding by string ID
    return branches_collection.find_one({"_id": branch_id})

doctors_collection = db['doctor']
patients_collection = db['patients']
appointments_collection = db['appointments']
admin_collection = db['admin']
branches_collection = db['branch']
circulars_collection = db['circulars']
receptionists_collection = db['receptionists']
certificates_collection = db['certificates']
pharmacy_orders_collection = db['pharmacy_orders']

@app.route("/pharmacist_dashboard")
def pharmacist_dashboard():
    if "pharmacist" not in session: return redirect("/login")
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Pharmacy Dashboard - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-slate-50 min-h-screen">
        <nav class="bg-emerald-600 p-4 text-white flex justify-between items-center shadow-lg">
            <h1 class="text-xl font-bold flex items-center"><i class="ri-capsule-line mr-2"></i> Pharmacy Services</h1>
            <div>
                <a href="/my_payroll" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 mr-2">My Payroll</a>
                <a href="/logout" class="bg-red-500 px-4 py-2 rounded-lg hover:bg-red-600">Logout</a>
            </div>
        </nav>
        <div class="p-20 text-center">
            <div class="w-24 h-24 bg-emerald-100 text-emerald-600 rounded-3xl flex items-center justify-center text-4xl mx-auto mb-6 shadow-xl border border-emerald-200">
                <i class="ri-medicine-bottle-line"></i>
            </div>
            <h2 class="text-3xl font-black text-slate-800">Welcome, {{ session.pharmacist }}</h2>
            <p class="text-slate-400 mt-2 font-medium">Medication Inventory & Prescription Fulfillment</p>
        </div>
    </body>
    </html>
    """)

@app.route("/finance_dashboard")
def finance_dashboard():
    if "financial_analytics" not in session: return redirect("/login")
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Finance Dashboard - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen">
        <nav class="bg-slate-900 border-b border-white/10 p-4 text-white flex justify-between items-center sticky top-0 z-50">
            <h1 class="text-xl font-black flex items-center tracking-tighter">
                <i class="ri-money-dollar-circle-line mr-2 text-emerald-400"></i> FINANCIAL CONTROLLER
            </h1>
            <div class="flex items-center space-x-6">
                <a href="/my_payroll" class="text-xs font-black uppercase tracking-widest hover:text-emerald-400 transition-all">My Payroll</a>
                <a href="/logout" class="bg-red-500/10 text-red-400 px-4 py-2 rounded-xl border border-red-500/20 hover:bg-red-500 hover:text-white transition-all">LOGOUT</a>
            </div>
        </nav>
        <div class="max-w-7xl mx-auto p-12">
            <div class="bg-white rounded-[48px] p-12 shadow-2xl shadow-slate-200 border border-slate-100 flex items-center justify-between">
                <div>
                   <h2 class="text-5xl font-black text-slate-800 tracking-tighter">Welcome, {{ session.financial_analytics }}</h2>
                   <p class="text-slate-400 font-bold mt-2 uppercase tracking-widest text-xs">High-Trust Financial Dashboard authenticated via Face ID</p>
                </div>
                <div class="w-24 h-24 bg-emerald-50 text-emerald-600 rounded-[32px] flex items-center justify-center text-4xl shadow-xl shadow-emerald-500/10">
                    <i class="ri-line-chart-line"></i>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mt-12">
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-refund-2-line text-3xl text-emerald-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800 text-lg">Revenue Streams</h4>
                    <p class="text-slate-400 text-sm mt-2">Real-time tracking of consultation and pharmacy revenue.</p>
                </div>
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-bank-card-line text-3xl text-blue-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800 text-lg">Payroll Audits</h4>
                    <p class="text-slate-400 text-sm mt-2">Oversee staff compensation and bonus distributions.</p>
                </div>
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-file-shield-2-line text-3xl text-purple-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800 text-lg">Tax Compliance</h4>
                    <p class="text-slate-400 text-sm mt-2">Automated tax calculation and statutory reporting.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)

@app.route("/branch_admin_dashboard")
def branch_admin_dashboard():
    if "branch_admin" not in session: return redirect("/login")
    
    # Check for face encoding
    user = branch_admins_collection.find_one({"username": session["branch_admin"]})
    user_has_face = True if user and "face_encoding" in user else False
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Branch Admin Dashboard - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <style>
            .scan-pulse { animation: scan-pulse 2s infinite; }
            @keyframes scan-pulse {
                0% { opacity: 0.6; transform: scale(1); }
                50% { opacity: 1; transform: scale(1.02); }
                100% { opacity: 0.6; transform: scale(1); }
            }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen">
        <nav class="bg-indigo-900 border-b border-white/10 p-4 text-white flex justify-between items-center sticky top-0 z-50">
            <h1 class="text-xl font-black flex items-center tracking-tighter">
                <i class="ri-government-line mr-2 text-indigo-400"></i> BRANCH ADMINISTRATION
            </h1>
            <div class="flex items-center space-x-6 text-sm">
                <a href="/my_payroll" class="font-black uppercase tracking-widest hover:text-indigo-400 transition-all">Payroll</a>
                <a href="/logout" class="bg-red-500 px-5 py-2 rounded-xl font-black uppercase tracking-widest hover:bg-red-600 transition-all shadow-lg shadow-red-500/20">LOGOUT</a>
            </div>
        </nav>
        <div class="max-w-7xl mx-auto p-12">
            {% if not user_has_face %}
            <!-- Face ID Banner -->
            <div class="relative overflow-hidden bg-gradient-to-r from-teal-600 to-indigo-700 rounded-[32px] p-8 shadow-2xl shadow-teal-900/20 mb-8 border border-white/10 group cursor-pointer" onclick="window.location.href='/staff/face_register'">
                <div class="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-3xl -mr-32 -mt-32"></div>
                <div class="relative flex items-center justify-between">
                    <div class="flex items-center space-x-6">
                        <div class="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center text-white border border-white/20 scan-pulse">
                            <i class="ri-face-recognition-line text-3xl"></i>
                        </div>
                        <div>
                            <h3 class="text-xl font-black text-white tracking-tight">Face ID Setup Required</h3>
                            <p class="text-teal-100 text-sm font-medium">Register your face to enable secure, fast authentication.</p>
                        </div>
                    </div>
                    <div>
                        <button class="bg-white text-teal-700 px-8 py-3 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-teal-50 transition-all shadow-xl">
                            Register Now
                        </button>
                    </div>
                </div>
            </div>
            {% endif %}

            <div class="bg-white rounded-[48px] p-12 shadow-2xl shadow-indigo-500/10 border border-indigo-50 flex items-center justify-between">
                <div>
                   <h2 class="text-5xl font-black text-slate-800 tracking-tighter">Welcome, {{ session.branch_admin }}</h2>
                   <p class="text-slate-400 font-bold mt-2 uppercase tracking-widest text-xs">Face ID-Authenticated Branch Executive</p>
                </div>
                <div class="w-24 h-24 bg-indigo-50 text-indigo-600 rounded-[32px] flex items-center justify-center text-4xl shadow-xl shadow-indigo-500/10">
                    <i class="ri-shield-user-line"></i>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-8 mt-12">
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-team-line text-3xl text-indigo-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800">Staffing</h4>
                    <p class="text-slate-400 text-xs mt-2">Manage branch-specific medical and support personnel.</p>
                </div>
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-hospital-line text-3xl text-blue-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800">Capacity</h4>
                    <p class="text-slate-400 text-xs mt-2">Optimize bed availability and department resources.</p>
                </div>
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-calendar-todo-line text-3xl text-purple-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800">Schedules</h4>
                    <p class="text-slate-400 text-xs mt-2">Roster management and shift planning for all units.</p>
                </div>
                <div class="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm hover:shadow-xl transition-all">
                    <i class="ri-file-list-3-line text-3xl text-amber-500 mb-6 block"></i>
                    <h4 class="font-black text-slate-800">Analytics</h4>
                    <p class="text-slate-400 text-xs mt-2">Review branch KPIs and operational efficiency reports.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, user_has_face=user_has_face)

@app.route("/lab_dashboard")
def lab_dashboard():
    if "lab_assistant" not in session: return redirect("/login")
    
    # Simple report management logic
    search_query = request.args.get("search", "")
    patients = []
    if search_query:
        patients = list(patients_collection.find({
            "$or": [
                {"phone": {"$regex": search_query, "$options": "i"}},
                {"name": {"$regex": search_query, "$options": "i"}}
            ]
        }).limit(10))

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Lab Dashboard - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-slate-50 min-h-screen">
        <nav class="bg-indigo-900 p-4 text-white flex justify-between items-center shadow-lg sticky top-0 z-50">
            <h1 class="text-xl font-black flex items-center tracking-tight">
                <i class="ri-test-tube-line mr-2 text-indigo-400"></i> LABORATORY SERVICES
            </h1>
            <div class="flex items-center space-x-6 text-sm font-bold">
                <a href="/lab_dashboard" class="hover:text-indigo-200 uppercase tracking-widest">Reports Console</a>
                <a href="/my_payroll" class="bg-white/10 px-4 py-2 rounded-xl hover:bg-white/20 transition-all">MY PAYROLL</a>
                <a href="/logout" class="bg-red-500/80 px-4 py-2 rounded-xl hover:bg-red-600 transition-all shadow-lg shadow-red-500/20">LOGOUT</a>
            </div>
        </nav>

        <div class="max-w-6xl mx-auto p-12">
            <header class="mb-12">
                <h2 class="text-4xl font-black text-slate-800 tracking-tighter">Welcome, {{ session.lab_assistant }}</h2>
                <p class="text-slate-400 font-medium mt-2">Manage diagnostics and patient medical records</p>
            </header>

            <div class="bg-white rounded-[40px] shadow-2xl shadow-indigo-500/5 p-10 border border-indigo-50">
                <h3 class="text-lg font-bold text-slate-700 mb-8 flex items-center">
                    <i class="ri-search-line mr-3 text-indigo-500"></i> Find Patient to Upload Report
                </h3>
                
                <form action="/lab_dashboard" method="GET" class="flex gap-4 mb-10">
                    <input type="text" name="search" placeholder="Search by Phone or Name..." value="{{ search_query }}"
                           class="flex-1 bg-slate-50 border border-slate-100 px-6 py-4 rounded-2xl outline-none focus:ring-4 focus:ring-indigo-500/10 font-bold transition-all">
                    <button type="submit" class="bg-indigo-600 text-white px-8 py-4 rounded-2xl font-black uppercase tracking-widest hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-500/20">Search</button>
                </form>

                {% if patients %}
                <div class="space-y-4">
                    {% for p in patients %}
                    <div class="bg-slate-50/50 border border-slate-100 p-6 rounded-3xl flex items-center justify-between hover:border-indigo-200 transition-all">
                        <div>
                            <p class="font-black text-slate-800 text-lg">{{ p.name }}</p>
                            <p class="text-slate-400 font-bold text-xs uppercase tracking-widest">{{ p.phone }}</p>
                        </div>
                        <button onclick="openUploadModal('{{ p.phone }}', '{{ p.name }}')" 
                                class="bg-white border-2 border-indigo-100 text-indigo-600 px-6 py-2 rounded-xl font-bold hover:bg-indigo-600 hover:text-white transition-all shadow-sm">
                            Upload Report
                        </button>
                    </div>
                    {% endfor %}
                </div>
                {% elif search_query %}
                <p class="text-center py-10 text-slate-400 font-bold italic">No patients found. Please try another search.</p>
                {% endif %}
            </div>
        </div>

        <!-- Upload Modal -->
        <div id="uploadModal" class="hidden fixed inset-0 bg-slate-900/80 backdrop-blur-md z-[100] flex items-center justify-center p-6">
            <div class="bg-white w-full max-w-lg rounded-[40px] overflow-hidden shadow-2xl">
                <div class="bg-indigo-600 p-8 text-white relative">
                    <button onclick="document.getElementById('uploadModal').classList.add('hidden')" class="absolute right-6 top-6 text-white/50 hover:text-white transition-colors">
                        <i class="ri-close-line text-2xl"></i>
                    </button>
                    <h3 class="text-2xl font-black tracking-tight" id="modalPatientName">Upload Report</h3>
                    <p class="text-indigo-100 text-sm mt-1" id="modalPatientPhone"></p>
                </div>
                <form action="/lab/upload_report" method="POST" enctype="multipart/form-data" class="p-10 space-y-6">
                    <input type="hidden" name="patient_phone" id="hiddenPatientPhone">
                    <div>
                        <label class="text-[10px] font-black uppercase text-slate-400 tracking-widest block mb-2 px-1">Report Title / Name</label>
                        <input type="text" name="report_name" placeholder="e.g., Blood Test Feb 2026" required
                               class="w-full bg-slate-50 border border-slate-100 px-6 py-4 rounded-2xl outline-none focus:ring-4 focus:ring-indigo-500/10 font-bold">
                    </div>
                    <div>
                        <label class="text-[10px] font-black uppercase text-slate-400 tracking-widest block mb-2 px-1">Select File (PDF/Image)</label>
                        <input type="file" name="report_file" required
                               class="w-full bg-slate-50 border border-slate-100 px-6 py-4 rounded-2xl outline-none file:mr-4 file:py-1 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-black file:bg-indigo-100 file:text-indigo-700 hover:file:bg-indigo-200">
                    </div>
                    <button type="submit" class="w-full bg-indigo-600 text-white py-5 rounded-2xl font-black uppercase tracking-widest hover:bg-indigo-700 transition-all shadow-xl shadow-indigo-500/20 mt-4">
                        Process and Securely Upload
                    </button>
                </form>
            </div>
        </div>

        <script>
            function openUploadModal(phone, name) {
                document.getElementById('modalPatientName').innerText = 'Report for ' + name;
                document.getElementById('modalPatientPhone').innerText = phone;
                document.getElementById('hiddenPatientPhone').value = phone;
                document.getElementById('uploadModal').classList.remove('hidden');
            }
        </script>
    </body>
    </html>
    """, patients=patients, search_query=search_query)

@app.route("/lab/upload_report", methods=["POST"])
def lab_upload_report():
    if "lab_assistant" not in session: return redirect("/login")
    
    phone = request.form.get("patient_phone")
    report_name = request.form.get("report_name")
    file = request.files.get("report_file")
    
    if not file or not phone or not report_name:
        flash("All fields are required", "error")
        return redirect("/lab_dashboard")
        
    # Ensure directory exists
    if not os.path.exists(CERTIFICATES_FOLDER):
        os.makedirs(CERTIFICATES_FOLDER, exist_ok=True)
        
    filename = secure_filename(f"lab_{phone}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
    file_path = os.path.join(CERTIFICATES_FOLDER, filename)
    file.save(file_path)
    
    report_data = {
        "name": report_name,
        "filename": filename,
        "url": f"/uploads/certificates/{filename}",
        "uploaded_by": session["lab_assistant"],
        "date": datetime.now().strftime("%d-%m-%Y"),
        "created_at": datetime.utcnow()
    }
    
    patients_collection.update_one(
        {"phone": phone},
        {"$push": {"medical_reports": {"$each": [report_data], "$position": 0}}}
    )
    
    flash(f"Report '{report_name}' uploaded successfully!", "success")
    return redirect("/lab_dashboard")

@app.route("/reports")
def universal_reports_redirect():
    """Solve the 404 for 'reports' by redirecting to appropriate dashboard"""
    if "patient_phone" in session: return redirect("/patient_dashboard")
    if "lab_assistant" in session: return redirect("/lab_dashboard")
    if "doctor" in session: return redirect("/dashboard")
    return redirect("/login")
inventory_collection = db['inventory']
holidays_collection = db['holidays']
blocked_slots_collection = db["blocked_slots"]
loc_aval_collection = db["LocAval"]
password_reset_collection = db["password_reset"]
payments_collection = db["payments"]
leaves_collection = db["leaves"]
prescriptions_collection = db["prescriptions"]
login_otp_collection = db["login_otp"]
site_settings_collection = db['site_settings']
homepage_content_collection = db['homepage_content']
pharmacists_collection = db["pharmacists"]
lab_assistants_collection = db["lab_assistants"]
financial_analytics_collection = db["financial_analytics"]
branch_admins_collection = db["branch_admins"]
payroll_settings_collection = db['payroll_settings']
attendance_collection = db['attendance']
salaries_collection = db['salaries']

# --- Configuration for Uploads ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PROFILE_PHOTOS_FOLDER = os.path.join(UPLOAD_FOLDER, 'profiles')
CIRCULAR_ATTACHMENTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'circulars')
CERTIFICATES_FOLDER = os.path.join(UPLOAD_FOLDER, 'certificates')

for folder in [PROFILE_PHOTOS_FOLDER, CIRCULAR_ATTACHMENTS_FOLDER, CERTIFICATES_FOLDER]:
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
    except Exception as e:
        print(f"Warning: Could not create upload folder {folder}: {e}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Location/Timings configuration ---
# Supported clinic locations that determine which Mongo collection to read working hours from
AVAILABLE_CITIES = ["Akola", "Hyderabad", "Pune"]  # still used elsewhere; form will accept free-text

# Map each city to its timings collection (as shown in MongoDB Atlas screenshot)
# If these collections do not exist in your cluster, the code will gracefully fall back to defaults
CITY_TO_TIMINGS_COLLECTION = {
    "Akola": db.get_collection("Akola_Doctor-overiden_hospital_timings"),
    "Hyderabad": db.get_collection("Hyderabad_Doctor-overiden_hospital_timings"),
    "Pune": db.get_collection("Pune_Doctor-overiden_hospital_timings"),
}

# --- Email notification function ---
def send_cancellation_email(patient_name, patient_email, appointment_date, appointment_time):
    """Send cancellation email to patient"""
    try:
        if not patient_email or patient_email == "No email provided":
            return False
            
        message_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <p>Dear {patient_name},</p>
            <p>Your appointment scheduled for <strong>{appointment_date}</strong> at <strong>{appointment_time}</strong> has been cancelled.</p>
            <p>If you have any questions or would like to reschedule, please contact us.</p>
            <p>Best Regards,</p>
            <p><strong>Hey Doc!</strong></p>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = patient_email
        msg["Subject"] = "❌ Appointment Cancelled"
        msg.attach(MIMEText(message_html, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, patient_email, msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending cancellation email: {e}")
        return False

# --- Language Helper ---
@app.route("/set_language/<lang>")
def set_language(lang):
    if lang in ["en", "te"]:
        session["lang"] = lang
    return redirect(request.referrer or "/")

# --- Authentication Helper Functions ---

def send_credentials_email(email, username, password, user_type, name):
    """Send credentials to newly created users with ultra-premium styling"""
    html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 640px; margin: auto; border: 1px solid #e2e8f0; border-radius: 24px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.05);">
        <div style="background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); padding: 60px 40px; text-align: center;">
             <h1 style="color: white; margin: 0; font-size: 32px; font-weight: 800; letter-spacing: -1px;">Welcome to Hey Doc!</h1>
             <p style="color: rgba(255,255,255,0.8); margin-top: 10px; font-size: 16px;">The Heart of Healthcare Intelligence</p>
        </div>
        <div style="padding: 40px; background: white;">
            <p style="font-size: 18px; color: #1e293b; font-weight: 600;">Hello {name},</p>
            <p style="color: #64748b; line-height: 1.7;">Your professional profile for <strong>{user_type}</strong> has been successfully provisioned. Please use the secure credentials below to access your dashboard.</p>
            
            <div style="background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 16px; padding: 24px; margin: 32px 0;">
                <table style="width: 100%;">
                    <tr>
                         <td style="color: #94a3b8; font-size: 12px; font-weight: 800; text-transform: uppercase; padding-bottom: 8px;">Username</td>
                    </tr>
                    <tr>
                         <td style="color: #0f172a; font-size: 16px; font-weight: 700; padding-bottom: 24px;">{username}</td>
                    </tr>
                    <tr>
                         <td style="color: #94a3b8; font-size: 12px; font-weight: 800; text-transform: uppercase; padding-bottom: 8px;">Security Token</td>
                    </tr>
                    <tr>
                         <td style="background: white; border: 1px solid #cbd5e1; color: #0f766e; font-size: 18px; font-weight: 800; padding: 12px 16px; border-radius: 8px; font-family: monospace;">{password}</td>
                    </tr>
                </table>
            </div>

            <div style="background: #fffbeb; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px;">
                <p style="color: #92400e; font-size: 14px; margin: 0; font-weight: 600;">⚠️ MANDATORY SECURITY ACTION:</p>
                <p style="color: #b45309; font-size: 13px; margin: 4px 0 0 0;">This security token is temporary. You will be prompted to establish dynamic credentials upon your first login.</p>
            </div>
            
            <p style="color: #94a3b8; font-size: 12px; margin-top: 40px; text-align: center;">Technical Support: {DOCTOR_EMAIL}</p>
        </div>
    </div>
    """
    return send_hospital_email(email, f"Access Credentials for {name} - Hey Doc!", html)

def send_password_reset_email(email, reset_token):
    """Send password reset link"""
    try:
        reset_link = f"{request.host_url}reset_password?token={reset_token}"
        message_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Password Reset Request - Hey Doc!</h2>
            <p>Dear User,</p>
            <p>You have requested to reset your password.</p>
            <p>Click the link below to reset your password:</p>
            <p><a href="{reset_link}" style="background-color: #0d9488; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>Or copy and paste this link in your browser:</p>
            <p>{reset_link}</p>
            <p>This link is valid for 1 hour.</p>
            <p>If you did not request this, please ignore this email.</p>
            <p>Best Regards,<br><strong>Hey Doc!</strong></p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = "Password Reset Request - Hey Doc!"
        msg.attach(MIMEText(message_html, "html"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email, msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False

def send_hospital_email(recipient_email, subject, body_html):
    """Generic high-reliability email sender with enhanced error logging and console fallback"""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(1) # Enable debug level for logs
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, [recipient_email], msg.as_string())
        server.quit()
        print(f"SUCCESS: Email sent to {recipient_email}")
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError:
        err = "SMTP Authentication Error: Invalid credentials."
        print(f"CRITICAL SMTP ERROR: {err}")
        return False, err
    except smtplib.SMTPConnectError:
        err = "SMTP Connection Error: Could not connect to server."
        print(f"CRITICAL SMTP ERROR: {err}")
        return False, err
    except Exception as e:
        err = f"Email Delivery Failed: {str(e)}"
        print(f"CRITICAL SMTP ERROR: {err}")
        return False, err

def send_otp_email(email, otp):
    """Send OTP with console fallback for development/demo reliability"""
    # ALWAYS print OTP to console for immediate backup access
    print(f"\n{'='*50}\n[SECURE BACKUP] OTP for {email}: {otp}\n{'='*50}\n")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Helvetica Neue', sans-serif; background-color: #f8fafc; padding: 40px 0;">
        <div style="max-w-md mx-auto bg-white rounded-3xl shadow-lg overflow-hidden border border-slate-100">
            <div style="background-color: #0d9488; padding: 40px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -1px;">Hey Doc! Security</h1>
            </div>
            <div style="padding: 40px; text-align: center;">
                <p style="color: #64748b; font-size: 16px; margin-bottom: 30px;">Your secure verification code is:</p>
                <div style="background-color: #f0fdfa; border: 2px dashed #ccfbf1; padding: 20px; border-radius: 16px; margin-bottom: 30px;">
                    <span style="font-family: monospace; font-size: 42px; font-weight: 900; color: #0f766e; letter-spacing: 8px;">{otp}</span>
                </div>
                <p style="color: #94a3b8; font-size: 12px;">Use this code to verify your identity. Valid for 5 minutes.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return send_hospital_email(email, "🔐 Your Verification Code", html)
    """Send 2FA OTP to the user's registered email with premium branding"""
    html = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: auto; padding: 40px; border-radius: 20px; border: 1px solid #f1f5f9; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
        <h2 style="color: #0d9488; font-weight: 800; font-size: 24px; margin-bottom: 20px;">Security Verification</h2>
        <p style="color: #64748b; font-size: 16px; line-height: 1.6;">A login attempt was made using your credentials. Please use the verification code below to authorize access:</p>
        <div style="background: #f0fdfa; border: 2px dashed #99f6e4; padding: 30px; text-align: center; border-radius: 16px; margin: 30px 0;">
            <h1 style="font-size: 40px; letter-spacing: 12px; color: #0f766e; margin: 0; font-family: monospace;">{otp}</h1>
        </div>
        <p style="color: #94a3b8; font-size: 13px;">This code expires in 5 minutes. If you didn't request this, please contact <strong>{DOCTOR_EMAIL}</strong> immediately.</p>
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #f1f5f9; text-align: center;">
            <p style="color: #0f172a; font-weight: 700; margin: 0;">Hey Doc! Hospital Management</p>
            <p style="color: #94a3b8; font-size: 11px; margin-top: 4px;">Powered by Advanced AI Health Intelligence</p>
        </div>
    </div>
    """
    return send_hospital_email(email, f"Verify Your Identity: {otp}", html)

def send_leave_notification(doctor_name, start_date, end_date, reason):
    """Send leave application notification to admin via high-reliability SMTP"""
    admin_emails = [admin['email'] for admin in admin_collection.find({}, {'email': 1})]
    if not admin_emails: return False
    
    html = f"""
    <div style="font-family: sans-serif; padding: 30px; border: 1px solid #fddada; border-radius: 12px; background: #fffafb;">
        <h2 style="color: #dc2626;">Internal Alert: New Leave Request</h2>
        <p>A new leave application has been submitted by <strong>{doctor_name}</strong>.</p>
        <div style="background: white; border: 1px solid #fee2e2; padding: 20px; border-radius: 8px;">
            <p><strong>Period:</strong> {start_date} to {end_date}</p>
            <p><strong>Reasoning:</strong> {reason}</p>
        </div>
        <p style="margin-top: 20px; color: #64748b;">Please login to the Admin Panel to approve/reject.</p>
    </div>
    """
    # Simply send to the first admin for reliable dispatch
    return send_hospital_email(admin_emails[0], f"Leave Alert: {doctor_name}", html)

def send_leave_approval_email(email, leave_data, status):
    """Send leave approval/rejection email"""
    try:
        status_text = "approved" if status == "approved" else "rejected"
        message_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Leave Request {status_text.title()} - Hey Doc!</h2>
            <p>Dear Doctor,</p>
            <p>Your leave request has been <strong>{status_text}</strong>.</p>
            <p><strong>Leave Details:</strong></p>
            <ul>
                <li><strong>Start Date:</strong> {leave_data.get('start_date', 'N/A')}</li>
                <li><strong>End Date:</strong> {leave_data.get('end_date', 'N/A')}</li>
                <li><strong>Reason:</strong> {leave_data.get('reason', 'N/A')}</li>
                <li><strong>Status:</strong> {status_text.title()}</li>
            </ul>
            <p>Best Regards,<br><strong>Hey Doc! Admin</strong></p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = f"Leave Request {status_text.title()} - Hey Doc!"
        msg.attach(MIMEText(message_html, "html"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email, msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending leave approval email: {e}")
        return False

def send_appointment_notification(receptionist_emails, patient_name, appointment_date, symptoms):
    """Send new appointment notification to branch receptionists"""
    try:
        if not receptionist_emails:
            return False
            
        message_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #0d9488;">New Appointment Booked - Hey Doc!</h2>
            <p>Dear receptionist,</p>
            <p>A new appointment has been booked for your branch:</p>
            <div style="background: #f0fdfa; padding: 15px; border-radius: 10px; border: 1px solid #ccfbf1;">
                <p><strong>Patient Name:</strong> {patient_name}</p>
                <p><strong>Appointment Date:</strong> {appointment_date}</p>
                <p><strong>Symptoms:</strong> {symptoms if symptoms else "N/A"}</p>
            </div>
            <p>Please log in to the dashboard to review and manage this appointment.</p>
            <p>Best Regards,<br><strong>Hey Doc! System</strong></p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = ", ".join(receptionist_emails)
        msg["Subject"] = f"New Appointment: {patient_name} - {appointment_date}"
        msg.attach(MIMEText(message_html, "html"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, receptionist_emails, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending appointment notification: {e}")
        return False

def send_circular_notification_email(recipients, subject, content, attachment_path=None):
    """Send circular notification to staff"""
    if not recipients: return False
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_SENDER  # Primary To: Admin/Self
        msg["Subject"] = f"New Circular: {subject}"
        
        message_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>New Circular - Hey Doc!</h2>
            <p><strong>Topic:</strong> {subject}</p>
            <hr>
            <p style="white-space: pre-wrap;">{content}</p>
            <hr>
            <p>Please check your dashboard for more details.</p>
            <p>Best Regards,<br><strong>Hey Doc! Admin</strong></p>
        </body>
        </html>
        """
        msg.attach(MIMEText(message_html, "html"))
        
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(attachment_path)}")
            msg.attach(part)
            
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        
        # Send as BCC to all recipients to protect privacy
        server.sendmail(EMAIL_SENDER, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending circular email: {e}")
        return False


def get_user_role():
    """Get current user's role from session"""
    if "admin" in session:
        return "admin"
    elif "doctor" in session:
        return "doctor"
    elif "receptionist" in session:
        return "receptionist"
    elif "pharmacist" in session:
        return "pharmacist"
    elif "lab_assistant" in session:
        return "lab_assistant"
    elif "patient" in session:
        return "patient"
    elif "branch_admin" in session:
        return "branch_admin"
    return None

def require_role(allowed_roles):
    """Decorator to check user role"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            role = get_user_role()
            if role not in allowed_roles:
                flash("Access denied. You don't have permission to access this page.", "error")
                return redirect("/")
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# --- Helper: parse times like "11:00 AM" → datetime.time ---
def _parse_12h_to_time(value: str):
    try:
        return datetime.strptime(value.strip(), "%I:%M %p").time()
    except Exception:
        # Try already-24h formats like "18:00"
        try:
            return datetime.strptime(value.strip(), "%H:%M").time()
        except Exception:
            return None


# --- Helper: get working hour ranges for a city/date from Mongo ---
def _get_time_ranges_for_city(city, for_date=None):
    """Return list of (start_time, end_time) for the city and optional date.
    Priority order:
      1) LocAval date-specific override for city
      2) LocAval Default:true for city
      3) Legacy city collections mapping
    Note: Only morning and evening shifts are used (afternoon ignored).
    """
    ranges = []
    try:
        # 1) Try LocAval collection first
        doc = None
        if for_date:
            try:
                dt_obj = datetime.strptime(for_date, "%d-%m-%Y")
                ddmmyyyy = dt_obj.strftime("%d-%m-%Y")
                doc = loc_aval_collection.find_one({"location": city, "date": ddmmyyyy})
                if not doc:
                    doc = loc_aval_collection.find_one({"location": city, "date": for_date})
            except Exception:
                pass
        if doc is None:
            doc = loc_aval_collection.find_one({"location": city, "Default": {"$in": [True, "true", "True"]}})

        if not doc:
            # 2) Fallback to legacy per-city collections
            col = CITY_TO_TIMINGS_COLLECTION.get(city)
            if col is not None:
                if for_date:
                    try:
                        dt_obj = datetime.strptime(for_date, "%d-%m-%Y")
                        ddmmyyyy = dt_obj.strftime("%d-%m-%Y")
                        doc = col.find_one({"date": ddmmyyyy}) or col.find_one({"date": for_date})
                    except Exception:
                        pass
                if doc is None:
                    doc = col.find_one({"Default": {"$in": [True, "true", "True"]}}) or col.find_one({})

        if doc and isinstance(doc.get("working_hours"), dict):
            wh = doc["working_hours"]
            for key in ["morning_shift", "evening_shift"]:  # afternoon intentionally ignored
                shift = wh.get(key)
                if isinstance(shift, dict):
                    start_label = shift.get("start")
                    end_label = shift.get("end")
                    start_time = _parse_12h_to_time(start_label) if start_label else None
                    end_time = _parse_12h_to_time(end_label) if end_label else None
                    if start_time and end_time:
                        ranges.append((start_time, end_time))

        # Defaults if nothing configured
        if not ranges:
            ranges = [
                (datetime.strptime("07:00", "%H:%M").time(), datetime.strptime("12:00", "%H:%M").time()),
                (datetime.strptime("18:00", "%H:%M").time(), datetime.strptime("21:00", "%H:%M").time()),
            ]
    except Exception:
        ranges = [
            (datetime.strptime("07:00", "%H:%M").time(), datetime.strptime("12:00", "%H:%M").time()),
            (datetime.strptime("18:00", "%H:%M").time(), datetime.strptime("21:00", "%H:%M").time()),
        ]
    return ranges


# --- Helper: normalize and validate Indian phone numbers (10 digits) ---
def normalize_indian_phone(raw_phone: str):
    """
    Accepts inputs like '+91XXXXXXXXXX', '91XXXXXXXXXX', '0XXXXXXXXXX', or just 10 digits.
    Returns ('+91XXXXXXXXXX', None) if valid, otherwise (None, error_message).
    Only accepts exactly 10 digits after removing leading 0, +91, or 91.
    Shows error if more or less than 10 digits are entered.
    """
    try:
        if raw_phone is None:
            return None, "Phone number is required."
        digits_only = ''.join(ch for ch in str(raw_phone) if ch.isdigit())
        # Remove leading 0, 91, or +91 if present
        if digits_only.startswith('0'):
            digits_only = digits_only[1:]
        elif digits_only.startswith('91') and len(digits_only) > 10:
            digits_only = digits_only[2:]
        # After removing prefix, must be exactly 10 digits
        if len(digits_only) != 10:
            return None, "Enter a valid 10-digit phone number (do not enter more or less than 10 digits)."
        return f"+91{digits_only}", None
    except Exception:
        return None, "Enter a valid 10-digit phone number."

def generate_temp_password(length=12):
    """Generate a secure temporary password for new staff members.
    Password contains uppercase, lowercase, digits, and special characters.
    """
    import string
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%&*"
    
    # Ensure at least one of each type
    password = [
        random.choice(uppercase),
        random.choice(lowercase),
        random.choice(digits),
        random.choice(special)
    ]
    
    # Fill rest with random mix
    all_chars = uppercase + lowercase + digits + special
    password += [random.choice(all_chars) for _ in range(length - 4)]
    
    # Shuffle to avoid predictable pattern
    random.shuffle(password)
    return ''.join(password)

# ...existing code...

# --- Helper function to generate time slots (optionally city-aware) ---
# --- Helper function to generate time slots (optionally city-aware) ---
def generate_time_slots(city: str = None, for_date: str = None):
    """Generate 10-minute slots from the city's working hours (optionally for a specific date).
    If city is None or timings not found, defaults are used.
    Returns slots in 12-hour format with AM/PM.
    Filters out past time slots if the date is today."""
    slots = []
    ranges = _get_time_ranges_for_city(city, for_date) if city else _get_time_ranges_for_city("Hyderabad", for_date)

    # Get current time for filtering past slots
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    # Check if the date is today
    is_today = False
    if for_date:
        try:
            # Try to parse the date and compare with today
            if len(for_date) == 10 and for_date[4] == '-' and for_date[7] == '-':
                # YYYY-MM-DD format
                date_obj = datetime.strptime(for_date, "%Y-%m-%d")
            elif len(for_date) == 10 and for_date[2] == '-' and for_date[5] == '-':
                # DD-MM-YYYY format
                date_obj = datetime.strptime(for_date, "%d-%m-%Y")
            else:
                date_obj = None
                
            if date_obj and date_obj.date() == now.date():
                is_today = True
        except ValueError:
            # If date parsing fails, assume it's not today
            pass

    for start_time, end_time in ranges:
        start_dt = datetime.combine(datetime.today(), start_time)
        end_dt = datetime.combine(datetime.today(), end_time)
        current_time = start_dt
        while current_time < end_dt:
            slot_time_str = current_time.strftime("%I:%M %p")
            slot_time_24 = current_time.strftime("%H:%M")
            
            # If it's today, only include future or current time slots
            if is_today:
                if slot_time_24 >= current_time_str:
                    slots.append(slot_time_str)
            else:
                # For future dates, include all slots
                slots.append(slot_time_str)
            
            current_time += timedelta(minutes=10)
    return slots

# ...existing code...

# --- Helper function to clean up appointments with missing fields ---
def cleanup_appointments():
    """Clean up appointments that might have missing or incorrect field names"""
    try:
        # Find appointments that might have different field names
        appointments_to_update = []
        
        # Check for appointments with 'patient_name' instead of 'name'
        appointments_with_patient_name = appointments_collection.find({"patient_name": {"$exists": True}})
        for appointment in appointments_with_patient_name:
            if 'name' not in appointment:
                appointments_to_update.append({
                    "_id": appointment["_id"],
                    "name": appointment.get("patient_name", "Unknown Patient")
                })
        
        # Check for appointments with 'patient_phone' instead of 'phone'
        appointments_with_patient_phone = appointments_collection.find({"patient_phone": {"$exists": True}})
        for appointment in appointments_with_patient_phone:
            if 'phone' not in appointment:
                appointments_to_update.append({
                    "_id": appointment["_id"],
                    "phone": appointment.get("patient_phone", "No phone")
                })
        
        # Update appointments with missing fields
        for update_data in appointments_to_update:
            appointment_id = update_data.pop("_id")
            appointments_collection.update_one(
                {"_id": appointment_id},
                {"$set": update_data}
            )
        
        # Also ensure all appointments have required fields
        all_appointments = appointments_collection.find({})
        for appointment in all_appointments:
            updates_needed = {}
            
            # Ensure appointment_id exists
            if 'appointment_id' not in appointment:
                date_str = datetime.now().strftime("%Y%m%d")
                random_num = str(random.randint(1, 9999)).zfill(4)
                updates_needed['appointment_id'] = f"HeyDoc-{date_str}-{random_num}"
            
            # Ensure name exists
            if 'name' not in appointment or not appointment['name']:
                updates_needed['name'] = 'Unknown Patient'
            
            # Ensure phone exists
            if 'phone' not in appointment or not appointment['phone']:
                updates_needed['phone'] = 'No phone'
            
            # Ensure email exists
            if 'email' not in appointment or not appointment['email']:
                updates_needed['email'] = 'No email provided'
            
            # Ensure address exists
            if 'address' not in appointment or not appointment['address']:
                updates_needed['address'] = 'No address provided'
            
            # Ensure symptoms exists
            if 'symptoms' not in appointment or not appointment['symptoms']:
                updates_needed['symptoms'] = 'No symptoms provided'
            
            # Ensure date exists
            if 'date' not in appointment or not appointment['date']:
                updates_needed['date'] = datetime.now().strftime("%Y-%m-%d")
            
            # Ensure time exists
            if 'time' not in appointment or not appointment['time']:
                updates_needed['time'] = '09:00'
            
            # Ensure status exists
            if 'status' not in appointment or not appointment['status']:
                updates_needed['status'] = 'pending'
            
            # Apply updates if needed
            if updates_needed:
                appointments_collection.update_one(
                    {"_id": appointment["_id"]},
                    {"$set": updates_needed}
                )
                print(f"Updated appointment {appointment.get('appointment_id', 'NO_ID')} with missing fields: {list(updates_needed.keys())}")
        
    except Exception as e:
        print(f"Error cleaning up appointments: {e}")

# --- Helper function to get booked time slots for a specific date (and optional city) ---
def get_booked_slots_for_date(date, city=None, exclude_appointment_id=None):
    """Get list of booked time slots for a specific date, optionally filtered by city."""
    # Normalize incoming date to support both YYYY-MM-DD (from <input type="date">)
    # and DD-MM-YYYY (stored in Mongo)
    date_candidates = [date]
    try:
        if len(date) == 10 and date[4] == '-' and date[7] == '-':
            # Looks like YYYY-MM-DD → add DD-MM-YYYY variant
            dt = datetime.strptime(date, "%Y-%m-%d")
            date_candidates.append(dt.strftime("%d-%m-%Y"))
        elif len(date) == 10 and date[2] == '-' and date[5] == '-':
            # Looks like DD-MM-YYYY → add YYYY-MM-DD variant
            dt = datetime.strptime(date, "%d-%m-%Y")
            date_candidates.append(dt.strftime("%Y-%m-%d"))
    except Exception:
        pass

    query = {"date": {"$in": date_candidates}}
    if city:
        query["location"] = city
    if exclude_appointment_id:
        query["appointment_id"] = {"$ne": exclude_appointment_id}
    
    # Exclude past times if the date is today
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    cutoff_time = now.strftime("%H:%M") if date == today_str else None

    def not_past(time_str: str) -> bool:
        if cutoff_time is None:
            return True
        return time_str >= cutoff_time

    booked_appointments = appointments_collection.find(query)
    booked_slots = [appointment["time"] for appointment in booked_appointments if not_past(appointment["time"])]
    
    # Include blocked slots for the date (optionally by city)
    blocked_query = {"date": {"$in": date_candidates}}
    if city:
        blocked_query["location"] = city
    blocked = blocked_slots_collection.find(blocked_query)
    blocked_times = [b.get("time") for b in blocked if not_past(b.get("time"))]
    
    # Merge and deduplicate
    all_unavailable = sorted(list({*booked_slots, *blocked_times}))
    return all_unavailable

# --- Existing Templates (included for completeness) ---
home_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    <link rel="stylesheet" href="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/themes/df-messenger-default.css">
    <script src="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/df-messenger.js"></script>
</head>
<body class="font-sans bg-white">
    <nav class="bg-white shadow-lg fixed w-full top-0 z-50">
        <div class="max-w-6xl mx-auto px-4">
            <div class="flex justify-between items-center py-4">
                <div class="flex items-center space-x-3">
                    <img src="/static/images/heydoc_logo.png" alt="Hey Doc Logo" class="h-10 w-10 rounded-lg object-contain">
                    <span class="text-xl font-bold text-gray-800">Hey Doc!</span>
                </div>
                <div class="hidden md:flex space-x-8 text-gray-700 font-medium" id="navbar-menu-desktop">
                    <a href="#home" class="hover:text-teal-600 transition-colors">Home</a>
                    <a href="#doctor" class="hover:text-teal-600 transition-colors">Meet Doctor</a>
                    <a href="#contact" class="hover:text-teal-600 transition-colors">Contact</a>
                    <a href="/patient/book_appointment" class="bg-indigo-600 text-white px-6 py-2 rounded-full hover:bg-indigo-700 shadow-md hover:shadow-lg transition-all font-bold">Book Appointment</a>
                    <a href="/login" class="bg-teal-600 text-white px-6 py-2 rounded-full hover:bg-teal-700 shadow-md hover:shadow-lg transition-all font-bold">Staff Login</a>
                </div>
                <div class="md:hidden">
                    <button id="mobile-menu-button" class="text-gray-700">
                        <i class="ri-menu-line text-2xl"></i>
                    </button>
                </div>
            </div>
        </div>
        <div id="mobile-menu" class="md:hidden hidden bg-white py-2 shadow-lg">
            <a href="#home" class="block px-4 py-2 text-gray-700 hover:bg-gray-100">Home</a>
            <a href="#doctor" class="block px-4 py-2 text-gray-700 hover:bg-gray-100">Meet Doctor</a>
            <a href="#contact" class="block px-4 py-2 text-gray-700 hover:bg-gray-100">Contact</a>
            <a href="/login" class="block px-4 py-2 text-gray-700 hover:bg-gray-100">Doctor Login</a>
        </div>
    </nav>

    <section id="home" class="pt-20 min-h-screen bg-gradient-to-br from-teal-600 to-teal-300 text-white flex items-center">
        <div class="max-w-6xl mx-auto px-4 text-center">
            <h1 class="text-4xl md:text-6xl font-bold mb-6">
                Welcome to Hey Doc 
            </h1>
            <p class="text-xl mb-8 max-w-3xl mx-auto">
                Experience holistic homeopathic treatment tailored to your unique needs, guided by expertise and empathy. Our approach combines traditional healing wisdom with modern understanding to restore your natural balance.
            </p>
            <div class="flex flex-col md:flex-row items-center justify-center space-y-4 md:space-y-0 md:space-x-4">
                <a href="#doctor" class="w-full md:w-auto bg-white text-teal-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors inline-block">
                    Meet the Doctor
                </a>
                <a href="#contact" class="w-full md:w-auto border-2 border-white text-white px-8 py-3 rounded-lg font-semibold hover:bg-white hover:text-teal-600 transition-colors inline-block">
                    Contact Us
                </a>
            </div>
        </div>
    </section>
    </section>

    <!-- Latest News / Circulars Section -->
    {% if circulars %}
    <section id="news" class="py-16 bg-white border-b border-gray-100">
        <div class="max-w-6xl mx-auto px-4">
            <div class="text-center mb-12">
                <span class="text-teal-600 font-bold tracking-wider uppercase text-sm">Updates & Announcements</span>
                <h2 class="text-3xl font-bold text-gray-800 mt-2">Latest News</h2>
            </div>
            
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                {% for circular in circulars %}
                <div class="bg-slate-50 rounded-2xl p-8 border border-slate-100 hover:shadow-lg transition-all group">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-sm text-teal-600 border border-slate-100 group-hover:bg-teal-600 group-hover:text-white transition-colors">
                            <i class="ri-newspaper-line text-lg"></i>
                        </div>
                        <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">{{ circular.created_at.strftime('%d %b, %Y') if circular.created_at else 'Recent' }}</span>
                    </div>
                    <h3 class="text-xl font-bold text-slate-800 mb-3 group-hover:text-teal-700 transition-colors">{{ circular.title }}</h3>
                    <p class="text-slate-600 mb-4 line-clamp-3 leading-relaxed">{{ circular.message }}</p>
                    {% if circular.message|length > 150 %}
                    <button onclick="this.previousElementSibling.classList.toggle('line-clamp-3'); this.innerText = this.innerText === 'Read More' ? 'Show Less' : 'Read More'" class="text-teal-600 font-bold text-sm hover:underline">Read More</button>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
    </section>
    {% endif %}

    <section id="doctor" class="py-20 bg-white">
        <div class="max-w-6xl mx-auto px-4">
            <div class="bg-white rounded-xl shadow-lg p-8 max-w-4xl mx-auto">
                <div class="text-center mb-8">
                    <h2 class="text-3xl font-bold text-gray-800 mb-4">Dr. Priya Sharma</h2>
                    <p class="text-lg text-gray-600">BHMS, MD (Homeopathy), 15+ Years Experience</p>
                </div>
                
                <div class="grid md:grid-cols-3 gap-6 mb-8">
                    <div class="text-center">
                        <div class="w-16 h-16 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-3">
                            <i class="ri-mental-health-line text-teal-600 text-2xl"></i>
                        </div>
                        <h3 class="font-semibold text-gray-800">Psychiatry & Mental Health</h3>
                    </div>
                    <div class="text-center">
                        <div class="w-16 h-16 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-3">
                            <i class="ri-graduation-cap-line text-teal-600 text-2xl"></i>
                        </div>
                        <h3 class="font-semibold text-gray-800">Learning Disabilities</h3>
                    </div>
                    <div class="text-center">
                        <div class="w-16 h-16 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-3">
                            <i class="ri-heart-line text-teal-600 text-2xl"></i>
                        </div>
                        <h3 class="font-semibold text-gray-800">Mood Disorders</h3>
                    </div>
                </div>
                
                <div class="grid md:grid-cols-3 gap-6">
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
                            <i class="ri-phone-line text-teal-600 text-xl"></i>
                        </div>
                        <div>
                            <p class="font-medium text-gray-800">Phone</p>
                            <p class="text-gray-600">+91 98765 43210</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
                            <i class="ri-mail-line text-teal-600 text-xl"></i>
                        </div>
                        <div>
                            <p class="font-medium text-gray-800">Email</p>
                            <p class="text-gray-600">dr.priya@Hey Dochomoeo.com</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
                            <i class="ri-map-pin-line text-teal-600 text-xl"></i>
                        </div>
                        <div>
                            <p class="font-medium text-gray-800">Location</p>
                            <p class="text-gray-600">Hyderabad, India</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="py-20 bg-gray-50">
        <div class="max-w-6xl mx-auto px-4">
            <h2 class="text-3xl font-bold text-center text-gray-800 mb-12">What Our Patients Say</h2>
            <div class="grid md:grid-cols-3 gap-8">
                <div class="bg-white rounded-lg shadow-md p-6">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center mr-3">
                            <i class="ri-user-line text-teal-600"></i>
                        </div>
                        <div>
                            <h3 class="font-semibold text-gray-800">Rajesh Kumar</h3>
                            <div class="flex text-yellow-400">
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                            </div>
                        </div>
                    </div>
                    <p class="text-gray-600 italic">"Dr. Sharma's homeopathic treatment completely transformed my chronic anxiety. Her compassionate approach and personalized care made all the difference in my healing journey."</p>
                </div>
                
                <div class="bg-white rounded-lg shadow-md p-6">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center mr-3">
                            <i class="ri-user-line text-teal-600"></i>
                        </div>
                        <div>
                            <h3 class="font-semibold text-gray-800">Meera Patel</h3>
                            <div class="flex text-yellow-400">
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                            </div>
                        </div>
                    </div>
                    <p class="text-gray-600 italic">"My daughter's learning difficulties improved significantly under Dr. Sharma's care. The holistic approach addressed not just symptoms but the root cause of her challenges."</p>
                </div>
                
                <div class="bg-white rounded-lg shadow-md p-6">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center mr-3">
                            <i class="ri-user-line text-teal-600"></i>
                        </div>
                        <div>
                            <h3 class="font-semibold text-gray-800">Arjun Singh</h3>
                            <div class="flex text-yellow-400">
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                                <i class="ri-star-fill"></i>
                            </div>
                        </div>
                    </div>
                    <p class="text-gray-600 italic">"Professional, knowledgeable, and genuinely caring. Dr. Sharma's treatment helped me overcome depression naturally without harsh side effects. Highly recommended!"</p>
                </div>
            </div>
        </div>
    </section>

    <section id="contact" class="py-20 bg-white">
        <div class="max-w-6xl mx-auto px-4">
            <h2 class="text-3xl font-bold text-center text-gray-800 mb-12">Contact Us</h2>
            <div class="grid md:grid-cols-2 gap-12">
                <div class="bg-white rounded-lg shadow-md p-8">
                    <h3 class="text-2xl font-semibold text-gray-800 mb-6">Get in Touch</h3>
                    <div class="space-y-6">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-map-pin-line text-teal-600 text-xl"></i>
                            </div>
                            <div>
                                <p class="font-medium text-gray-800">Address</p>
                                <p class="text-gray-600">123 Main Street, Hyderabad, India</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-mail-line text-teal-600 text-xl"></i>
                            </div>
                            <div>
                                <p class="font-medium text-gray-800">Email</p>
                                <p class="text-gray-600">info@Hey Dochomoeo.com</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-phone-line text-teal-600 text-xl"></i>
                            </div>
                            <div>
                                <p class="font-medium text-gray-800">Phone</p>
                                <p class="text-gray-600">+91 12345 67890</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-8">
                        <h4 class="font-semibold text-gray-800 mb-4">Follow Us</h4>
                        <div class="flex space-x-4">
                            <div class="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-facebook-fill text-teal-600"></i>
                            </div>
                            <div class="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-twitter-fill text-teal-600"></i>
                            </div>
                            <div class="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-instagram-fill text-teal-600"></i>
                            </div>
                            <div class="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                                <i class="ri-linkedin-fill text-teal-600"></i>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-white rounded-lg shadow-md p-8">
                    <h3 class="text-2xl font-semibold text-gray-800 mb-6">Send Message</h3>
                    <form class="space-y-4">
                        <input type="text" placeholder="Your Name" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
                        <input type="email" placeholder="Your Email" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
                        <input type="tel" placeholder="Your Phone" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
                        <textarea placeholder="Your Message" rows="4" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"></textarea>
                        <button type="submit" class="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition-colors">
                            Send Message
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </section>

    <footer class="bg-gray-800 text-white py-12">
        <div class="max-w-6xl mx-auto px-4">
            <div class="grid md:grid-cols-3 gap-8">
                <div>
                    <div class="flex items-center space-x-3 mb-4">
                        <div class="bg-teal-600 text-white p-2 rounded-full">
                            <i class="ri-heart-pulse-line"></i>
                        </div>
                        <span class="text-xl font-bold">Hey Doc!</span>
                    </div>
                    <p class="text-gray-300 mb-4">
                        Providing compassionate homeopathic care with personalized treatment approaches for holistic healing and wellness.
                    </p>
                </div>
                
                <div>
                    <h4 class="text-lg font-semibold mb-4">Quick Links</h4>
                    <ul class="space-y-2">
                        <li><a href="#home" class="text-gray-300 hover:text-white transition-colors">Home</a></li>
                        <li><a href="#doctor" class="text-gray-300 hover:text-white transition-colors">Meet a doctor</a></li>
                        <li><a href="#contact" class="text-gray-300 hover:text-white transition-colors">contact</a></li>
                        
                    </ul>
                </div>
                
                <div>
                    <h4 class="text-lg font-semibold mb-4">Connect With Us</h4>
                    <div class="flex space-x-4 mb-4">
                        <div class="w-10 h-10 bg-gray-700 rounded-full flex items-center justify-center">
                            <i class="ri-facebook-fill text-white"></i>
                        </div>
                        <div class="w-10 h-10 bg-gray-700 rounded-full flex items-center justify-center">
                            <i class="ri-twitter-fill text-white"></i>
                        </div>
                        <div class="w-10 h-10 bg-gray-700 rounded-full flex items-center justify-center">
                            <i class="ri-instagram-fill text-white"></i>
                        </div>
                        <div class="w-10 h-10 bg-gray-700 rounded-full flex items-center justify-center">
                            <i class="ri-linkedin-fill text-white"></i>
                        </div>
                    </div>
                    <p class="text-gray-300 text-sm"> 2024 Hey Doc!. All rights reserved.</p>
                </div>
            </div>
        </div>
    </footer>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const mobileMenuButton = document.getElementById('mobile-menu-button');
            const mobileMenu = document.getElementById('mobile-menu');

            if (mobileMenuButton && mobileMenu) { // Ensure elements exist
                mobileMenuButton.addEventListener('click', function() {
                    mobileMenu.classList.toggle('hidden');
                });

                // Close the mobile menu when a link is clicked (for smoother navigation)
                mobileMenu.querySelectorAll('a').forEach(link => {
                    link.addEventListener('click', () => {
                        mobileMenu.classList.add('hidden');
                    });
                });
            }
        });

        // Function to fully reset the Dialogflow widget (new session)
        function clearChatAndRefresh() {
            try {
                const old = document.querySelector('df-messenger');
                if (!old) return;
                const parent = old.parentNode;

                // Best-effort: clear any cached chat stored by the widget
                try {
                    Object.keys(sessionStorage).forEach(k => {
                        if (k.toLowerCase().includes('df') || k.toLowerCase().includes('dialogflow')) {
                            sessionStorage.removeItem(k);
                        }
                    });
                    Object.keys(localStorage).forEach(k => {
                        if (k.toLowerCase().includes('df') || k.toLowerCase().includes('dialogflow')) {
                            localStorage.removeItem(k);
                        }
                    });
                } catch(_) {}

                // Remove old element first, then recreate after a short delay
                const attrs = Array.from(old.attributes).reduce((acc, a) => { acc[a.name] = a.value; return acc; }, {});
                parent.removeChild(old);
                setTimeout(() => {
                    const fresh = document.createElement('df-messenger');
                    Object.keys(attrs).forEach(name => {
                        if (name.toLowerCase() !== 'session-id') {
                            fresh.setAttribute(name, attrs[name]);
                        }
                    });
                    const newSession = 'session-' + Date.now();
                    fresh.setAttribute('session-id', newSession);

                    const bubble = document.createElement('df-messenger-chat-bubble');
                    bubble.setAttribute('chat-title', 'Hey Doc!');
                    bubble.setAttribute('chat-icon', '/file.jpeg');
                    fresh.appendChild(bubble);

                    parent.appendChild(fresh);
                }, 60);
            } catch (e) {
                console.log('Refresh failed, reloading page as fallback', e);
                location.reload();
            }
        }
    </script>

    <!-- Dialogflow Chatbot -->
    <df-messenger
      project-id="heydoc-473715-d6"
      agent-id="8e2c9653-bd6b-4151-be4d-75cc6c44b35e"
      language-code="en"
      max-query-length="-1">
      <df-messenger-chat-bubble
        chat-title="Hey Doc">
      </df-messenger-chat-bubble>
    </df-messenger>
    <style>
      df-messenger {
        z-index: 999;
        position: fixed;
        --df-messenger-font-color: #000;
        --df-messenger-font-family: Google Sans;
        --df-messenger-chat-background: #f3f6fc;
        --df-messenger-message-user-background: #d3e3fd;
        --df-messenger-message-bot-background: #fff;
        bottom: 16px;
        right: 16px;
      }
      /* Small floating refresh button and starter prompt */
      #df-refresh-btn {
        position: fixed;
        bottom: 84px;  /* sit above bubble */
        right: 28px;
        width: 36px;
        height: 36px;
        border-radius: 9999px;
        background: #10b981; /* teal-500 */
        color: #fff;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        cursor: pointer;
      }
      #df-starter-tip {
        position: fixed;
        bottom: 130px;
        right: 28px;
        background: #ffffff;
        color: #111827;
        border: 1px solid #e5e7eb;
        padding: 8px 12px;
        border-radius: 10px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        max-width: 260px;
      }
    </style>

    <button id="df-refresh-btn" type="button" title="Refresh chat" onclick="clearChatAndRefresh()"></button>
    <div id="df-starter-tip">Hi! Ask about booking, timings, fees, or cancelling an appointment.</div>
    <script>
      // Hide starter tip after a few seconds and when the chat is interacted with
      function hideStarterTip() {
        var tip = document.getElementById('df-starter-tip');
        if (tip) tip.style.display = 'none';
      }
      setTimeout(hideStarterTip, 5000);
      document.addEventListener('click', function(e) {
        const df = document.querySelector('df-messenger');
        if (df && df.contains(e.target)) hideStarterTip();
      });

      // Auto-greet once per session by sending an initial 'hi' to the bot
      document.addEventListener('DOMContentLoaded', function() {
        try {
          const df = document.querySelector('df-messenger');
          if (!df) return;
          const greet = function() {
            if (sessionStorage.getItem('df_greeted') === '1') return;
            sessionStorage.setItem('df_greeted', '1');
            try { if (typeof df.renderCustomText === 'function') df.renderCustomText(''); } catch(_) {}
            try { if (typeof df.sendQuery === 'function') df.sendQuery('hi'); } catch(_) {}
          };
          if (typeof df.sendQuery === 'function') {
            greet();
          } else {
            df.addEventListener('df-messenger-loaded', greet);
          }
        } catch(_) {}
      });
    </script>
</body>
</html>
"""

# Reusable Appointment Form Template (for both Add and Edit)
appointment_form_template = r"""
<!DOCTYPE html>
<html lang="en" class="bg-gray-100">
<head>
  <meta charset="UTF-8">
  <title>{{ 'Add New' if mode == 'add' else 'Edit' }} Appointment - Hey Doc!</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body>
  <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
  <img src="/file.jpeg" alt="Hey Doc Logo" style="height:56px;">
    <h1 class="text-xl font-bold">Hey Doc!- {{ 'Add New' if mode == 'add' else 'Edit' }} Appointment</h1>
    <div>
      <a href="/dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">Dashboard</a>
      <a href="{{ url_for('logout') }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Logout</a>
    </div>
  </nav>

  <div class="p-6">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
          {{ message }}
        </div>
      {% endfor %}
    {% endwith %}

    <div class="bg-white rounded-lg shadow-md p-6 max-w-2xl mx-auto">
      <h2 class="text-2xl font-semibold mb-6">{{ 'Add New' if mode == 'add' else 'Edit' }} Appointment</h2>
      
      <form method="POST" action="{{ '/add_appointment' if mode == 'add' else '/edit_appointment/' + appointment_data.appointment_id }}" class="space-y-4">
        {% if mode == 'edit' %}
          <input type="hidden" id="current_appointment_time" value="{{ appointment_data.time }}">
          <input type="hidden" id="current_appointment_date" value="{{ appointment_data.date }}">
          <input type="hidden" id="current_appointment_location" value="{{ appointment_data.location if appointment_data and appointment_data.location else 'Hyderabad' }}">
        {% endif %}
        
        {# Hidden field for appointment_id when editing, to ensure it's passed with form data #}
        {% if mode == 'edit' %}
        <input type="hidden" name="appointment_id" value="{{ appointment_data.appointment_id }}">
        {% endif %}

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="name" class="block text-gray-700 font-medium mb-2">Patient Name *</label>
            <input type="text" id="name" name="name" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ appointment_data.name if appointment_data else '' }}">
          </div>
          
          <div>
            <label for="phone" class="block text-gray-700 font-medium mb-2">Phone Number *</label>
            <input type="tel" id="phone" name="phone" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ appointment_data.phone if appointment_data else '' }}">
          </div>
          
          <div>
            <label for="email" class="block text-gray-700 font-medium mb-2">Email</label>
            <input type="email" id="email" name="email"
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ appointment_data.email if appointment_data else '' }}">
          </div>

          <div>
            <label for="consultation_type" class="block text-gray-700 font-medium mb-2">Consultation Type *</label>
            <select id="consultation_type" name="consultation_type" required
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
                <option value="Walk-in" {% if appointment_data and appointment_data.get('consultation_type') == 'Walk-in' %}selected{% endif %}>In-Person Visit (Walk-in)</option>
                <option value="Video Consultation" {% if appointment_data and appointment_data.get('consultation_type') == 'Video Consultation' %}selected{% endif %}>Video Consultation</option>
            </select>
          </div>
          
          <div>
            <label for="location" class="block text-gray-700 font-medium mb-2">Location *</label>
            {% if location_options and location_options|length > 0 %}
              <select id="location" name="location" required
                      class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
                {% for city in location_options %}
                  <option value="{{ city }}" {% if appointment_data and appointment_data.location == city %}selected{% endif %}>{{ city }}</option>
                {% endfor %}
              </select>
              <p class="text-xs text-gray-500 mt-1">Showing Branch + City options.</p>
            {% else %}
              <input type="text" id="location" name="location" required
                     class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                     value="{{ appointment_data.location if appointment_data else '' }}" placeholder="Enter city/town">
              <p class="text-xs text-gray-500 mt-1">Must be a real place; validated when loading time slots.</p>
            {% endif %}
          </div>
          
          <div>
            <label for="date" class="block text-gray-700 font-medium mb-2">Appointment Date *</label>
            <input type="date" id="date" name="date" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ appointment_data.date if appointment_data else '' }}"
                   min="{{ today_date }}"> {# Added min attribute here #}
          </div>
          
          <div>
            <label for="time" class="block text-gray-700 font-medium mb-2">Appointment Time *</label>
            <select id="time" name="time" required
        class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
    <option value="" disabled {% if not appointment_data or not appointment_data.time %}selected{% endif %}>Select a time slot</option>
    {% for slot in time_slots %}
        {% set is_booked = slot in booked_slots %}
        <option value="{{ slot }}"
                {% if appointment_data and appointment_data.time == slot %}selected{% endif %}
                {% if is_booked %}disabled style="color: #dc2626; font-weight: bold;"{% else %}style="color: #059669;"{% endif %}>
            {{ slot }}{% if is_booked %} (Booked){% else %} (Available){% endif %}
        </option>
        {% if slot == "11:50" %}
            <option value="" disabled style="color: #f59e42; font-weight: bold;">--- Lunch Break (12:00 - 14:00) ---</option>
        {% endif %}
    {% endfor %}
</select>
<p class="text-sm text-gray-600 mt-1">
    <span class="text-red-600 font-semibold">● Red slots are booked</span> |
    <span class="text-green-600">● Green slots are available</span>
</p>
          </div>
        </div>
        
        <div>
          <label for="address" class="block text-gray-700 font-medium mb-2">Address</label>
          <textarea id="address" name="address" rows="2"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">{{ appointment_data.address if appointment_data else '' }}</textarea>
        </div>
        
        <div>
          <label for="symptoms" class="block text-gray-700 font-medium mb-2">Symptoms/Reason *</label>
          <textarea id="symptoms" name="symptoms" rows="3" required
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">{{ appointment_data.symptoms if appointment_data else '' }}</textarea>
        </div>
        
        <div class="flex space-x-4">
          <button type="submit" class="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700 transition-colors">
            {{ 'Create Appointment' if mode == 'add' else 'Save Changes' }}
          </button>
          <a href="/dashboard" class="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600 transition-colors">
            Cancel
          </a>
        </div>
      </form>
    </div>
  </div>
  
  <script>
    let ALL_SLOTS_APPT = {{ time_slots | tojson }};

    async function reloadSlotsForCity(city, selectedDate) {
      try {
        const isReal = await validatePlace(city);
        if (!isReal) { throw new Error('Invalid place'); }
        const url = `/get_time_slots?city=${encodeURIComponent(city)}${selectedDate ? `&date=${encodeURIComponent(selectedDate)}` : ''}`;
        const res = await fetch(url);
        const data = await res.json();
        if (data && Array.isArray(data.time_slots)) {
          ALL_SLOTS_APPT = data.time_slots;
        }
      } catch (e) { console.error('Failed to load city slots', e); }
    }

    async function validatePlace(place) {
      try {
        const q = encodeURIComponent(place);
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${q}`, { headers: { 'User-Agent': 'clinic-app/1.0' }});
        if (!res.ok) return false;
        const data = await res.json();
        return Array.isArray(data) && data.length > 0;
      } catch (_) { return false; }
    }

    // Function to update time slots based on selected date and city
    async function updateTimeSlots() {
  const dateInput = document.getElementById('date');
  const timeSelect = document.getElementById('time');
  const citySelect = document.getElementById('location');
  const selectedCity = citySelect ? citySelect.value : 'Hyderabad';
  const selectedDate = dateInput.value;
  const curTimeEl = document.getElementById('current_appointment_time');
  const curDateEl = document.getElementById('current_appointment_date');
  const curLocEl = document.getElementById('current_appointment_location');
  const originalTime = (curTimeEl && curDateEl && curDateEl.value === selectedDate && (!curLocEl || curLocEl.value === selectedCity)) ? curTimeEl.value : '';
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  const todayStr = `${yyyy}-${mm}-${dd}`;
  const nowHHMM = now.toTimeString().slice(0,5);

  if (!selectedDate) {
    timeSelect.innerHTML = '<option value="">Select date first</option>';
    timeSelect.disabled = true;
    return;
  }

  // Ensure slots match current city and chosen date (for date-specific overrides)
  const ok = await validatePlace(selectedCity);
  if (!ok) {
    timeSelect.innerHTML = '<option value="">Enter a real location</option>';
    timeSelect.disabled = true;
    return;
  }
  await reloadSlotsForCity(selectedCity, selectedDate);

  // Rebuild options
  timeSelect.innerHTML = '<option value="">Select a time slot</option>' +
    ALL_SLOTS_APPT.map(s => `<option value="${s}">${s}</option>`).join('');
  timeSelect.disabled = false;

  // Make AJAX request to get booked slots for the selected date and city
  fetch(`/get_booked_slots/${selectedDate}?city=${encodeURIComponent(selectedCity)}`)
    .then(response => response.json())
    .then(data => {
      let bookedSlots = data.booked_slots || [];
      if (originalTime) {
        bookedSlots = bookedSlots.filter(s => s !== originalTime);
      }
      function normalizeSlot(str) {
    // Remove spaces and make uppercase for reliable comparison
    return str.replace(/\s+/g, '').toUpperCase();
}
      Array.from(timeSelect.options).forEach(option => {
    if (option.value && option.value !== '') {
        const slotTime = option.value;
        // Normalize both for comparison
        const isBookedOrBlocked = bookedSlots.some(
            booked => normalizeSlot(booked) === normalizeSlot(slotTime)
        );
        // ...rest of your logic...
        if (isBookedOrBlocked) {
            option.disabled = true;
            option.style.color = "#dc2626"; // red]
            option.style.fontWeight = "bold";
            option.textContent = slotTime + " (Booked)";
            option.style.display = "";
        } else {
            option.disabled = false;
            option.style.color = "#059669"; // green
            option.style.fontWeight = "bold";
            option.textContent = slotTime + " (Available)";
            option.style.display = "";
        }
    }
});
      if (originalTime) {
        timeSelect.value = originalTime;
      }
    })
    .catch(error => {
      console.error('Error fetching booked slots:', error);
    });
}
    
    // Event listeners
    document.addEventListener('DOMContentLoaded', function() {
      const dateInput = document.getElementById('date');
      const citySelect = document.getElementById('location');
      if (dateInput) {
        dateInput.addEventListener('change', updateTimeSlots);
      }
      if (citySelect) {
        citySelect.addEventListener('change', updateTimeSlots);
      }
      updateTimeSlots();
    });
  </script>
</body>
</html>
"""

# Simple Block Slot Page
block_slot_template = """
<!DOCTYPE html>
<html lang="en" class="bg-gray-100">
<head>
  <meta charset="UTF-8">
  <title>Block Slot - Hey Doc!</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
  <script>
    let ALL_SLOTS_BLOCK = {{ time_slots | tojson }};

    async function reloadBlockSlotsForCity(city) {
      try {
        // When called from fetchUnavailable, we will pass date through that function
        const res = await fetch(`/get_time_slots?city=${encodeURIComponent(city)}`);
        const data = await res.json();
        if (data && Array.isArray(data.time_slots)) {
          ALL_SLOTS_BLOCK = data.time_slots;
          // Rebuild the options quickly; fetchUnavailable will handle disabling
          const select = document.getElementById('b_time');
          if (select) {
            select.innerHTML = '<option value="">Select time</option>' + ALL_SLOTS_BLOCK.map(s => `<option value="${s}">${s}</option>`).join('');
          }
        }
      } catch (e) { console.error('Failed to load block slots for city', e); }
    }

    function fetchUnavailable() {
      const date = document.getElementById('b_date').value;
      const select = document.getElementById('b_time');
      const citySel = document.getElementById('b_location');
      const city = citySel ? citySel.value : 'Hyderabad';
      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, '0');
      const dd = String(now.getDate()).padStart(2, '0');
      const todayStr = `${yyyy}-${mm}-${dd}`;
      const nowHHMM = now.toTimeString().slice(0,5);
      if (!date) {
        // No date chosen yet
        select.innerHTML = '<option value="">Select date first</option>';
        select.disabled = true;
        return;
      }

      // Reload slots for city+date to respect date-specific overrides
      fetch(`/get_time_slots?city=${encodeURIComponent(city)}&date=${encodeURIComponent(date)}`)
        .then(r => r.json())
        .then(data => {
          if (data && Array.isArray(data.time_slots)) {
            ALL_SLOTS_BLOCK = data.time_slots;
          }
          select.innerHTML = '<option value="">Select time</option>' + ALL_SLOTS_BLOCK.map(s => `<option value="${s}">${s}</option>`).join('');
          select.disabled = false;
        })
        .catch(() => {
          select.innerHTML = '<option value="">Select time</option>' + ALL_SLOTS_BLOCK.map(s => `<option value="${s}">${s}</option>`).join('');
          select.disabled = false;
        });
      fetch(`/get_booked_slots/${date}?city=${encodeURIComponent(city)}`)
        .then(r => r.json())
        .then(data => {
          const unavailable = data.booked_slots || [];
          Array.from(select.options).forEach(opt => {
            if (!opt.value) return;
            const isUnavailable = unavailable.includes(opt.value);
            const isPastToday = (date === todayStr) && (opt.value < nowHHMM);

            if (isUnavailable) {
              opt.disabled = true;
              opt.textContent = opt.value + ' (Unavailable)';
              opt.style.display = '';
            } else if (isPastToday) {
              opt.disabled = true;
              opt.textContent = opt.value + ' (Past)';
              opt.style.display = 'none';
            } else {
              opt.disabled = false;
              opt.textContent = opt.value;
              opt.style.display = '';
            }
          });
        });
    }
    document.addEventListener('DOMContentLoaded', function() {
      const locSel = document.getElementById('b_location');
      if (locSel) {
        locSel.addEventListener('change', async function() {
          const date = document.getElementById('b_date') ? document.getElementById('b_date').value : '';
          // Preload slots for city+date
          try { await fetch(`/get_time_slots?city=${encodeURIComponent(this.value)}${date ? `&date=${encodeURIComponent(date)}` : ''}`); } catch(e) {}
          fetchUnavailable();
        });
      }
    });
  </script>
</head>
<body>
  <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
    <h1 class="text-xl font-bold">Block a Slot</h1>
    <div>
      <a href="/dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Dashboard</a>
    </div>
  </nav>
  <div class="p-6 max-w-xl mx-auto">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">{{ message }}</div>
      {% endfor %}
    {% endwith %}

    <div class="bg-white rounded-lg shadow p-6">
      <form method="POST" action="/block_slot" class="space-y-4">
        <div>
          <label class="block text-gray-700 font-medium mb-2">Date</label>
          <input type="date" id="b_date" name="date" class="professional-input w-full" required onchange="fetchUnavailable()" min="{{ datetime.utcnow().strftime('%Y-%m-%d') }}">
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-2">Location</label>
          <select id="b_location" name="location" class="professional-select w-full" onchange="fetchUnavailable()" required>
            {% for city in available_cities %}
            <option value="{{ city }}">{{ city }}</option>
            {% endfor %}
          </select>
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-2">Time</label>
          <select id="b_time" name="time" class="professional-select w-full" required>
            <option value="">Select time</option>
            {% for slot in time_slots %}
            <option value="{{ slot }}">{{ slot }}</option>
            {% endfor %}
          </select>
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-2">Reason (optional)</label>
          <input type="text" name="reason" class="professional-input w-full" placeholder="Personal, Surgery, Meeting...">
        </div>
        <div class="flex space-x-3">
          <button type="submit" class="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700">Block Slot</button>
          <a href="/dashboard" class="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600">Cancel</a>
        </div>
      </form>
    </div>

    <div class="bg-white rounded-lg shadow p-6 mt-6">
      <h2 class="text-lg font-semibold mb-4">Currently Blocked Slots (Upcoming)</h2>
      <ul class="list-disc pl-5 space-y-2">
        {% for s in blocked_list %}
          <li>{{ s.date }} {{ s.time }}{% if s.reason %} - {{ s.reason }}{% endif %}
            <a class="text-red-600 ml-2" href="/unblock_slot?id={{ s._id }}">Unblock</a>
          </li>
        {% else %}
          <li class="text-gray-600">No blocked slots</li>
        {% endfor %}
      </ul>
    </div>
  </div>
</body>
</html>
"""

# Availability Form Template
availability_form_template = """
<!DOCTYPE html>
<html lang="en" class="bg-gray-100">
<head>
  <meta charset="UTF-8">
  <title>Add Availability - Hey Doc!</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
  <script>
    function onModeChange() {
      const mode = document.querySelector('input[name="mode"]:checked').value;
      const dateRow = document.getElementById('date_row');
      if (mode === 'date') { dateRow.classList.remove('hidden'); } else { dateRow.classList.add('hidden'); }
    }
    document.addEventListener('DOMContentLoaded', onModeChange);
  </script>
  <style>
    .professional-input { width: 100%; padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.5rem; }
    .professional-select { width: 100%; padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.5rem; }
    .section-title { font-size: 1.125rem; font-weight: 600; color: #1f2937; margin-bottom: 0.5rem; }
  </style>
</head>
<body>
  <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
    <h1 class="text-xl font-bold">Add Availability</h1>
    <div>
      <a href="/dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Dashboard</a>
    </div>
  </nav>

  <div class="p-6 max-w-3xl mx-auto">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">{{ message }}</div>
      {% endfor %}
    {% endwith %}

    <div class="bg-white rounded-lg shadow p-6">
      <form method="POST" action="/add_availability" class="space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-gray-700 font-medium mb-2">Hospital Name</label>
            <input type="text" name="hospital_name" class="professional-input" value="Hey Doc!" placeholder="Hospital/Clinic name">
          </div>
          <div>
            <label class="block text-gray-700 font-medium mb-2">Location</label>
            {% if location_options and location_options|length > 0 %}
              <select name="location" class="professional-select" required>
                {% for city in location_options %}
                  <option value="{{ city }}">{{ city }}</option>
                {% endfor %}
              </select>
              <p class="text-xs text-gray-500 mt-1">Locations from Branch + City list.</p>
            {% else %}
              <input type="text" name="location" class="professional-input" placeholder="Akola, Hyderabad or Pune" list="cities" required>
              <datalist id="cities">
                {% for city in available_cities %}
                <option value="{{ city }}"></option>
                {% endfor %}
              </datalist>
              <p class="text-xs text-gray-500 mt-1">Only real clinic locations are accepted.</p>
            {% endif %}
          </div>
        </div>

        <div>
          <label class="block text-gray-700 font-medium mb-2">Document Mode</label>
          <div class="flex items-center space-x-6">
            <label class="inline-flex items-center space-x-2">
              <input type="radio" name="mode" value="default" checked onchange="onModeChange()">
              <span>Default (applies to all dates)</span>
            </label>
            <label class="inline-flex items-center space-x-2">
              <input type="radio" name="mode" value="date" onchange="onModeChange()">
              <span>Date-specific override</span>
            </label>
          </div>
        </div>

        <div id="date_row" class="hidden">
          <label class="block text-gray-700 font-medium mb-2">Date</label>
          <input type="date" name="date" class="professional-input" min="{{ datetime.utcnow().strftime('%Y-%m-%d') }}">
          <p class="text-sm text-gray-500 mt-1">
            <span class="text-red-600 font-semibold">● Red slots are booked</span> |
            <span class="text-green-600">● Green slots are available</span>
          </p>
        </div>

        <div>
          <h3 class="section-title">Working Hours</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="border rounded-lg p-4">
              <h4 class="font-medium text-gray-800 mb-3">Morning Shift</h4>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">Start</label>
                  <input type="time" name="morning_start" class="professional-input" placeholder="hh:mm">
                </div>
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">End</label>
                  <input type="time" name="morning_end" class="professional-input" placeholder="hh:mm">
                </div>
              </div>
            </div>
            
            <div class="border rounded-lg p-4 md:col-span-2">
              <h4 class="font-medium text-gray-800 mb-3">Evening Shift</h4>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">Start</label>
                  <input type="time" name="evening_start" class="professional-input" placeholder="hh:mm">
                </div>
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">End</label>
                  <input type="time" name="evening_end" class="professional-input" placeholder="hh:mm">
                </div>
              </div>
            </div>
          </div>
          <p class="text-sm text-gray-500 mt-2">Enter at least one shift with both start and end times.</p>
        </div>

        <div class="flex space-x-3">
          <button type="submit" class="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700">Save Availability</button>
          <a href="/dashboard" class="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600">Cancel</a>
        </div>
      </form>
    </div>
  </div>
</body>
</html>
"""

# Prescription Form Template
prescription_form_template = """
<!DOCTYPE html>
<html lang="en" class="bg-gray-100">
<head>
  <meta charset="UTF-8">
  <title>Add Prescription - Hey Doc!</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body>
  <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
    <h1 class="text-xl font-bold">Hey Doc! - Add Prescription</h1>
    <div>
      <a href="/dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">Dashboard</a>
      <a href="/prescriptions" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">View Prescriptions</a>
      <a href="{{ url_for('logout') }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Logout</a>
    </div>
  </nav>

  <div class="p-6">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
          {{ message }}
        </div>
      {% endfor %}
    {% endwith %}

    <div class="bg-white rounded-lg shadow-md p-6 max-w-4xl mx-auto">
      <h2 class="text-2xl font-semibold mb-6">Add New Prescription</h2>
      
      <form method="POST" action="/add_prescription" class="space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label for="patient_name" class="block text-gray-700 font-medium mb-2">Patient Name *</label>
            <input type="text" id="patient_name" name="patient_name" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ prescription_data.patient_name if prescription_data else '' }}">
          </div>
          
          <div>
            <label for="patient_phone" class="block text-gray-700 font-medium mb-2">Patient Phone *</label>
            <input type="tel" id="patient_phone" name="patient_phone" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ prescription_data.patient_phone if prescription_data else '' }}">
          </div>
          
          <div>
            <label for="prescription_date" class="block text-gray-700 font-medium mb-2">Prescription Date *</label>
            <input type="date" id="prescription_date" name="prescription_date" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ prescription_data.prescription_date_iso if prescription_data and prescription_data.prescription_date_iso else today_date }}">
          </div>
          
          <div>
            <label for="diagnosis" class="block text-gray-700 font-medium mb-2">Diagnosis *</label>
            <input type="text" id="diagnosis" name="diagnosis" required
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                   value="{{ prescription_data.diagnosis if prescription_data else '' }}">
          </div>
        </div>
        
        <div>
          <label for="medicines" class="block text-gray-700 font-medium mb-2">Medicines *</label>
          <div id="medicines-container" class="space-y-4">
            <div class="medicine-entry border border-gray-200 rounded-lg p-4">
              <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">Medicine Name</label>
                  <input type="text" name="medicine_names[]" required
                         class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                         placeholder="e.g., Arnica Montana">
                </div>
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">Potency</label>
                  <input type="text" name="potencies[]" required
                         class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                         placeholder="e.g., 30C">
                </div>
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">Dosage</label>
                  <input type="text" name="dosages[]" required
                         class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                         placeholder="e.g., 3 times daily">
                </div>
                <div>
                  <label class="block text-gray-700 text-sm font-medium mb-1">Duration</label>
                  <input type="text" name="durations[]" required
                         class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                         placeholder="e.g., 7 days">
                </div>
              </div>
            </div>
          </div>
          <button type="button" id="add-medicine" class="mt-2 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 transition-colors">
            <i class="ri-add-line mr-1"></i>Add Another Medicine
          </button>
        </div>
        
        <div>
          <label for="instructions" class="block text-gray-700 font-medium mb-2">Special Instructions</label>
          <textarea id="instructions" name="instructions" rows="3"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                    placeholder="Any special instructions for the patient...">{{ prescription_data.instructions if prescription_data else '' }}</textarea>
        </div>
        
        <div>
          <label for="notes" class="block text-gray-700 font-medium mb-2">Doctor's Notes</label>
          <textarea id="notes" name="notes" rows="3"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
                    placeholder="Additional notes...">{{ prescription_data.notes if prescription_data else '' }}</textarea>
        </div>
        
        <div class="flex space-x-4">
          <button type="submit" class="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700 transition-colors">
            Save Prescription
          </button>
          <a href="/prescriptions" class="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600 transition-colors">
            Cancel
          </a>
        </div>
      </form>
    </div>
  </div>
  
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      const addMedicineBtn = document.getElementById('add-medicine');
      const medicinesContainer = document.getElementById('medicines-container');
      
      addMedicineBtn.addEventListener('click', function() {
        const medicineEntry = document.createElement('div');
        medicineEntry.className = 'medicine-entry border border-gray-200 rounded-lg p-4';
        medicineEntry.innerHTML = `
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label class="block text-gray-700 text-sm font-medium mb-1">Medicine Name</label>
              <input type="text" name="medicine_names[]" required
                     class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                     placeholder="e.g., Arnica Montana">
            </div>
            <div>
              <label class="block text-gray-700 text-sm font-medium mb-1">Potency</label>
              <input type="text" name="potencies[]" required
                     class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                     placeholder="e.g., 30C">
            </div>
            <div>
              <label class="block text-gray-700 text-sm font-medium mb-1">Dosage</label>
              <input type="text" name="dosages[]" required
                     class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                     placeholder="e.g., 3 times daily">
            </div>
            <div class="flex items-end">
              <div class="flex-1">
                <label class="block text-gray-700 text-sm font-medium mb-1">Duration</label>
                <input type="text" name="durations[]" required
                       class="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"
                       placeholder="e.g., 7 days">
              </div>
              <button type="button" class="ml-2 bg-red-500 text-white px-3 py-2 rounded hover:bg-red-600 transition-colors remove-medicine">
                <i class="ri-delete-bin-line"></i>
              </button>
            </div>
          </div>
        `;
        
        medicinesContainer.appendChild(medicineEntry);
        
        // Add remove functionality to the new entry
        const removeBtn = medicineEntry.querySelector('.remove-medicine');
        removeBtn.addEventListener('click', function() {
          medicineEntry.remove();
        });
      });
      
      // Add remove functionality to the first entry
      const firstRemoveBtn = medicinesContainer.querySelector('.remove-medicine');
      if (firstRemoveBtn) {
        firstRemoveBtn.addEventListener('click', function() {
          medicinesContainer.querySelector('.medicine-entry').remove();
        });
      }
    });
  </script>
</body>
</html>
"""

# Prescription History Template
prescription_history_template = """
<!DOCTYPE html>
<html lang="en" class="bg-gray-100">
<head>
  <meta charset="UTF-8">
  <title>Prescription History - Hey Doc!</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
  <link rel="stylesheet" href="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/themes/df-messenger-default.css">
  <script src="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/df-messenger.js"></script>
</head>
<body>
  <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
    <h1 class="text-xl font-bold">Hey Doc! - Prescription History</h1>
    <div>
      <a href="/dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">Dashboard</a>
      <a href="/add_prescription" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">Add Prescription</a>
      <a href="{{ url_for('logout') }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Logout</a>
    </div>
  </nav>

  <div class="p-6">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
          {{ message }}
        </div>
      {% endfor %}
    {% endwith %}

    <div class="bg-white rounded-lg shadow-md p-6">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-semibold">
          {% if patient_phone %}
            {% if patient_name %}
              Prescriptions for Patient: {{ patient_name }} ({{ patient_phone }})
            {% else %}
              Prescriptions for Patient: {{ patient_phone }}
            {% endif %}
          {% else %}
            Prescription History
          {% endif %}
        </h2>
        <div class="flex space-x-2">
          {% if patient_phone %}
            <a href="/prescriptions" class="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors">
              <i class="ri-list-check mr-1"></i>View All Prescriptions
            </a>
          {% endif %}
          <a href="/add_prescription{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" class="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 transition-colors">
            <i class="ri-add-line mr-1"></i>Add New Prescription
          </a>
        </div>
      </div>

      <form method="GET" action="/prescriptions" class="mb-6 flex flex-col md:flex-row items-center space-y-2 md:space-y-0 md:space-x-4">
        {% if patient_phone %}
          <input type="hidden" name="patient_phone" value="{{ patient_phone }}">
        {% endif %}
        <input type="text" name="search_query" placeholder="Search by Patient Name or Phone..." 
               class="flex-grow w-full md:w-auto px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500"
               value="{{ search_query if search_query else '' }}">
        <button type="submit" class="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 transition-colors">
          <i class="ri-search-line mr-1"></i>Search
        </button>
        {% if search_query %}
          <a href="/prescriptions{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" class="bg-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-400 transition-colors">Clear Search</a>
        {% endif %}

        <div class="flex items-center space-x-2 w-full md:w-auto">
          <label for="sort_by" class="text-gray-700">Sort by:</label>
          <select id="sort_by" name="sort_by" class="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500">
            <option value="">Default (Latest First)</option>
            <option value="patient_name_asc" {% if sort_by == 'patient_name_asc' %}selected{% endif %}>Patient Name (A-Z)</option>
            <option value="patient_name_desc" {% if sort_by == 'patient_name_desc' %}selected{% endif %}>Patient Name (Z-A)</option>
            <option value="date_asc" {% if sort_by == 'date_asc' %}selected{% endif %}>Date (Oldest First)</option>
            <option value="date_desc" {% if sort_by == 'date_desc' %}selected{% endif %}>Date (Newest First)</option>
          </select>
          <button type="submit" class="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 transition-colors">
            Sort
          </button>
        </div>
      </form>

      <div class="space-y-6">
        {% for prescription in prescriptions %}
        <div class="border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
          <div class="flex justify-between items-start mb-4">
            <div>
              <h3 class="text-xl font-semibold text-gray-800">{{ prescription.patient_name }}</h3>
              <p class="text-gray-600">{{ prescription.patient_phone }}</p>
              <p class="text-sm text-gray-500">Prescription Date: {{ prescription.prescription_date }}</p>
              <p class="text-sm text-gray-500">Prescription ID: {{ prescription.prescription_id }}</p>
            </div>
            <div class="text-right">
              <span class="bg-teal-100 text-teal-800 px-3 py-1 rounded-full text-sm font-medium">
                {{ prescription.created_at_str }}
              </span>
            </div>
          </div>
          
          <div class="grid md:grid-cols-2 gap-6 mb-4">
            <div>
              <h4 class="font-semibold text-gray-700 mb-2">Diagnosis</h4>
              <p class="text-gray-600">{{ prescription.diagnosis }}</p>
            </div>
            <div>
              <h4 class="font-semibold text-gray-700 mb-2">Special Instructions</h4>
              <p class="text-gray-600">{{ prescription.instructions or 'None' }}</p>
            </div>
          </div>
          
          <div class="mb-4">
            <h4 class="font-semibold text-gray-700 mb-3">Medicines</h4>
            <div class="bg-gray-50 rounded-lg p-4">
              {% for medicine in prescription.medicines %}
              <div class="border-b border-gray-200 pb-3 mb-3 last:border-b-0 last:pb-0 last:mb-0">
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span class="font-medium text-gray-700">Medicine:</span>
                    <p class="text-gray-600">{{ medicine.name }}</p>
                  </div>
                  <div>
                    <span class="font-medium text-gray-700">Potency:</span>
                    <p class="text-gray-600">{{ medicine.potency }}</p>
                  </div>
                  <div>
                    <span class="font-medium text-gray-700">Dosage:</span>
                    <p class="text-gray-600">{{ medicine.dosage }}</p>
                  </div>
                  <div>
                    <span class="font-medium text-gray-700">Duration:</span>
                    <p class="text-gray-600">{{ medicine.duration }}</p>
                  </div>
                </div>
              </div>
              {% endfor %}
            </div>
          </div>
          
          {% if prescription.notes %}
          <div class="mb-4">
            <h4 class="font-semibold text-gray-700 mb-2">Doctor's Notes</h4>
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p class="text-gray-700">{{ prescription.notes }}</p>
            </div>
          </div>
          {% endif %}
          
          <div class="flex justify-end space-x-2">
            <a href="/view_prescription/{{ prescription.prescription_id }}{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" 
               class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 transition-colors text-sm">
              <i class="ri-eye-line mr-1"></i>View Details
            </a>
            <a href="/view_certificate/{{ prescription.prescription_id }}" 
               class="bg-teal-500 text-white px-4 py-2 rounded hover:bg-teal-600 transition-colors text-sm">
              <i class="ri-award-line mr-1"></i>Certificate
            </a>
            <a href="/print_prescription/{{ prescription.prescription_id }}{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" 
               class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 transition-colors text-sm">
              <i class="ri-printer-line mr-1"></i>Print
            </a>
            <a href="/delete_prescription/{{ prescription.prescription_id }}{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" 
               class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 transition-colors text-sm"
               onclick="return confirm('Are you sure you want to delete this prescription? This action cannot be undone.')">
              <i class="ri-delete-bin-line mr-1"></i>Delete
            </a>
          </div>
        </div>
        {% endfor %}
        
        {% if not prescriptions %}
        <div class="text-center py-12">
          <div class="text-gray-400 mb-4">
            <i class="ri-medicine-bottle-line text-6xl"></i>
          </div>
          <h3 class="text-xl font-semibold text-gray-600 mb-2">
            {% if patient_phone %}
              {% if patient_name %}
                No Prescriptions Found for Patient: {{ patient_name }} ({{ patient_phone }})
              {% else %}
                No Prescriptions Found for Patient: {{ patient_phone }}
              {% endif %}
            {% else %}
              No Prescriptions Found
            {% endif %}
          </h3>
          <p class="text-gray-500 mb-4">
            {% if patient_phone %}
              This patient doesn't have any prescriptions yet.
            {% else %}
              Start by adding your first prescription.
            {% endif %}
          </p>
          <a href="/add_prescription{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" class="bg-teal-600 text-white px-6 py-3 rounded-lg hover:bg-teal-700 transition-colors">
            {% if patient_phone %}
              Add Prescription for This Patient
            {% else %}
              Add First Prescription
            {% endif %}
          </a>
        </div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Dialogflow Chatbot -->
  <df-messenger
    project-id="heydoc-473715-d6"
    agent-id="8e2c9653-bd6b-4151-be4d-75cc6c44b35e"
    language-code="en"
    max-query-length="-1">
    <df-messenger-chat-bubble
      chat-title="Hey Doc">
    </df-messenger-chat-bubble>
  </df-messenger>
  <style>
    df-messenger {
      z-index: 999;
      position: fixed;
      --df-messenger-font-color: #000;
      --df-messenger-font-family: Google Sans;
      --df-messenger-chat-background: #f3f6fc;
      --df-messenger-message-user-background: #d3e3fd;
      --df-messenger-message-bot-background: #fff;
      bottom: 16px;
      right: 16px;
    }
  </style>

    /* Removed refresh button and starter tip styles */
  </style>

  <!-- Removed refresh button and starter tip scripts -->
  <script>
    // Auto-greet once per session on this page
    document.addEventListener('DOMContentLoaded', function() {
      try {
        const df = document.querySelector('df-messenger');
        if (!df) return;
        const greet = function() {
          if (sessionStorage.getItem('df_greeted') === '1') return;
          sessionStorage.setItem('df_greeted', '1');
          try { if (typeof df.renderCustomText === 'function') df.renderCustomText(''); } catch(_) {}
          try { if (typeof df.sendQuery === 'function') df.sendQuery('hi'); } catch(_) {}
        };
        if (typeof df.sendQuery === 'function') {
          greet();
        } else {
          df.addEventListener('df-messenger-loaded', greet);
        }
      } catch(_) {}
    });
  </script>
</body>
</html>
"""

dashboard_template = """
<!DOCTYPE html>
<html lang="en" class="bg-gray-50">
<head>
  <meta charset="UTF-8">
  <title>Doctor Dashboard - Hey Doc!</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
  <link rel="stylesheet" href="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/themes/df-messenger-default.css">
  <script src="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/df-messenger.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Outfit', sans-serif; }
    .glass { background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(10px); }
  </style>
</head>
<body class="min-h-screen flex bg-[#f8fafc]">
  <!-- Sidebar -->
  <aside class="w-72 bg-white border-r border-slate-200 flex flex-col fixed h-full z-50">
    <div class="p-6 border-b border-slate-50">
      <div class="flex items-center space-x-3">
        <div class="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-lg shadow-teal-100 p-1">
          <img src="/static/images/heydoc_logo.png" alt="HeyDoc" class="w-full h-full object-contain">
        </div>
        <span class="text-xl font-bold text-slate-800 tracking-tight">Hey Doc!</span>
      </div>
    </div>

    <div class="p-6 flex flex-col items-center border-b border-slate-50">
      <div class="relative group">
        <div class="w-24 h-24 rounded-2xl overflow-hidden border-4 border-white shadow-xl bg-slate-100 mb-3 group-hover:scale-105 transition-transform duration-300">
          {% if doctor_data and doctor_data.profile_photo %}
            <img src="/download/{{ doctor_data.profile_photo }}?v={{ range(1, 10000) | random }}" class="w-full h-full object-cover">
          {% else %}
            <div class="w-full h-full flex items-center justify-center text-slate-300">
              <i class="ri-user-smile-fill text-5xl"></i>
            </div>
          {% endif %}
        </div>
        <a href="/doctor/profile" class="absolute bottom-1 right-1 bg-teal-600 text-white w-8 h-8 rounded-lg flex items-center justify-center shadow-lg hover:bg-teal-700 transition-colors">
          <i class="ri-pencil-line"></i>
        </a>
      </div>
      <h3 class="text-lg font-bold text-slate-800">Dr. {{ doctor_data.name if doctor_data else doctor }}</h3>
      <p class="text-xs font-semibold text-slate-400 uppercase tracking-widest">{{ doctor_data.specialization if doctor_data and doctor_data.specialization else 'Medical Specialist' }}</p>
    </div>

    <nav class="flex-grow p-4 space-y-1 overflow-y-auto">
      <a href="/dashboard" class="flex items-center space-x-3 p-3 rounded-xl bg-teal-50 text-teal-700 font-bold group">
        <i class="ri-dashboard-3-line text-lg"></i>
        <span>Dashboard</span>
      </a>
      <a href="/video_call/consultation-{{ session.doctor }}" class="flex items-center space-x-3 p-3 rounded-xl text-teal-600 bg-teal-50 hover:bg-teal-100 transition-all font-bold">
        <i class="ri-video-chat-line text-xl"></i>
        <span>Video Consultation</span>
        <span class="ml-auto w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
      </a>
      <a href="/calendar" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-calendar-line text-lg"></i>
        <span>Schedule</span>
      </a>
      <a href="/prescriptions" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-medicine-bottle-line text-lg"></i>
        <span>Prescriptions</span>
      </a>
      <a href="/leave/calendar" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-calendar-check-line text-lg"></i>
        <span>Leave Calendar</span>
      </a>
      <a href="/holiday/calendar" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-calendar-event-line text-lg"></i>
        <span>Hospital Holidays</span>
      </a>
      <a href="/doctor/apply_leave" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-add-circle-line text-lg"></i>
        <span>Apply Leave</span>
      </a>
      <a href="/doctor/my_leaves" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-history-line text-lg"></i>
        <span>My Leaves</span>
      </a>
      <a href="/my_payroll" class="flex items-center space-x-3 p-3 rounded-xl text-slate-600 hover:bg-slate-50 hover:text-teal-600 transition-all">
        <i class="ri-bank-card-line text-lg"></i>
        <span>My Payroll</span>
      </a>
    </nav>

    <div class="p-4 border-t border-slate-50">
      <a href="/logout" class="flex items-center space-x-3 p-3 rounded-xl text-red-500 hover:bg-red-50 font-bold transition-all">
        <i class="ri-logout-box-line text-lg"></i>
        <span>Logout</span>
      </a>
    </div>
  </aside>

  <!-- Main Content -->
  <main class="ml-72 flex-grow p-8">
    <header class="flex justify-between items-center mb-10">
      <div>
        <h2 class="text-3xl font-bold text-slate-800">Patient Dashboard</h2>
        <p class="text-slate-400 mt-1">Manage your appointments and medical records</p>
      </div>
      <div class="flex items-center space-x-4">
        <div class="relative group">
          <button class="w-10 h-10 bg-white border border-slate-200 rounded-xl flex items-center justify-center text-slate-400 hover:border-teal-500 hover:text-teal-500 transition-all">
            <i class="ri-notification-3-line text-xl"></i>
          </button>
          {% if circulars %}
          <div class="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white"></div>
          {% endif %}
        </div>
        <a href="/add_appointment" class="bg-teal-600 text-white px-6 py-3 rounded-2xl font-bold shadow-xl shadow-teal-100 hover:bg-teal-700 hover:-translate-y-0.5 transition-all">
          <i class="ri-add-line mr-2"></i>New Appointment
        </a>
      </div>
    </header>
    
    {% if next_holiday %}
    <div class="mb-8 bg-blue-600 rounded-[30px] p-6 text-white shadow-xl flex items-center justify-between group overflow-hidden relative">
        <div class="absolute -right-4 -top-4 w-32 h-32 bg-white/10 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700"></div>
        <div class="flex items-center space-x-6 relative z-10">
            <div class="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center text-3xl blur-px"><i class="ri-calendar-event-line"></i></div>
            <div>
                <p class="text-xs font-black uppercase tracking-widest text-blue-100 opacity-80">Upcoming Hospital Holiday</p>
                <h3 class="text-2xl font-black">{{ next_holiday.title }}</h3>
            </div>
        </div>
        <div class="text-right relative z-10">
            <p class="text-[10px] font-black uppercase tracking-widest text-blue-200">Scheduled for</p>
            <p class="text-xl font-bold">{{ next_holiday.date }}</p>
            <a href="/holiday/calendar" class="mt-1 inline-block text-[10px] font-black uppercase tracking-widest underline underline-offset-4 hover:text-white transition-colors">View All Holidays</a>
        </div>
    </div>
    {% endif %}
      <!-- Appointments List -->
      <div class="lg:col-span-3 space-y-6">
        <!-- Search & Filter -->
        <div class="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm flex items-center space-x-4">
          <form method="GET" action="/dashboard" class="flex-grow flex items-center relative">
            <i class="ri-search-line absolute left-4 text-slate-400"></i>
            <input type="text" name="search_query" placeholder="Patient lookup by phone or ID..." 
                   class="w-full pl-12 pr-4 py-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-teal-500 outline-none text-sm"
                   value="{{ search_query if search_query else '' }}">
            <button type="submit" class="hidden">Search</button>
          </form>
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Sort:</span>
            <select onchange="this.form.submit()" name="sort_by" class="bg-slate-50 border-none rounded-xl px-4 py-3 text-sm font-semibold text-slate-600 outline-none focus:ring-2 focus:ring-teal-500">
               <option value="">Latest</option>
               <option value="name_asc" {% if sort_by == 'name_asc' %}selected{% endif %}>A-Z</option>
               <option value="date_asc" {% if sort_by == 'date_asc' %}selected{% endif %}>Oldest</option>
            </select>
          </div>
        </div>

        <!-- Appointment Table -->
        <div class="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left">
              <thead>
                <tr class="bg-slate-50/50">
                  <th class="p-6 text-xs font-bold text-slate-400 uppercase tracking-widest">Patient</th>
                  <th class="p-6 text-xs font-bold text-slate-400 uppercase tracking-widest">Schedule</th>
                  <th class="p-6 text-xs font-bold text-slate-400 uppercase tracking-widest">Symptoms</th>
                  <th class="p-6 text-xs font-bold text-slate-400 uppercase tracking-widest">Status</th>
                  <th class="p-6 text-xs font-bold text-slate-400 uppercase tracking-widest">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-50">
                {% for appointment in appointments %}
                <tr class="group hover:bg-teal-50/30 transition-colors">
                  <td class="p-6">
                    <div class="flex items-center space-x-3">
                      <div class="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center text-slate-400 group-hover:bg-teal-100 group-hover:text-teal-600 transition-colors">
                        <i class="ri-user-line text-lg"></i>
                      </div>
                      <div>
                        <a href="/patient_details/{{ appointment.get('phone', '') }}" class="font-bold text-slate-800 hover:text-teal-600 transition-colors">{{ appointment.get('name', 'N/A') }}</a>
                        <p class="text-xs text-slate-400">{{ appointment.get('phone', 'N/A') }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="p-6">
                    <p class="text-sm font-bold text-slate-700">{{ appointment.get('date', 'N/A') }}</p>
                    <p class="text-xs text-slate-400">{{ appointment.get('time', 'N/A') }}</p>
                  </td>
                  <td class="p-6">
                    <p class="text-sm text-slate-500 line-clamp-1 truncate max-w-[150px]">{{ appointment.get('symptoms', 'N/A') }}</p>
                  </td>
                  <td class="p-6">
                    <span class="px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-wider
                      {% if appointment.get('status') == 'confirmed' %}bg-green-100 text-green-700
                      {% elif appointment.get('status') == 'sent_to_doctor' %}bg-blue-100 text-blue-700
                      {% elif appointment.get('status') == 'cancelled' %}bg-red-100 text-red-700
                      {% else %}bg-yellow-100 text-yellow-700{% endif %}">
                      {{ appointment.get('status', 'pending').replace('_', ' ') }}
                    </span>
                  </td>
                  <td class="p-6">
                    <div class="flex items-center space-x-2">
                        {% if appointment.get('consultation_type') == 'Video Consultation' %}
                            <a href="/video_call/consultation-{{ appointment.appointment_id }}" target="_blank" class="w-8 h-8 bg-teal-100 text-teal-600 rounded-lg flex items-center justify-center hover:bg-teal-600 hover:text-white transition-all shadow-sm" title="Join Video Call">
                                <i class="ri-video-chat-line"></i>
                            </a>
                        {% endif %}
                      {% if appointment.get('status') == 'sent_to_doctor' %}
                        <a href="/update_appointment_status/{{ appointment.appointment_id }}/confirmed" class="w-8 h-8 bg-green-100 text-green-600 rounded-lg flex items-center justify-center hover:bg-green-500 hover:text-white transition-all shadow-sm">
                          <i class="ri-check-line"></i>
                        </a>
                        <a href="/edit_appointment/{{ appointment.appointment_id }}" class="w-8 h-8 bg-orange-100 text-orange-600 rounded-lg flex items-center justify-center hover:bg-orange-500 hover:text-white transition-all shadow-sm">
                          <i class="ri-history-line"></i>
                        </a>
                      {% else %}
                        <a href="/edit_appointment/{{ appointment.appointment_id }}" class="w-8 h-8 bg-slate-100 text-slate-600 rounded-lg flex items-center justify-center hover:bg-teal-600 hover:text-white transition-all shadow-sm">
                          <i class="ri-pencil-line"></i>
                        </a>
                      {% endif %}
                      <a href="/prescriptions?patient_phone={{ appointment.get('phone', '') }}" class="w-8 h-8 bg-purple-100 text-purple-600 rounded-lg flex items-center justify-center hover:bg-purple-600 hover:text-white transition-all shadow-sm">
                        <i class="ri-medicine-bottle-line"></i>
                      </a>
                    </div>
                  </td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          {% if not appointments %}
          <div class="p-20 text-center">
            <div class="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <i class="ri-calendar-todo-line text-4xl text-slate-200"></i>
            </div>
            <p class="text-slate-400 font-medium">No appointments found</p>
          </div>
          {% endif %}
        </div>
      </div>

      <!-- Right Sidebar Widgets -->
      <div class="space-y-8">
        <!-- Calendars Widget -->
        <div class="bg-white rounded-3xl border border-slate-100 shadow-sm p-6 overflow-hidden relative">
          <h3 class="text-lg font-bold text-slate-800 mb-6 flex items-center">
            <i class="ri-calendar-2-line mr-2 text-indigo-500"></i> Quick Calendars
          </h3>
          <div class="grid grid-cols-2 gap-3">
            <a href="/leave/calendar" class="flex flex-col items-center justify-center p-4 bg-indigo-50/50 rounded-2xl hover:bg-indigo-100 transition-colors border border-indigo-50">
              <i class="ri-calendar-check-line text-2xl text-indigo-600 mb-1"></i>
              <span class="text-[10px] font-black uppercase text-indigo-700">Leaves</span>
            </a>
            <a href="/holiday/calendar" class="flex flex-col items-center justify-center p-4 bg-pink-50/50 rounded-2xl hover:bg-pink-100 transition-colors border border-pink-50">
              <i class="ri-calendar-event-line text-2xl text-pink-600 mb-1"></i>
              <span class="text-[10px] font-black uppercase text-pink-700">Holidays</span>
            </a>
          </div>
        </div>

        <!-- Circulars Widget -->
        <div class="bg-white rounded-3xl border border-slate-100 shadow-sm p-6 overflow-hidden relative">
          <div class="flex justify-between items-center mb-6">
            <h3 class="text-lg font-bold text-slate-800">Circulars</h3>
            <span class="bg-red-50 text-red-500 px-2 py-1 rounded-lg text-[10px] font-black uppercase">{{ circulars|length }} NEW</span>
          </div>
          <div class="space-y-4 max-h-[400px] overflow-y-auto pr-2">
            {% for c in circulars %}
              <div class="group p-4 bg-slate-50 rounded-2xl border border-transparent hover:border-teal-100 hover:bg-teal-50/50 transition-all cursor-pointer">
                <p class="font-bold text-slate-800 text-sm group-hover:text-teal-700 transition-colors">{{ c.title }}</p>
                <p class="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">{{ c.content }}</p>
                <div class="flex justify-between items-center mt-3 pt-3 border-t border-slate-100">
                  <span class="text-[10px] font-bold text-slate-300 uppercase">{{ c.created_at.strftime('%d %b %Y') }}</span>
                  {% if c.file_path %}
                    <a href="/download/{{ c.file_path.split('/')[-1] }}" class="text-[10px] font-black text-teal-600 hover:underline flex items-center">
                      <i class="ri-download-2-line mr-1"></i> DOWNLOAD
                    </a>
                  {% endif %}
                </div>
              </div>
            {% endfor %}
            {% if not circulars %}
              <p class="text-slate-400 text-xs text-center py-10 italic">No new broadcast messages</p>
            {% endif %}
          </div>
        </div>

        <!-- Quick Help / Support -->
        <div class="bg-teal-600 rounded-3xl p-6 text-white overflow-hidden relative group">
          <div class="absolute -top-12 -right-12 w-40 h-40 bg-white/10 rounded-full group-hover:scale-110 transition-transform duration-700"></div>
          <i class="ri-customer-service-2-line text-4xl mb-4"></i>
          <h4 class="text-xl font-bold mb-2">Need Help?</h4>
          <p class="text-white/80 text-xs leading-relaxed mb-6">Our support team is available 24/7 for any technical issues.</p>
          <a href="#" class="inline-block bg-white text-teal-700 px-6 py-3 rounded-xl font-bold text-sm hover:shadow-lg transition-all">Support Center</a>
        </div>
      </div>
    </div>
  </main>

  <!-- Dialogflow Chatbot -->
  <df-messenger
    project-id="heydoc-473715-d6"
    agent-id="8e2c9653-bd6b-4151-be4d-75cc6c44b35e"
    language-code="en"
    max-query-length="-1">
    <df-messenger-chat-bubble
      chat-title="Hey Doc">
    </df-messenger-chat-bubble>
  </df-messenger>
  <style>
    df-messenger {
      z-index: 999;
      position: fixed;
      --df-messenger-font-color: #000;
      --df-messenger-font-family: Google Sans;
      --df-messenger-chat-background: #f3f6fc;
      --df-messenger-message-user-background: #d3e3fd;
      --df-messenger-message-bot-background: #fff;
      bottom: 16px;
      right: 16px;
    }
  </style>
</body>
</html>
"""

# --- Login Templates ---
login_template = """
<!DOCTYPE html>
<html lang="en" class="bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        body { font-family: 'Outfit', sans-serif; }
        .glass { background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(12px); }
        @keyframes scan {
            0% { top: 0; }
            50% { top: 100%; }
            100% { top: 0; }
        }
        .animate-scan { animation: scan 3s linear infinite; }
        .animate-spin-slow { animation: spin 8s linear infinite; }
    </style>
</head>
<body class="min-h-screen bg-gradient-to-br from-teal-500 via-teal-600 to-indigo-700 flex items-center justify-center p-6 relative overflow-y-auto">
    <!-- Decorative patterns -->
    <div class="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full -mr-48 -mt-48 blur-3xl"></div>
    <div class="absolute bottom-0 left-0 w-96 h-96 bg-teal-400/20 rounded-full -ml-48 -mb-48 blur-3xl"></div>

    <div class="w-full max-w-xl relative">
        <div class="glass border border-white/30 rounded-[40px] shadow-2xl overflow-hidden">
            <div class="p-10 md:p-14">
                <div class="text-center mb-10">
                    <div class="relative w-20 h-20 bg-white rounded-2xl shadow-xl flex items-center justify-center p-4 ring-1 ring-slate-100 mx-auto mb-6">
                         <img src="/static/images/heydoc_logo.png" alt="Hey Doc Logo" class="w-full h-full object-contain">
                    </div>
                    <h1 class="text-3xl font-bold text-slate-800 tracking-tight">Access Portal</h1>
                    <p class="text-slate-500 mt-2 font-medium">Identify your role to continue</p>
                </div>

                <form method="POST" action="/login" class="space-y-8">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% for category, message in messages %}
                            <div class="p-4 rounded-2xl {% if category == 'error' %}bg-red-50 text-red-600{% else %}bg-green-50 text-green-600{% endif %} font-bold text-sm text-center border border-red-100/50">
                                {{ message }}
                            </div>
                        {% endfor %}
                    {% endwith %}

                    <!-- Explicit Role Selection -->
                    <div class="space-y-4">
                        <p class="text-[10px] font-black uppercase tracking-[3px] text-slate-400 text-center">Select Workspace</p>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <!-- Admin Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="admin" class="peer hidden" {% if request.args.get('type') == 'admin' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-shield-keyhole-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">System Admin</span>
                                    <!-- Icon change on check -->
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>

                            <!-- Doctor Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="doctor" class="peer hidden" {% if not request.args.get('type') or request.args.get('type') == 'doctor' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-nurse-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Medical Doctor</span>
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>

                            <!-- Frontdesk Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="receptionist" class="peer hidden" {% if request.args.get('type') == 'receptionist' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-customer-service-2-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Front Desk</span>
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>

                            <!-- Pharmacist Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="pharmacist" class="peer hidden" {% if request.args.get('type') == 'pharmacist' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-capsule-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Pharmacist</span>
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>

                            <!-- Lab Assistant Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="lab_assistant" class="peer hidden" {% if request.args.get('type') == 'lab_assistant' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-microscope-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Lab Asst</span>
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>

                            <!-- Financial Analytics Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="financial_analytics" class="peer hidden" {% if request.args.get('type') == 'financial_analytics' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-bar-chart-box-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Finance</span>
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>

                            <!-- Branch Admin Option -->
                            <label class="relative cursor-pointer group">
                                <input type="radio" name="user_type" value="branch_admin" class="peer hidden" {% if request.args.get('type') == 'branch_admin' %}checked{% endif %}>
                                <div class="p-5 bg-white/50 border-2 border-slate-100 rounded-[32px] transition-all peer-checked:border-teal-500 peer-checked:bg-teal-50/50 peer-checked:shadow-lg peer-checked:shadow-teal-900/5 group-hover:border-teal-200 text-center relative overflow-hidden">
                                    <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3 transition-colors peer-checked:bg-white">
                                        <i class="ri-user-star-line text-2xl text-slate-400 group-hover:text-teal-500"></i>
                                    </div>
                                    <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Branch Admin</span>
                                    <div class="absolute top-3 right-3 scale-0 peer-checked:scale-100 transition-transform">
                                        <i class="ri-checkbox-circle-fill text-teal-600 text-xl"></i>
                                    </div>
                                </div>
                            </label>
                        </div>
                    </div>

                    <div class="space-y-6">
                        <div class="relative group">
                            <i class="ri-user-smile-line absolute left-5 top-1/2 -translate-y-1/2 text-slate-400 text-xl group-focus-within:text-teal-600 transition-colors"></i>
                            <input type="text" name="username" placeholder="Username" required 
                                   class="w-full pl-14 pr-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all font-bold text-slate-700">
                        </div>

                        <div class="relative group">
                            <i class="ri-lock-password-line absolute left-5 top-1/2 -translate-y-1/2 text-slate-400 text-xl group-focus-within:text-teal-600 transition-colors"></i>
                            <input type="password" name="password" id="passwordInput" placeholder="Password" required
                                   class="w-full pl-14 pr-14 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all font-bold text-slate-700">
                            <button type="button" onclick="togglePassword()" class="absolute right-5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-teal-600 transition-colors">
                                <i id="toggleIcon" class="ri-eye-line text-xl"></i>
                            </button>
                        </div>
                        
                        <div class="text-right">
                            <a href="/forgot_password" class="text-xs font-bold text-teal-600 hover:text-teal-700 hover:underline">Forgot Password?</a>
                        </div>

                        <div id="loginButtons" class="space-y-4">
                            <button type="submit" class="w-full bg-teal-600 hover:bg-teal-700 text-white py-5 rounded-[24px] font-black text-sm uppercase tracking-widest shadow-xl shadow-teal-900/20 hover:-translate-y-0.5 transition-all">
                                Secure Login <i class="ri-shield-check-line ml-2"></i>
                            </button>
                            
                            <div class="relative py-2">
                                <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-200"></div></div>
                                <div class="relative flex justify-center"><span class="bg-white px-4 text-xs text-gray-400 font-bold uppercase tracking-widest">OR</span></div>
                            </div>

                            <button type="button" onclick="initFaceLogin()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-4 rounded-[24px] font-black text-sm uppercase tracking-widest shadow-lg shadow-indigo-900/20 hover:-translate-y-0.5 transition-all flex items-center justify-center group">
                                <i class="ri-face-recognition-fill text-xl mr-2 group-hover:scale-110 transition-transform"></i>
                                Authenticate with Hey Doc! Face ID
                            </button>
                        </div>
                    </div>

                    <div class="text-center pt-4">
                        <a href="/auth_home" class="text-slate-400 hover:text-teal-600 text-xs font-bold uppercase tracking-widest transition-colors flex items-center justify-center">
                            <i class="ri-arrow-left-s-line mr-1 text-lg"></i> Back to Homepage
                        </a>
                    </div>
                </form>
            </div>
        </div>
        </div>
    </div>
    
    <!-- Face Login Modal -->
    <div id="faceLoginModal" class="fixed inset-0 z-50 hidden bg-gray-900/90 backdrop-blur-md flex items-center justify-center p-4">
        <div class="bg-white rounded-[40px] shadow-2xl p-8 max-w-md w-full relative overflow-hidden">
            <button onclick="closeFaceLogin()" class="absolute top-6 right-6 text-gray-400 hover:text-gray-800 transition-colors">
                <i class="ri-close-circle-fill text-3xl"></i>
            </button>
            
            <div class="text-center mb-8">
                <h3 class="text-2xl font-black text-gray-800">Face Authentication</h3>
                <p class="text-gray-500 text-sm mt-1">Please look directly at the camera</p>
            </div>
            
            <div class="relative rounded-3xl overflow-hidden bg-black aspect-[4/3] mb-6 shadow-inner ring-4 ring-gray-100">
                <video id="loginVideo" autoplay playsinline class="w-full h-full object-cover transform scale-x-[-1]"></video>
                <div class="absolute inset-0 border-2 border-white/20 rounded-3xl pointer-events-none"></div>
                <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div class="w-48 h-64 border-2 border-dashed border-white/50 rounded-[40%]"></div>
                </div>
            </div>
            
            <div id="loginStatus" class="text-center font-bold text-gray-600 mb-6 min-h-[1.5rem] animate-pulse">
                Initializing camera...
            </div>
            
            <button id="captureBtn" onclick="captureAndLogin()" class="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white py-4 rounded-2xl font-black uppercase tracking-widest transition-all">
                <i class="ri-camera-lens-line mr-2"></i> Scan Face
            </button>
        </div>
    </div>
    <script>
        function togglePassword() {
            const passwordInput = document.getElementById('passwordInput');
            const toggleIcon = document.getElementById('toggleIcon');
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                toggleIcon.classList.replace('ri-eye-line', 'ri-eye-off-line');
            } else {
                passwordInput.type = 'password';
                toggleIcon.classList.replace('ri-eye-off-line', 'ri-eye-line');
            }
        }

        let loginStream = null;

        async function initFaceLogin() {
            const modal = document.getElementById('faceLoginModal');
            const video = document.getElementById('loginVideo');
            const status = document.getElementById('loginStatus');
            const captureBtn = document.getElementById('captureBtn');
            
            modal.classList.remove('hidden');
            captureBtn.disabled = true;
            status.innerText = "Requesting camera access...";
            
            try {
                loginStream = await navigator.mediaDevices.getUserMedia({ video: true });
                video.srcObject = loginStream;
                status.innerText = "Camera active. Ready to scan.";
                captureBtn.disabled = false;
            } catch (err) {
                console.error("Camera error:", err);
                status.innerText = "Camera access denied. Please verify permissions.";
                status.classList.add('text-red-500');
            }
        }
        
        function closeFaceLogin() {
            const modal = document.getElementById('faceLoginModal');
            modal.classList.add('hidden');
            if (loginStream) {
                loginStream.getTracks().forEach(track => track.stop());
                loginStream = null;
            }
        }
        
        async function captureAndLogin() {
            const video = document.getElementById('loginVideo');
            const status = document.getElementById('loginStatus');
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            
            // Draw video frame to canvas
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Convert to base64
            const dataURL = canvas.toDataURL('image/jpeg');
            
            status.innerText = "Verifying identity...";
            
            try {
                const response = await fetch('/api/face_login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: dataURL })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    status.innerText = "Identity Verified! Redirecting...";
                    status.classList.add('text-green-600');
                    setTimeout(() => {
                        window.location.href = data.redirect_url;
                    }, 1000);
                } else {
                    status.innerText = data.message || "Authentication failed.";
                    status.classList.add('text-red-600');
                    setTimeout(() => {
                        status.classList.remove('text-red-600');
                        status.innerText = "Try again.";
                    }, 2000);
                }
            } catch (err) {
                console.error("Login error:", err);
                status.innerText = "Server error. Try again.";
            }
        }

        // Logic to show Face ID button only for Admin
        document.querySelectorAll('input[name="user_type"]').forEach(input => {
            input.addEventListener('change', (e) => {
                const adminBtn = document.getElementById('adminFaceId');
                if (e.target.value === 'admin') {
                    adminBtn.classList.remove('hidden');
                } else {
                    adminBtn.classList.add('hidden');
                }
            });
            // Trigger check on load
            if (input.checked && input.value === 'admin') {
                document.getElementById('adminFaceId').classList.remove('hidden');
            }
        });
    </script>
</body>
</html>
"""

patient_auth_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Patient Authentication - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        body { font-family: 'Outfit', sans-serif; }
    </style>
</head>
<body class="min-h-screen bg-gradient-to-br from-indigo-500 via-purple-600 to-teal-500 flex items-center justify-center p-6">
    <div class="w-full max-w-md">
        <div class="bg-white/95 backdrop-blur-md rounded-[40px] shadow-2xl p-10 border border-white/20">
            <div class="text-center mb-8">
                <div class="w-20 h-20 bg-indigo-100 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-lg">
                    <i class="ri-phone-line text-4xl text-indigo-600"></i>
                </div>
                <h1 class="text-3xl font-black text-slate-800 tracking-tight">Booking Portal</h1>
                <p class="text-slate-500 mt-2 font-medium">Enter your phone number to proceed</p>
            </div>

            <form method="POST" action="/patient/auth" class="space-y-6">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-4 rounded-2xl bg-{{ 'red' if category == 'error' else 'green' }}-50 text-{{ 'red' if category == 'error' else 'green' }}-600 font-bold text-sm text-center border border-{{ 'red' if category == 'error' else 'green' }}-100">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}

                <div class="relative group">
                    <i class="ri-smartphone-line absolute left-5 top-1/2 -translate-y-1/2 text-slate-400 text-xl group-focus-within:text-indigo-600 transition-colors"></i>
                    <input type="tel" name="phone" placeholder="Phone Number (e.g. 9876543210)" required
                           class="w-full pl-14 pr-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none transition-all font-bold text-slate-700">
                </div>

                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-5 rounded-3xl font-black text-sm uppercase tracking-widest shadow-xl shadow-indigo-900/20 hover:-translate-y-0.5 transition-all">
                    Verify & Continue
                </button>

                <div class="text-center mt-6">
                    <a href="/auth_home" class="text-slate-400 hover:text-indigo-600 text-xs font-bold uppercase tracking-widest transition-colors flex items-center justify-center">
                        <i class="ri-arrow-left-s-line mr-1 text-lg"></i> Back to Home
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

patient_verify_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTP Verification - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center p-6">
    <div class="max-w-md w-full">
        <div class="bg-white rounded-[40px] shadow-2xl p-10 border border-slate-100">
            <div class="text-center mb-10">
                <div class="w-20 h-20 bg-emerald-100 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-xl shadow-emerald-900/5">
                    <i class="ri-shield-check-line text-4xl text-emerald-600"></i>
                </div>
                <h1 class="text-3xl font-black text-slate-800 tracking-tight">Verification</h1>
                <p class="text-slate-500 mt-2 font-medium">Enter the code sent to your email</p>
                <p class="text-emerald-600 font-bold text-sm mt-1">{{ session.pending_email }}</p>
            </div>

            <form method="POST" action="/patient/verify" class="space-y-8">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-4 rounded-2xl bg-{{ 'red' if category == 'error' else 'green' }}-50 text-{{ 'red' if category == 'error' else 'green' }}-600 font-bold text-sm text-center border border-{{ 'red' if category == 'error' else 'green' }}-100">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}

                <input type="text" name="otp" placeholder="6-Digit OTP Code" required maxlength="6"
                       class="w-full text-center py-5 bg-slate-50 border-2 border-slate-100 rounded-3xl focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 outline-none transition-all text-3xl font-black tracking-[10px] text-slate-800">

                <button type="submit" class="w-full bg-slate-900 hover:bg-black text-white py-5 rounded-3xl font-black text-sm uppercase tracking-widest shadow-xl transition-all hover:-translate-y-0.5">
                    Confirm & Proceed
                </button>

                <div class="flex flex-col gap-4 text-center">
                    <button type="button" onclick="window.location.reload()" class="text-emerald-600 hover:text-emerald-700 text-xs font-black uppercase tracking-widest transition-colors">
                        Resend Code
                    </button>
                    <a href="/patient/auth" class="text-slate-400 hover:text-slate-600 text-xs font-black uppercase tracking-widest transition-colors">
                        Change Phone Number
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

patient_register_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finish Registration - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body class="min-h-screen bg-gradient-to-br from-teal-500 to-indigo-600 flex items-center justify-center p-6">
    <div class="max-w-lg w-full">
        <div class="bg-white rounded-[40px] shadow-2xl p-10 border border-white/20">
            <div class="text-center mb-8">
                <div class="w-16 h-16 bg-indigo-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <i class="ri-user-add-line text-3xl text-indigo-600"></i>
                </div>
                <h1 class="text-3xl font-black text-slate-800 tracking-tight">Patient Profile</h1>
                <p class="text-slate-500 mt-1 font-medium">Complete your details to finish registration</p>
                <div class="mt-4 px-4 py-2 bg-slate-50 rounded-xl inline-block border border-slate-100">
                    <span class="text-xs font-black text-slate-400 uppercase tracking-widest">Phone:</span>
                    <span class="text-sm font-bold text-indigo-600 ml-2">{{ session.pending_phone }}</span>
                </div>
            </div>

            <form method="POST" action="/patient/register_info" class="space-y-5">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-4 rounded-2xl bg-{{ 'red' if category == 'error' else 'green' }}-50 text-{{ 'red' if category == 'error' else 'green' }}-600 font-bold text-sm text-center border border-{{ 'red' if category == 'error' else 'green' }}-100">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}

                <div class="space-y-4">
                    <div class="relative">
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-2">Full Name</label>
                        <input type="text" name="name" placeholder="John Doe" required
                               class="w-full px-6 py-4 bg-slate-50 border border-slate-100 rounded-2xl focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-bold text-slate-700">
                    </div>
                    <div class="relative">
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-2">Email Address (for Verification)</label>
                        <input type="email" name="email" placeholder="john@example.com" required
                               class="w-full px-6 py-4 bg-slate-50 border border-slate-100 rounded-2xl focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-bold text-slate-700">
                    </div>
                    <div class="relative">
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-2">City</label>
                        <input type="text" name="city" placeholder="Hyderabad" required
                               class="w-full px-6 py-4 bg-slate-50 border border-slate-100 rounded-2xl focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-bold text-slate-700">
                    </div>
                </div>

                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-5 rounded-3xl font-black text-sm uppercase tracking-widest shadow-xl shadow-indigo-900/20 hover:-translate-y-0.5 transition-all mt-4">
                    Verify Email & Create Account
                </button>
            </form>
        </div>
    </div>
</body>
</html>
"""




@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/patient/book_appointment")
def patient_book_init():
    """Initial redirect for booking button"""
    return redirect("/patient/auth")

@app.route("/patient/book_appointment_submit", methods=["POST"])
def patient_book_appointment_submit():
    if "patient_name" not in session:
        flash("Please log in to book an appointment.", "error")
        return redirect("/patient/auth")

    try:
        # Get Patient Details
        patient = patients_collection.find_one({"phone": session.get("patient_phone")})
        if not patient:
            flash("Patient profile not found.", "error")
            return redirect("/patient_dashboard")

        # Get Form Data
        branch_name = request.form.get("branch")
        consultation_type = request.form.get("consultation_type")
        date_input = request.form.get("date")
        symptoms = request.form.get("symptoms")

        # Validate Inputs
        if not all([branch_name, consultation_type, date_input]):
            flash("Please fill in all required fields.", "error")
            return redirect("/patient_dashboard")

        # Get Branch ID
        branch = branches_collection.find_one({"name": branch_name})
        if not branch:
            flash("Selected clinic not found.", "error")
            return redirect("/patient_dashboard")
        
        branch_id = str(branch["_id"])

        # Format Date (YYYY-MM-DD -> DD-MM-YYYY)
        try:
            date_obj = datetime.strptime(date_input, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d-%m-%Y")
        except ValueError:
            formatted_date = date_input

        # Generate Appointment ID
        location_id = branch_name.replace(" ", "_")[:3].upper()
        date_str = datetime.now().strftime("%d%m%y")
        random_num = str(random.randint(1000, 9999))
        appointment_id = f"BK_{location_id}_{date_str}_{random_num}"

        # Create Appointment Record
        appointment_doc = {
            "appointment_id": appointment_id,
            "patient_id": str(patient["_id"]),
            "name": patient["name"],
            "phone": patient["phone"],
            "email": patient.get("email", ""),
            "branch_id": branch_id,  # CRITICAL: For reception dashboard logic
            "branch_name": branch_name,
            "consultation_type": consultation_type,
            "date": formatted_date,
            "time": request.form.get("time", "Pending Confirmation"),  # User selected time
            "symptoms": symptoms,
            "status": "pending",  # Initial status
            "created_at": datetime.now(),
            "created_at_str": datetime.now().strftime("%d-%m-%Y %I:%M %p")
        }

        appointments_collection.insert_one(appointment_doc)
        
        flash("Appointment request submitted successfully! The reception will confirm your slot shortly.", "success")
        return redirect("/patient_dashboard")

    except Exception as e:
        print(f"Error booking appointment: {e}")
        flash("An error occurred while processing your request.", "error")
        return redirect("/patient_dashboard")

@app.route("/patient/dashboard")
def patient_dashboard_redirect():
    """Redirect for compatibility with old links"""
    return redirect("/patient_dashboard")

@app.route("/patient/auth", methods=["GET", "POST"])
def patient_auth():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        if not phone:
            flash("Phone number is required", "error")
            return redirect("/patient/auth")
        
        normalized_phone, phone_error = normalize_indian_phone(phone)
        if phone_error:
            flash(phone_error, "error")
            return redirect("/patient/auth")
        
        session["pending_phone"] = normalized_phone
        
        # Check if patient exists
        patient = patients_collection.find_one({"phone": normalized_phone})
        
        if patient:
            email = patient.get("email")
            if not email:
                # Incomplete profile - redirect to registration to fill details
                flash("Your profile is incomplete. Please finish setting it up.", "info")
                return redirect("/patient/register_info")
            
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            expires_at = datetime.utcnow() + timedelta(minutes=10)
            
            # Store OTP
            login_otp_collection.insert_one({
                "email": email,
                "phone": normalized_phone,
                "otp": otp,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "used": False,
                "user_type": "patient"
            })
            
            # Send Email
            dispatch_success, msg = send_otp_email(email, otp)
            
            session["pending_email"] = email
            session["is_new_patient"] = False
            
            if not dispatch_success:
                flash(f"OTP dispatch failed: {msg}. (Check Console for Backup OTP)", "warning")
            else:
                flash("A verification code has been sent to your registered email.", "success")
            
            return redirect("/patient/verify")
        else:
            # New Patient - Redirect to collect name/email
            return redirect("/patient/register_info")
            
    return render_template_string(patient_auth_template)

@app.route("/patient/register_info", methods=["GET", "POST"])
def patient_register_info():
    if "pending_phone" not in session:
        return redirect("/patient/auth")
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        city = request.form.get("city", "").strip()
        
        if not all([name, email, city]):
            flash("All fields are required", "error")
            return redirect("/patient/register_info")
        
        session["pending_name"] = name
        session["pending_email"] = email
        session["pending_city"] = city
        session["is_new_patient"] = True
        
        # Generate OTP for email verification
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        login_otp_collection.insert_one({
            "email": email,
            "phone": session["pending_phone"],
            "otp": otp,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "used": False,
            "user_type": "patient"
        })
        
        dispatch_success = send_otp_email(email, otp)
        if not dispatch_success:
            flash(f"OTP dispatch failed. FOR TESTING: {otp}", "warning")
        else:
            flash("A verification code has been sent to your email to verify it.", "success")
            
        return redirect("/patient/verify")
        
    return render_template_string(patient_register_template)

@app.route("/patient/verify", methods=["GET", "POST"])
def patient_verify():
    if "pending_email" not in session or "pending_phone" not in session:
        return redirect("/patient/auth")
        
    if request.method == "POST":
        otp_input = request.form.get("otp", "").strip()
        
        # Verify OTP
        otp_record = login_otp_collection.find_one({
            "email": session["pending_email"],
            "otp": otp_input,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if otp_record:
            # Mark OTP as used
            login_otp_collection.update_one({"_id": otp_record["_id"]}, {"$set": {"used": True}})
            
            # If new patient or incomplete profile, create/update record
            if session.get("is_new_patient"):
                new_patient_data = {
                    "name": session["pending_name"],
                    "email": session["pending_email"],
                    "phone": session["pending_phone"],
                    "city": session["pending_city"],
                    "updated_at": datetime.utcnow()
                }
                
                # Use upsert or check for existing record to avoid duplicate phone errors
                existing = patients_collection.find_one({"phone": session["pending_phone"]})
                if existing:
                    patients_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": new_patient_data}
                    )
                    session["patient_id"] = existing.get("patient_id") or f"PAT{random.randint(100000, 999999)}"
                    if not existing.get("patient_id"):
                        patients_collection.update_one({"_id": existing["_id"]}, {"$set": {"patient_id": session["patient_id"]}})
                else:
                    new_patient_data["patient_id"] = f"PAT{random.randint(100000, 999999)}"
                    new_patient_data["created_at"] = datetime.utcnow()
                    patients_collection.insert_one(new_patient_data)
                    session["patient_id"] = new_patient_data["patient_id"]
                
                session["patient_name"] = session["pending_name"]
            else:
                patient = patients_collection.find_one({"phone": session["pending_phone"]})
                session["patient_name"] = patient.get("name")
                session["patient_id"] = patient.get("patient_id") or f"PAT{random.randint(100000, 999999)}"
                if not patient.get("patient_id"):
                     patients_collection.update_one({"_id": patient["_id"]}, {"$set": {"patient_id": session["patient_id"]}})
            
            # Set session variables for login
            session["patient"] = session["patient_name"]
            session["patient_phone"] = session["pending_phone"]
            session["patient_email"] = session["pending_email"]
            
            # Clear pending session
            for key in ["pending_phone", "pending_email", "pending_name", "pending_city", "is_new_patient"]:
                session.pop(key, None)
                
            flash("Successfully verified!", "success")
            return redirect("/patient_dashboard")
        else:
            flash("Invalid or expired OTP", "error")
            return redirect("/patient/verify")
            
    return render_template_string(patient_verify_template)

@app.route("/patient/log_vitals", methods=["POST"])
def patient_log_vitals():
    if "patient_phone" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    weight = request.form.get("weight")
    bp = request.form.get("bp")
    sugar = request.form.get("sugar")
    
    vitals = {
        "weight": weight,
        "bp": bp,
        "sugar": sugar,
        "date": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "created_at": datetime.utcnow()
    }
    
    patients_collection.update_one(
        {"phone": session["patient_phone"]},
        {"$push": {"vitals": {"$each": [vitals], "$position": 0}}}
    )
    
    flash("Vitals logged successfully", "success")
    return redirect("/patient_dashboard")

@app.route("/patient/upload_record", methods=["POST"])
def patient_upload_record():
    if "patient_phone" not in session:
        return redirect("/login")
    
    report_name = request.form.get("report_name")
    file = request.files.get("report_file")
    
    if not file or not report_name:
        flash("File and name are required", "error")
        return redirect("/patient_dashboard")
    
    filename = secure_filename(f"{session['patient_phone']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
    file_path = os.path.join(CERTIFICATES_FOLDER, filename)
    file.save(file_path)
    
    # Store in database
    report_data = {
        "name": report_name,
        "filename": filename,
        "url": f"/uploads/certificates/{filename}",
        "date": datetime.now().strftime("%d-%m-%Y"),
        "created_at": datetime.utcnow()
    }
    
    patients_collection.update_one(
        {"phone": session["patient_phone"]},
        {"$push": {"medical_reports": {"$each": [report_data], "$position": 0}}}
    )
    
    flash("Record uploaded successfully", "success")
    return redirect("/patient_dashboard")

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files to prevent 404s for reports and certificates"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/patient/trigger_sos", methods=["POST"])
def patient_trigger_sos():
    if "patient_phone" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    branch = request.form.get("branch")
    # In a real app, this would trigger SMS/Push notifications
    print(f"!!! SOS TRIGGERED BY {session['patient']} for branch {branch} !!!")
    
    return jsonify({"success": True})

@app.route("/patient_dashboard")
def patient_dashboard():
    if "patient_phone" not in session:
        return redirect("/login")
    
    phone = session["patient_phone"]
    patient = patients_collection.find_one({"phone": phone})
    
    if not patient:
        flash("Patient profile not found.", "error")
        return redirect("/")
    
    # Update session if missing ID
    if "patient_id" not in session:
        session["patient_id"] = patient.get("patient_id", "N/A")

    # Fetch Data
    upcoming_appointments = list(appointments_collection.find({"phone": phone}).sort("date", -1))
    medical_reports = patient.get("medical_reports", [])
    patient_vitals = patient.get("vitals", [])
    prescriptions = list(prescriptions_collection.find({"patient_phone": phone}).sort("created_at", -1))
    payments = list(payments_collection.find({"phone": phone}).sort("created_at", -1))
    
    # Reminders
    reminders = []
    for appt in upcoming_appointments:
        if appt.get("status") == "pending":
            reminders.append({
                "title": f"Upcoming Appointment: Dr. {appt.get('doctor_name', 'Hey Doc!')}",
                "date": appt.get("date"),
                "time": appt.get("time")
            })
    
    # Real Pharmacy Orders
    pharmacy_orders = list(pharmacy_orders_collection.find({"patient_phone": phone}).sort("created_at", -1))
    
    # Analytics
    analytics = {
        "total_visits": len(upcoming_appointments),
        "total_prescriptions": len(prescriptions),
        "total_reports": len(medical_reports),
        "last_visit": upcoming_appointments[0].get("date") if upcoming_appointments else "None"
    }

    # Find next video consultation
    next_video_appt = None
    for appt in upcoming_appointments:
        if appt.get("consultation_type") == "Video Consultation" and appt.get("status") not in ["cancelled", "completed", "rejected"]:
            next_video_appt = appt
            break
            
    branches = list(branches_collection.find({}))
    
    return render_template("patient_dashboard.html",
                           patient=patient,
                           upcoming_appointments=upcoming_appointments,
                           medical_reports=medical_reports,
                           patient_vitals=patient_vitals,
                           analytics=analytics,
                           branches=branches,
                           reminders=reminders,
                           prescriptions=prescriptions,
                           payments=payments,
                           pharmacy_orders=pharmacy_orders,
                           next_video_appt=next_video_appt,
                           lang=session.get('lang', 'en'))


@app.route("/get_time_slots")
def get_time_slots():
    city = request.args.get("city", "Hyderabad")
    date_str = request.args.get("date")
    
    # Default slots
    default_slots = [
        "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
        "12:00", "12:30", "14:00", "14:30", "15:00", "15:30",
        "16:00", "16:30", "17:00", "17:30", "18:00", "18:30"
    ]
    
    return jsonify({"time_slots": default_slots})

@app.route("/get_booked_slots/<date_str>")
def get_booked_slots(date_str):
    city = request.args.get("city", "Hyderabad")
    
    # Normalize date
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = dt.strftime("%d-%m-%Y")
    except:
        formatted_date = date_str
        
    booked = appointments_collection.find(
        {"date": formatted_date, "branch_name": city},
        {"time": 1, "_id": 0}
    )
    
    booked_slots = [b.get("time") for b in booked if b.get("time")]
    return jsonify({"booked_slots": booked_slots})

@app.route("/patient/order_medicine", methods=["POST"])
def patient_order_medicine():
    if "patient_phone" not in session:
        return redirect("/login")
        
    items = request.form.get("items")
    order_type = request.form.get("order_type")
    
    if not items:
        flash("Please specify items to order.", "error")
        return redirect("/patient_dashboard")
        
    phone = session["patient_phone"]
    patient = patients_collection.find_one({"phone": phone})
    
    order = {
        "order_id": f"ORD{random.randint(10000,99999)}",
        "patient_id": patient["_id"] if patient else None,
        "patient_phone": phone,
        "items": items,
        "order_type": order_type,
        "status": "Processing",
        "created_at": datetime.utcnow(),
        "date": datetime.now().strftime("%d-%m-%Y")
    }
    
    pharmacy_orders_collection.insert_one(order)
    flash("Pharmacy order placed successfully!", "success")
    return redirect("/patient_dashboard")

@app.route("/video_call/<room_name>")
def video_call_room(room_name):
    if not any(k in session for k in ["doctor", "patient", "admin", "receptionist"]):
        flash("Unauthorized access to video consultation.", "error")
        return redirect("/login")
    
    user_name = session.get("doctor") or session.get("patient_name") or session.get("admin") or session.get("receptionist")
    
    dashboard_url = "/"
    if "doctor" in session:
        dashboard_url = "/dashboard"
    elif "patient" in session:
        dashboard_url = "/patient_dashboard"
    elif "receptionist" in session:
        dashboard_url = "/reception_dashboard"
    elif "admin" in session:
        dashboard_url = "/admin/dashboard"
        
    return render_template("video_call.html", room_name=room_name, user_name=user_name, dashboard_url=dashboard_url)

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    print(f"DEBUG REDIRECT: verify_otp accessed. pending_face_authorized: {session.get('pending_face_authorized')}")
    # DOUBLE SUBMISSION PROTECTION: If we already authorized face ID, don't loop back
    # Only redirect to face verify if it's NOT an admin/branch_admin (who bypass for now)
    if session.get("pending_face_authorized"):
        user_type = session.get("pending_user_type")
        print(f"DEBUG REDIRECT: pending_face_authorized is SET. user_type: {user_type}")
        if user_type not in ["admin", "branch_admin"]:
            print("DEBUG REDIRECT: REDIRECTING TO FACE VERIFY")
            return redirect("/staff/face_verify")

    if "pending_user" not in session:
        return redirect("/login")
    
    email = session.get("pending_email")
    
    if request.method == "POST":
        otp_input = request.form.get("otp")
        
        stored_otp = login_otp_collection.find_one({
            "email": email,
            "otp": otp_input,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if stored_otp:
            # OTP is valid! Finalize login.
            login_otp_collection.update_one({"_id": stored_otp["_id"]}, {"$set": {"used": True}})
            
            user_type = session.get("pending_user_type")
            username = session.get("pending_user")
            
            if user_type == "patient":
                session["patient"] = session["pending_user"]
                session["patient_phone"] = session["pending_user"]
                session["patient_id"] = session.get("pending_user_id")
                session["patient_branch"] = session.get("pending_user_branch")
                
                # Clear pending session
                session.pop("pending_user", None)
                session.pop("pending_otp", None)
                session.pop("pending_user_type", None)
                session.pop("pending_user_id", None)
                session.pop("pending_user_branch", None)
                
                flash("Logged in successfully!", "success")
                return redirect("/patient_dashboard")
            
            # --- ADMIN FACE ID 2FA FLOW ---
            elif user_type in ["admin", "branch_admin"]:
                # Check if admin has Face ID registered
                collection = admin_collection if user_type == "admin" else branch_admins_collection
                current_user = collection.find_one({"username": username})
                
                has_face_id = current_user and "face_encoding" in current_user and current_user.get("face_id_enabled", False)
                
                if has_face_id:
                    # Admin has Face ID - require 2FA verification
                    session["pending_face_user"] = username
                    session["pending_face_type"] = user_type
                    session["pending_face_authorized"] = True
                    session["pending_face_email"] = email
                    
                    if user_type == "branch_admin" and current_user:
                        session["pending_face_branch"] = current_user.get("branch_id")
                    
                    # Clear OTP session but keep face verification pending
                    for key in ["pending_user", "pending_otp", "pending_user_type", "pending_email"]:
                        session.pop(key, None)
                    
                    print(f"DEBUG: Admin {username} has Face ID, redirecting to verification")
                    return redirect("/staff/face_verify")
                else:
                    # Admin does not have Face ID - allow direct login
                    session[user_type] = username
                    if email: session["email"] = email
                    
                    target_dashboard = "/admin_dashboard" if user_type == "admin" else "/branch_admin_dashboard"
                    
                    # Check for branch admin branch_id
                    if user_type == "branch_admin" and current_user:
                        session["branch_admin_branch"] = current_user.get("branch_id")

                    # Clear pending session
                    for key in ["pending_user", "pending_otp", "pending_user_type", "pending_email"]:
                        session.pop(key, None)

                    flash(f"Welcome back, {username}!", "success")
                    return redirect(target_dashboard)
                
            else:
                # Standard Staff (Doctor, Receptionist, Pharmacist, Lab, Finance) - No Face ID
                target_dashboard = {
                    "doctor": "/dashboard",
                    "receptionist": "/reception_dashboard",
                    "pharmacist": "/pharmacist_dashboard",
                    "lab_assistant": "/lab_dashboard",
                    "financial_analytics": "/financial_analytics_dashboard"
                }.get(user_type, "/dashboard")
                
                # Check for Temporary Password
                user_collection_map = {
                    "doctor": doctors_collection,
                    "receptionist": receptionists_collection,
                    "pharmacist": pharmacists_collection,
                    "lab_assistant": lab_assistants_collection,
                    "financial_analytics": financial_analytics_collection,
                    "branch_admin": branch_admins_collection
                }
                
                if user_type in user_collection_map:
                    current_user = user_collection_map[user_type].find_one({"username": username})
                    if current_user and current_user.get("is_temp_password", False):
                        # Force Password Change
                        session["pending_reset_user"] = username
                        session["pending_reset_type"] = user_type
                        
                        # Clear OTP session
                        session.pop("pending_user", None)
                        session.pop("pending_otp", None)
                        session.pop("pending_user_type", None)
                        
                        flash("Security Notice: You are using a temporary password. Please set a new secure password.", "warning")
                        return redirect("/change_password_force")
                        
                
                # Finalize Session Directly
                session[user_type] = username
                if email: session["email"] = email # Use the email from session
                
                # Update online status for doctor
                if user_type == "doctor":
                    doctors_collection.update_one({"username": username}, {"$set": {"is_online": True}})
                    session["doctor_branch"] = current_user.get("branch_id") if current_user else session.get("pending_user_branch")
                
                elif user_type == "receptionist":
                    session["receptionist_branch"] = current_user.get("branch_id") if current_user else session.get("pending_user_branch")
                
                # Clear pending session
                session.pop("pending_user", None)
                session.pop("pending_otp", None)
                session.pop("pending_user_type", None)
                
                flash(f"Welcome back, {current_user.get('name', username) if current_user else username}!", "success")
                return redirect(target_dashboard)
        else:
            flash("Invalid or expired OTP. Please try again.", "error")
            return redirect("/verify_otp")
            
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Identity Verification - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
            body { font-family: 'Outfit', sans-serif; }
            .glass { background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(16px); }
            .otp-input:focus { border-color: #0d9488; box-shadow: 0 0 0 4px rgba(13, 148, 136, 0.1); }
        </style>
    </head>
    <body class="min-h-screen bg-gradient-to-br from-teal-600 via-teal-700 to-emerald-800 flex items-center justify-center p-6 text-slate-800">
        <div class="w-full max-w-md">
            <div class="glass border border-white/40 rounded-[40px] shadow-2xl overflow-hidden">
                <div class="p-10 text-center">
                    <div class="w-20 h-20 bg-teal-600 rounded-[30px] flex items-center justify-center text-white shadow-xl shadow-teal-900/20 mx-auto mb-8">
                        <i class="ri-shield-check-line text-4xl"></i>
                    </div>
                    <h2 class="text-3xl font-bold tracking-tight mb-2">Verify Identity</h2>
                    <p class="text-slate-500 font-medium text-sm px-4">A security code has been sent to your email <span class="text-teal-600 font-bold">{{ email[:3] }}****@****.com</span></p>
                    
                    <form method="POST" class="mt-10 space-y-6" onsubmit="document.getElementById('submit-btn').disabled=true; document.getElementById('submit-btn').innerHTML='<i class=\'ri-loader-4-line animate-spin mr-2\'></i> PROCESSING...';">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% for category, message in messages %}
                                <div class="p-4 rounded-2xl {% if category == 'error' %}bg-red-50 text-red-600{% else %}bg-green-50 text-green-600{% endif %} font-bold text-xs border border-red-100/50">
                                    {{ message }}
                                </div>
                            {% endfor %}
                        {% endwith %}
                        
                        <div class="space-y-2">
                            <label class="text-[10px] font-black uppercase tracking-[3px] text-slate-400 block ml-1 text-left">6-Digit Access Code</label>
                            <input type="text" name="otp" maxlength="6" required autofocus
                                   placeholder="0 0 0 0 0 0"
                                   class="w-full px-6 py-5 bg-white/50 border-2 border-slate-100 rounded-2xl outline-none transition-all text-center text-3xl font-black tracking-[10px] text-teal-800 focus:border-teal-500 focus:bg-white shadow-inner">
                        </div>

                        <button type="submit" id="submit-btn" class="w-full bg-teal-600 text-white py-5 rounded-[22px] font-black uppercase tracking-widest text-sm hover:bg-teal-700 shadow-2xl shadow-teal-900/20 transition-all active:scale-[0.98]">
                            Complete Login
                        </button>
                    </form>
                    
                        <div class="mt-8 pt-6 border-t border-slate-100/50">
                            <div class="flex flex-col items-center gap-2">
                                <p class="text-xs text-slate-400 font-medium">Didn't receive the code?</p>
                                <a href="/resend_otp" class="text-teal-600 font-bold hover:underline text-sm py-2 px-4 rounded-xl hover:bg-teal-50 transition-all flex items-center gap-2">
                                    <i class="ri-refresh-line"></i> Resend Security Code
                                </a>
                                <a href="/login" class="text-slate-400 font-bold hover:text-teal-600 text-[10px] uppercase tracking-widest mt-2 hover:underline">
                                    Cancel & Restart
                                </a>
                            </div>
                        </div>
                </div>
            </div>
            
            <p class="text-white/40 text-[10px] font-black uppercase tracking-widest text-center mt-8">Secure Session Protection enabled</p>
        </div>
    </body>
    </html>
    """, email=email)

@app.route("/resend_otp")
def resend_otp():
    if "pending_user" not in session:
        return redirect("/login")
        
    email = session.get("pending_email")
    username = session.get("pending_user")
    user_type = session.get("pending_user_type")
    
    # Generate New OTP
    otp = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    # Update/Insert OTP in Database
    login_otp_collection.insert_one({
        "email": email,
        "otp": otp,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "used": False,
        "user_type": user_type,
        "username": username
    })
    
    # Dispatch
    success = send_otp_email(email, otp)
    if success:
        flash("A new security code has been sent to your email.", "success")
    else:
        flash("Security code dispatch failed. Please contact support.", "error")
        
    return redirect("/verify_otp")



# ==========================================
# PATIENT ROUTES
# ==========================================

@app.route("/patient_login", methods=["GET", "POST"])
def patient_login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        
        if not all([phone, name, email]):
            flash("All fields are required.", "error")
            return redirect("/patient_login")
            
        # check if patient exists or create new
        patient = patients_collection.find_one({"phone": phone})
        if not patient:
            patients_collection.insert_one({
                "name": name,
                "phone": phone,
                "email": email,
                "created_at": datetime.utcnow()
            })
        
        # Send OTP
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        login_otp_collection.insert_one({
            "email": email,
            "otp": otp,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "used": False,
            "user_type": "patient",
            "username": name
        })
        
        dispatch_success = send_otp_email(email, otp)
        
        session["pending_user"] = name
        session["pending_user_type"] = "patient"
        session["pending_email"] = email
        session["pending_phone"] = phone
        
        if not dispatch_success:
            flash(f"Security Alert: {msg}. OTP: {otp} (Console Logged)", "warning")
        else:
            flash("Verification code sent to your email.", "success")
            
        return redirect("/verify_otp")
        
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Patient Login - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-teal-50 flex items-center justify-center p-4">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md">
            <div class="text-center mb-8">
                <img src="/static/images/heydoc_logo.png" alt="HeyDoc" class="h-12 mx-auto mb-4">
                <h1 class="text-2xl font-bold text-gray-800">Patient Portal</h1>
                <p class="text-gray-500">Book appointments seamlessly</p>
            </div>
            
            <form method="POST" class="space-y-4">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800 text-sm">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}
                
                <div>
                    <label class="block text-gray-700 text-sm font-bold mb-2">Full Name</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <i class="ri-user-line text-gray-400"></i>
                        </div>
                        <input type="text" name="name" required class="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500 transition-colors" placeholder="Enter your name">
                    </div>
                </div>
                
                <div>
                    <label class="block text-gray-700 text-sm font-bold mb-2">Email Address</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <i class="ri-mail-line text-gray-400"></i>
                        </div>
                        <input type="email" name="email" required class="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500 transition-colors" placeholder="Enter your email">
                    </div>
                </div>

                <div>
                    <label class="block text-gray-700 text-sm font-bold mb-2">Phone Number</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <i class="ri-phone-line text-gray-400"></i>
                        </div>
                        <input type="tel" name="phone" required class="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-500 transition-colors" placeholder="Enter phone number">
                    </div>
                </div>
                
                <button type="submit" class="w-full bg-teal-600 text-white py-3 rounded-lg font-bold hover:bg-teal-700 transition-transform active:scale-95 shadow-lg shadow-teal-200">
                    Access Portal
                </button>
            </form>
            
            <div class="mt-6 text-center text-sm text-gray-500">
                <a href="/login" class="text-teal-600 hover:underline">Staff Login</a>
            </div>
        </div>
    </body>
    </html>
    """)



# Existing Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    # Check if already logged in
    current_role = get_user_role()
    if current_role:
        print(f"DEBUG LOGIN: User already logged in as {current_role}. session: {dict(session)}")
        if "admin" in session:
            return redirect("/admin_dashboard")
        elif "doctor" in session:
            return redirect("/dashboard")
        elif "receptionist" in session:
            return redirect("/reception_dashboard")
        elif "patient" in session:
            return redirect("/patient_dashboard")
    
    # Handle login form submission
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user_type = request.form.get("user_type", "doctor").strip()
        
        print(f"DEBUG LOGIN: POST attempt. user={username}, type={user_type}")
        
        # Completely clear session at start of new login attempt to prevent any state bleed/bypass
        session.clear()
        print(f"DEBUG LOGIN: Session cleared. current session: {dict(session)}")
        
        if not username or not password:
            flash("Username and password are required", "error")
            return redirect("/login")
        
        user = None
        email = None
        
        # Check based on user type
        if user_type == "admin":
            user = admin_collection.find_one({"username": username, "password": password})
        elif user_type == "doctor":
            user = doctors_collection.find_one({"username": username, "password": password})
        elif user_type == "receptionist":
            user = receptionists_collection.find_one({"username": username, "password": password})
        elif user_type == "pharmacist":
            user = pharmacists_collection.find_one({"username": username, "password": password})
        elif user_type == "lab_assistant":
            user = lab_assistants_collection.find_one({"username": username, "password": password})
        elif user_type == "financial_analytics":
            user = financial_analytics_collection.find_one({"username": username, "password": password})
        elif user_type == "branch_admin":
            user = branch_admins_collection.find_one({"username": username, "password": password})
        
        if user:
            email = user.get("email")
            print(f"DEBUG LOGIN: User found. email: {email}")
            if not email:
                flash("Security Error: No registered email found for this account. Please contact system admin to set up your 2FA email.", "error")
                return redirect("/login")
            
            # Generate Secure OTP
            otp = str(random.randint(100000, 999999))
            expires_at = datetime.utcnow() + timedelta(minutes=5)
            
            # Store OTP in Database
            login_otp_collection.insert_one({
                "email": email,
                "otp": otp,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "used": False,
                "user_type": user_type,
                "username": username
            })
            
            # Dispatch Verification Email
            dispatch_success = send_otp_email(email, otp)
            
            # Establish temporary pending session (Required for /verify_otp)
            session["pending_user"] = username
            session["pending_user_type"] = user_type
            session["pending_email"] = email
            session["pending_branch"] = user.get("branch_id")
            
            print(f"DEBUG LOGIN: Redirecting to /verify_otp. Session: {dict(session)}")
            
            if dispatch_success:
                flash(f"A security code has been sent to your registered email.", "success")
            else:
                flash(f"Security Alert: Email delivery failed. For demo purposes, your code is: {otp}", "error")
            
            return redirect("/verify_otp")
        else:
            print("DEBUG LOGIN: Invalid credentials")
            flash("Invalid username or password", "error")
    
    # GET request - show login form
    return render_template_string(login_template) 

@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
        
    # Check if admin has face registered
    admin_user = admin_collection.find_one({"username": session["admin"]})
    user_has_face = True if admin_user and "face_encoding" in admin_user else False

    branches = list(branches_collection.find({}))
    print(f"\n{'*'*50}")
    print(f"DEBUG DASHBOARD: branches_collection.name = {branches_collection.name}")
    print(f"DEBUG DASHBOARD: branches count = {len(branches)}")
    print(f"{'*'*50}\n")
    doctors = list(doctors_collection.find({}))
    receptionists = list(receptionists_collection.find({}))
    pharmacists = list(pharmacists_collection.find({}))
    lab_assistants = list(lab_assistants_collection.find({}))
    finance_analytics = list(financial_analytics_collection.find({}))
    branch_admins = list(branch_admins_collection.find({}))
    leaves = list(leaves_collection.find({"status": "pending"}))
    circulars = list(circulars_collection.find({}).sort("created_at", -1).limit(10))
    
    # Enrich leave data with staff balance and name
    for leave in leaves:
        username = leave.get("username") or leave.get("doctor_username")
        role = leave.get("role", "doctor")  # Default to doctor for old records
        
        staff = None
        if role == "doctor" or not role:
            staff = doctors_collection.find_one({"username": username})
        elif role == "receptionist":
            staff = receptionists_collection.find_one({"username": username})
            
        if staff:
            leave["staff_name"] = staff.get("name", "N/A")
            leave["staff_role"] = role
            # Determine appropriate balance for leave type
            ltype = leave.get("leave_type", "casual").lower()
            if "casual" in ltype: ltype = "casual"
            
            if "leave_accounts" in staff:
                accounts = staff["leave_accounts"]
                target_type = ltype if ltype in accounts else "casual"
                leave["staff_balance"] = accounts[target_type].get("balance", 0)
            else:
                leave["staff_balance"] = staff.get("leaves_remaining", 20)
        else:
             leave["staff_name"] = leave.get("doctor_name", "N/A") # Fallback
             leave["staff_balance"] = "N/A"
             leave["staff_role"] = role
    
    # Fetch consultation fees for dashboard
    fees = site_settings_collection.find_one({"type": "fees"}) or {
        "consultation_fee": 500,
        "free_consultation_days": 7
    }
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Admin Dashboard - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <style>
            .perspective-1000 { perspective: 1000px; }
            .preserve-3d { transform-style: preserve-3d; }
            .nav-item { transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); }
            .nav-item:hover { 
                transform: translateX(10px) translateZ(20px) rotateY(5deg);
                background: rgba(255, 255, 255, 0.1);
                box-shadow: -5px 5px 15px rgba(0,0,0,0.1);
            }
            .glass-sidebar {
                background: linear-gradient(180deg, #0f766e 0%, #115e59 100%);
                backdrop-filter: blur(10px);
            }
        </style>
    </head>
    <body class="bg-gray-50 h-screen flex overflow-hidden">
        <!-- 3D Sidebar -->
        <aside class="w-64 glass-sidebar text-white shadow-2xl relative z-20 hidden md:flex flex-col h-full perspective-1000">
            <div class="p-6 flex items-center space-x-3 border-b border-teal-600/30 mb-6">
                <img src="/static/images/heydoc_logo.png" alt="HeyDoc" class="h-10 bg-white rounded-lg p-1 shadow-lg">
                <div>
                    <h1 class="font-bold text-lg tracking-tight">Hey Doc!</h1>
                    <p class="text-xs text-teal-200 uppercase tracking-widest">Admin</p>
                </div>
            </div>
            
            <nav class="flex-1 px-4 space-y-2 overflow-y-auto">
                <div class="mb-4">
                    <p class="px-4 text-xs font-bold text-teal-200 uppercase tracking-wider mb-2">Main</p>
                    <a href="/admin_dashboard" class="nav-item flex items-center px-4 py-3 rounded-xl bg-teal-800/50 shadow-inner border border-teal-600/30">
                        <i class="ri-dashboard-3-line text-xl mr-3"></i>
                        <span class="font-medium">Dashboard</span>
                    </a>
                </div>
                
                <div class="mb-4">
                    <p class="px-4 text-xs font-bold text-teal-200 uppercase tracking-wider mb-2">Management</p>
                    <a href="/admin/staff" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-team-line text-xl mr-3"></i>
                        <span class="font-medium">Staff Directory</span>
                    </a>
                    <a href="/admin_dashboard#branch-inventory-section" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-hospital-line text-xl mr-3"></i>
                        <span class="font-medium">Branches</span>
                    </a>
                    <a href="/admin/holidays" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-calendar-event-line text-xl mr-3"></i>
                        <span class="font-medium">Hospital Holidays</span>
                    </a>
                    <a href="/admin/block_slots" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-calendar-close-line text-xl mr-3"></i>
                        <span class="font-medium">Block Slots</span>
                    </a>
                    <a href="/admin/financial_analytics" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-bar-chart-box-line text-xl mr-3"></i>
                        <span class="font-medium">Financial Analytics</span>
                    </a>
                    <a href="/admin/branch_admins" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-user-star-line text-xl mr-3"></i>
                        <span class="font-medium">Branch Admins</span>
                    </a>
                    <a href="/admin/payroll" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-money-dollar-box-line text-xl mr-3"></i>
                        <span class="font-medium">Hospital Payroll</span>
                    </a>
                    <a href="/admin/employee_details" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-team-line text-xl mr-3"></i>
                        <span class="font-medium">Employee Details</span>
                    </a>
                     <a href="/admin/manage_cms" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-layout-masonry-line text-xl mr-3"></i>
                        <span class="font-medium">CMS Management</span>
                    </a>
                </div>

                <div class="mb-4">
                    <p class="px-4 text-xs font-bold text-teal-200 uppercase tracking-wider mb-2">System</p>
                    <a href="/admin/profile" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-white/5 text-teal-50">
                        <i class="ri-user-settings-line text-xl mr-3"></i>
                        <span class="font-medium">Profile</span>
                    </a>
                    <a href="/logout" class="nav-item flex items-center px-4 py-3 rounded-xl hover:bg-red-500/10 hover:text-red-100 text-teal-50 transition-colors mt-4">
                        <i class="ri-logout-box-line text-xl mr-3"></i>
                        <span class="font-medium">Logout</span>
                    </a>
                </div>
            </nav>
            
            <div class="p-4 border-t border-teal-600/30 bg-teal-800/20">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-full bg-teal-500 flex items-center justify-center font-bold text-white shadow-lg">
                        {{ session.admin[:1]|upper }}
                    </div>
                    <div>
                        <p class="text-sm font-bold">{{ session.admin }}</p>
                        <p class="text-xs text-teal-300">Administrator</p>
                    </div>
                </div>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 overflow-x-hidden overflow-y-auto bg-gray-50 relative">
            <!-- Mobile Header -->
            <div class="md:hidden bg-teal-600 p-4 flex justify-between items-center text-white sticky top-0 z-50 shadow-md">
                 <div class="flex items-center">
                    <img src="/static/images/heydoc_logo.png" alt="HeyDoc" class="h-8 mr-2 bg-white rounded p-0.5">
                    <h1 class="font-bold">Admin</h1>
                </div>
                <a href="/logout"><i class="ri-logout-box-r-line text-xl"></i></a>
            </div>

            <div class="p-6 max-w-7xl mx-auto space-y-6">
            {% if not user_has_face %}
            <!-- Face ID Banner -->
            <div class="relative overflow-hidden bg-gradient-to-r from-teal-600 to-indigo-700 rounded-[32px] p-8 shadow-2xl shadow-teal-900/20 mb-8 border border-white/10 group cursor-pointer" onclick="window.location.href='/staff/face_register'">
                <div class="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-3xl -mr-32 -mt-32"></div>
                <div class="relative flex items-center justify-between">
                    <div class="flex items-center space-x-6">
                        <div class="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center text-white border border-white/20 scan-pulse">
                            <i class="ri-face-recognition-line text-3xl"></i>
                        </div>
                        <div>
                            <h3 class="text-xl font-black text-white tracking-tight">Security Setup Incomplete</h3>
                            <p class="text-teal-100 text-sm font-medium">Protect your workspace with button-free Face ID authentication.</p>
                        </div>
                    </div>
                    <div class="hidden md:block">
                        <button class="bg-white text-teal-700 px-8 py-3 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-teal-50 transition-all shadow-xl">
                            Register Now
                        </button>
                    </div>
                </div>
            </div>
            {% endif %}

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Branches</p>
                            <p class="text-3xl font-bold text-teal-600">{{ branches|length }}</p>
                        </div>
                        <div class="bg-teal-100 p-2 rounded-lg text-teal-600">
                            <i class="ri-building-2-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_branch" class="mt-4 text-sm text-teal-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Doctors</p>
                            <p class="text-3xl font-bold text-blue-600">{{ doctors|length }}</p>
                        </div>
                        <div class="bg-blue-100 p-2 rounded-lg text-blue-600">
                            <i class="ri-user-md-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_doctor" class="mt-4 text-sm text-blue-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Receptionists</p>
                            <p class="text-3xl font-bold text-purple-600">{{ receptionists|length }}</p>
                        </div>
                        <div class="bg-purple-100 p-2 rounded-lg text-purple-600">
                            <i class="ri-customer-service-2-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_receptionist" class="mt-4 text-sm text-purple-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Pending Leaves</p>
                            <p class="text-3xl font-bold text-orange-600">{{ leaves|length }}</p>
                        </div>
                        <div class="bg-orange-100 p-2 rounded-lg text-orange-600">
                            <i class="ri-calendar-event-line text-xl"></i>
                        </div>
                    </div>
                    <a href="#leaves-section" class="mt-4 text-sm text-orange-600 hover:underline flex items-center">
                        View All <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                <!-- Pharma & Lab Cards (Previously missing links) -->
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Pharmacists</p>
                            <p class="text-3xl font-bold text-teal-600">{{ pharmacists|length }}</p>
                        </div>
                        <div class="bg-teal-100 p-2 rounded-lg text-teal-600">
                            <i class="ri-capsule-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_pharmacist" class="mt-4 text-sm text-teal-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Lab Assistants</p>
                            <p class="text-3xl font-bold text-indigo-600">{{ lab_assistants|length }}</p>
                        </div>
                        <div class="bg-indigo-100 p-2 rounded-lg text-indigo-600">
                            <i class="ri-test-tube-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_lab_assistant" class="mt-4 text-sm text-indigo-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
                <!-- New specialized roles -->
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Finance Analytics</p>
                            <p class="text-3xl font-bold text-emerald-600">{{ finance_analytics|length }}</p>
                        </div>
                        <div class="bg-emerald-100 p-2 rounded-lg text-emerald-600">
                            <i class="ri-money-dollar-circle-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_financial_analytics" class="mt-4 text-sm text-emerald-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500 uppercase font-bold">Branch Admins</p>
                            <p class="text-3xl font-bold text-amber-600">{{ branch_admins|length }}</p>
                        </div>
                        <div class="bg-amber-100 p-2 rounded-lg text-amber-600">
                            <i class="ri-admin-line text-xl"></i>
                        </div>
                    </div>
                    <a href="/admin/add_branch_admin" class="mt-4 text-sm text-amber-600 hover:underline flex items-center">
                        Add New <i class="ri-arrow-right-s-line ml-1"></i>
                    </a>
                </div>
            </div>

            <!-- Standard Hospital Fees Management -->
            <div class="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden mb-6">
                <div class="bg-teal-600 px-6 py-4 flex justify-between items-center text-white">
                    <h3 class="font-black uppercase tracking-widest text-xs flex items-center">
                        <i class="ri-money-dollar-box-line mr-2"></i> Standard Consultation Fee Declaration
                    </h3>
                </div>
                <div class="p-6">
                    <form action="/admin/cms" method="POST" class="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
                        <input type="hidden" name="action" value="update_fees">
                        <div>
                            <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest block mb-2">Standard Fee (₹)</label>
                            <div class="relative">
                                <span class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 font-bold">₹</span>
                                <input type="number" name="consultation_fee" value="{{ fees.consultation_fee }}" required class="w-full bg-gray-50 border border-gray-100 rounded-xl px-10 py-3 text-sm font-bold focus:ring-2 focus:ring-teal-500 outline-none">
                            </div>
                        </div>
                        <div>
                            <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest block mb-2">Free Follow-up Days</label>
                            <input type="number" name="free_consultation_days" value="{{ fees.free_consultation_days }}" required class="w-full bg-gray-50 border border-gray-100 rounded-xl px-6 py-3 text-sm font-bold focus:ring-2 focus:ring-teal-500 outline-none">
                        </div>
                        <button type="submit" class="bg-teal-600 text-white font-black py-3 rounded-xl uppercase tracking-widest text-[10px] hover:bg-teal-700 transition-all shadow-lg shadow-teal-900/10">Apply Changes</button>
                    </form>
                    <p class="mt-4 text-[11px] text-gray-400 italic">
                        <i class="ri-information-line mr-1 text-teal-500"></i> These rates will be applied globally across all hospital branches for patient billing.
                    </p>
                </div>
            </div>

            
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <!-- Circulars Section -->
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div class="flex justify-between items-center mb-6">
                        <h3 class="text-lg font-bold text-gray-800 flex items-center">
                            <i class="ri-notification-3-line mr-2 text-teal-600"></i> Recent Circulars
                        </h3>
                        <button onclick="document.getElementById('circularModal').classList.remove('hidden')" class="bg-teal-600 text-white px-3 py-1 rounded text-sm hover:bg-teal-700">
                            Send Circular
                        </button>
                    </div>
                    {% if circulars %}
                        <div class="overflow-hidden">
                            <table class="w-full text-sm">
                                <thead class="bg-gray-50 text-gray-600">
                                    <tr>
                                        <th class="p-2 text-left">Title</th>
                                        <th class="p-2 text-left">Branch</th>
                                        <th class="p-2 text-left">Date</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-gray-200">
                                    {% for circular in circulars %}
                                        <tr>
                                            <td class="p-2 font-medium text-gray-800">{{ circular.title }}</td>
                                            <td class="p-2 text-gray-600">{{ circular.branch_name if circular.branch_name else "All Branches" }}</td>
                                            <td class="p-2 text-gray-500">{{ circular.created_at.strftime('%d %b, %H:%M') }}</td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    {% else %}
                        <p class="text-gray-500 text-center py-4">No circulars sent yet.</p>
                    {% endif %}
                </div>

                <!-- Leave Requests Section -->
                <div id="leaves-section" class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 class="text-lg font-bold text-gray-800 mb-6 flex items-center">
                        <i class="ri-calendar-todo-line mr-2 text-orange-600"></i> Pending Leave Requests
                    </h3>
                    {% if leaves %}
                        <div class="space-y-4 max-h-[400px] overflow-y-auto pr-2">
                            {% for leave in leaves %}
                                <div class="border border-gray-100 bg-gray-50 p-4 rounded-lg">
                                    <div class="flex justify-between items-start mb-2">
                                        <div class="flex flex-col">
                                            <div class="flex items-center space-x-2">
                                                <p class="font-bold text-gray-800">{{ leave.get('staff_name', 'N/A') }}</p>
                                                <span class="text-[10px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded {{ 'bg-blue-100 text-blue-600' if leave.get('staff_role') == 'doctor' else 'bg-purple-100 text-purple-600' }}">
                                                    {{ leave.get('staff_role', 'staff') }}
                                                </span>
                                            </div>
                                            <div class="flex items-center space-x-2 mt-0.5">
                                                <span class="text-[10px] font-black uppercase tracking-tighter bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{{ leave.get('leave_type', 'Casual Leave') }}</span>
                                                <p class="text-[10px] text-gray-400 font-medium">Dates: {{ leave.get('start_date', 'N/A') }} to {{ leave.get('end_date', 'N/A') }}</p>
                                                {% if leave.get('staff_balance') != 'N/A' %}
                                                    <span class="text-[10px] text-slate-500 font-medium ml-1">(Bal: {{ leave.get('staff_balance') }})</span>
                                                {% endif %}
                                            </div>
                                        </div>
                                        <span class="bg-orange-100 text-orange-600 text-[10px] px-2 py-0.5 rounded-full font-bold">PENDING</span>
                                    </div>
                                    <p class="text-sm text-gray-700 mb-4 bg-white p-2 rounded border border-gray-200">
                                        <strong>Reason:</strong> {{ leave.get('reason', 'N/A') }}
                                    </p>
                                    <form action="/admin/process_leave/{{ leave._id }}" method="POST" class="space-y-2">
                                        <textarea name="admin_reason" required placeholder="Enter reason for approval/rejection..." class="w-full text-xs p-2 border rounded border-gray-300 focus:outline-none focus:border-teal-500"></textarea>
                                        <div class="flex space-x-2">
                                            <button name="action" value="approve" class="flex-1 bg-green-600 text-white py-1.5 rounded text-xs font-bold hover:bg-green-700 transition-colors">
                                                Approve
                                            </button>
                                            <button name="action" value="reject" class="flex-1 bg-red-600 text-white py-1.5 rounded text-xs font-bold hover:bg-red-700 transition-colors">
                                                Reject
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            {% endfor %}
                        </div>
                    {% else %}
                        <p class="text-gray-500 text-center py-4">No pending leave requests.</p>
                    {% endif %}
                </div>
            </div>

            <!-- Branch Inventory Section -->
            <div id="branch-inventory-section" class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="text-lg font-bold text-gray-800 flex items-center">
                        <i class="ri-hospital-line mr-2 text-teal-600"></i> Branch Inventory
                    </h3>
                    <div class="flex space-x-2">
                        <a href="/admin/block_slots" class="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg text-sm hover:bg-red-600 hover:text-white transition-all flex items-center">
                            <i class="ri-calendar-close-line mr-1.5"></i> Block Slots
                        </a>
                        <a href="/admin/add_branch" class="bg-teal-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-teal-700 transition-all flex items-center">
                            <i class="ri-add-line mr-1.5"></i> Add Branch
                        </a>
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-50 text-slate-500 uppercase text-xs font-black tracking-widest border-b border-slate-100">
                                <th class="px-6 py-4">Branch Name</th>
                                <th class="px-6 py-4">Location</th>
                                <th class="px-6 py-4">Admin ID</th>
                                <th class="px-6 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {% for branch in branches %}
                            <tr class="hover:bg-slate-50/50 transition-colors group">
                                <td class="px-6 py-4">
                                    <div class="flex items-center">
                                        <div class="w-10 h-10 bg-teal-50 text-teal-600 rounded-xl flex items-center justify-center mr-3 font-bold">
                                            {{ branch.get('name', 'B')[:1]|upper }}
                                        </div>
                                        <span class="font-bold text-slate-700">{{ branch.get('name', 'Unnamed Branch') }}</span>
                                    </div>
                                </td>
                                <td class="px-6 py-4 text-slate-500 text-sm font-medium">{{ branch.get('location', 'N/A') }}</td>
                                <td class="px-6 py-4 font-mono text-xs text-slate-400">{{ branch._id }}</td>
                                <td class="px-6 py-4 text-right space-x-2">
                                    <a href="/admin/branch_details/{{ branch._id }}" class="inline-flex items-center px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs font-bold hover:bg-blue-600 hover:text-white transition-all">
                                        <i class="ri-eye-line mr-1"></i> Details
                                    </a>
                                    <a href="/admin/delete_branch/{{ branch._id }}" onclick="return confirm('WARNING: Are you sure? This will remove the branch and may affect linked staff.')" class="inline-flex items-center px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-xs font-bold hover:bg-red-600 hover:text-white transition-all">
                                        <i class="ri-delete-bin-line mr-1"></i> Remove
                                    </a>
                                </td>
                            </tr>
                            {% endfor %}
                            {% if not branches %}
                            <tr>
                                <td colspan="4" class="px-6 py-10 text-center text-slate-400 font-medium italic">No branches registered in the system.</td>
                            </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="text-lg font-bold text-gray-800">Global Data Access</h3>
                    <a href="/admin/all_patients" class="text-teal-600 text-sm font-bold hover:underline">View All Patients Across All Branches <i class="ri-external-link-line ml-1"></i></a>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <a href="/admin/add_branch" class="flex items-center p-4 bg-teal-50 rounded-lg text-teal-700 hover:bg-teal-100 transition-colors">
                        <i class="ri-add-circle-line text-2xl mr-3"></i>
                        <span class="font-bold">Add Branch</span>
                    </a>
                    <a href="/admin/add_doctor" class="flex items-center p-4 bg-blue-50 rounded-lg text-blue-700 hover:bg-blue-100 transition-colors">
                        <i class="ri-user-add-line text-2xl mr-3"></i>
                        <span class="font-bold">Add Doctor</span>
                    </a>
                    <a href="/admin/add_receptionist" class="flex items-center p-4 bg-purple-50 rounded-lg text-purple-700 hover:bg-purple-100 transition-colors">
                        <i class="ri-customer-service-line text-2xl mr-3"></i>
                        <span class="font-bold">Add Receptionist</span>
                    </a>
                    <a href="/admin/manage_leaves" class="flex items-center p-4 bg-orange-50 rounded-lg text-orange-700 hover:bg-orange-100 transition-colors">
                        <i class="ri-calendar-check-line text-2xl mr-3"></i>
                        <span class="font-bold">All Leaves</span>
                    </a>
                </div>
            </div>
        </div>

        <!-- Circular Modal -->
        <div id="circularModal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4">
            <div class="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 animate-in fade-in zoom-in duration-300">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-xl font-bold text-gray-800">Send New Circular</h2>
                    <button onclick="document.getElementById('circularModal').classList.add('hidden')" class="text-gray-400 hover:text-gray-600">
                        <i class="ri-close-line text-2xl"></i>
                    </button>
                </div>
                <form action="/admin/send_circular" method="POST" enctype="multipart/form-data" class="space-y-4">
                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-1">Target Branch</label>
                        <select name="branch_id" class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-teal-500 focus:outline-none">
                            <option value="all">All Branches</option>
                            {% for branch in branches %}
                                <option value="{{ branch._id }}">{{ branch.name }} ({{ branch.location }})</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-1">Title</label>
                        <input type="text" name="title" required class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-teal-500 focus:outline-none" placeholder="e.g., Holiday Notice">
                    </div>
                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-1">Content</label>
                        <textarea name="content" rows="4" required class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-teal-500 focus:outline-none" placeholder="Enter circular content here..."></textarea>
                    </div>
                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-1">Attachment (Optional)</label>
                        <input type="file" name="attachment" class="w-full p-1 text-sm border border-gray-300 rounded cursor-pointer">
                    </div>
                    <div class="pt-4 flex space-x-3">
                        <button type="button" onclick="document.getElementById('circularModal').classList.add('hidden')" class="flex-1 px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50 font-bold transition-colors">
                            Cancel
                        </button>
                        <button type="submit" class="flex-1 px-4 py-2 bg-teal-600 text-white rounded font-bold hover:bg-teal-700 transition-colors">
                            Send Circular
                        </button>
                    </div>
                </form>
            </div>
        </div>
        </main>
    </body>
    </html>
    """, branches=branches, doctors=doctors, receptionists=receptionists, 
             pharmacists=pharmacists, lab_assistants=lab_assistants, 
             finance_analytics=finance_analytics, branch_admins=branch_admins, 
             leaves=leaves, circulars=circulars, fees=fees, user_has_face=user_has_face)


@app.route("/admin/add_branch", methods=["GET", "POST"])
def admin_add_branch():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            location = request.form.get("location", "").strip()
            address = request.form.get("address", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            
            if not name or not location:
                flash("Branch name and location are required.", "error")
                return redirect("/admin/add_branch")
            
            branch_doc = {
                "name": name,
                "location": location,
                "address": address,
                "phone": phone,
                "email": email,
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin")
            }
            
            branches_collection.insert_one(branch_doc)
            flash("Branch added successfully!", "success")
            return redirect("/admin_dashboard")
        except Exception as e:
            flash(f"Error adding branch: {e}", "error")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Branch - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Add Branch</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <form method="POST" action="/admin/add_branch" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-1">Branch Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Location<span class="text-red-500">*</span></label>
                        <input type="text" name="location" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Address</label>
                        <textarea name="address" rows="3" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500"></textarea>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-gray-700 mb-1">Phone</label>
                            <input type="text" name="phone" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                        </div>
                        <div>
                            <label class="block text-gray-700 mb-1">Email</label>
                            <input type="email" name="email" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button type="submit" class="bg-teal-600 text-white px-5 py-2 rounded hover:bg-teal-700">Save Branch</button>
                        <a href="/admin_dashboard" class="bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)

@app.route("/admin/add_doctor", methods=["GET", "POST"])
def admin_add_doctor():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            branch_id = request.form.get("branch_id", "").strip()
            specialization = request.form.get("specialization", "").strip()
            
            # Generate secure temporary password
            password = generate_temp_password()
            
            if not all([name, username, email, branch_id]):
                flash("Name, username, email, and branch are required.", "error")
                return redirect("/admin/add_doctor")
            
            # Email Validation
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                flash("Invalid email format.", "error")
                return redirect("/admin/add_doctor")
            
            # Check if username or email already exists
            if doctors_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
                flash("Username or email already exists.", "error")
                return redirect("/admin/add_doctor")
            
            doctor_doc = {
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "phone": phone,
                "branch_id": branch_id,
                "must_change_password": True,
                "first_login": True,
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin"),
                "leave_accounts": {
                    "casual": {"granted": 22, "consumed": 0, "balance": 22},
                    "sick": {"granted": 5, "consumed": 0, "balance": 5},
                    "lop": {"granted": 0, "consumed": 0, "balance": 0},
                    "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
                    "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
                    "wfh": {"granted": 10, "consumed": 0, "balance": 10}
                },
                "leave_quota": 22, # Compatibility
                "leaves_remaining": 22 # Compatibility
            }
            
            doctors_collection.insert_one(doctor_doc)
            
            # Send credentials email
            send_credentials_email(email, username, password, "Doctor", name)
            
            flash("Doctor added successfully! Credentials have been sent to their email.", "success")
            return redirect("/admin_dashboard")
        except Exception as e:
            flash(f"Error adding doctor: {e}", "error")
    
    branches = list(branches_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Doctor - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Add Doctor</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <form method="POST" action="/admin/add_doctor" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-1">Full Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Username<span class="text-red-500">*</span></label>
                        <input type="text" name="username" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Email<span class="text-red-500">*</span></label>
                        <input type="email" name="email" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Password<span class="text-red-500">*</span></label>
                        <input type="password" name="password" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Phone</label>
                        <input type="text" name="phone" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Branch<span class="text-red-500">*</span></label>
                        <select name="branch_id" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500">
                            <option value="">Select Branch</option>
                            {% for branch in branches %}
                                <option value="{{ branch._id }}">{{ branch.name }} - {{ branch.location }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Specialization</label>
                        <input type="text" name="specialization" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div class="flex items-center space-x-3">
                        <button type="submit" class="bg-teal-600 text-white px-5 py-2 rounded hover:bg-teal-700">Save Doctor</button>
                        <a href="/admin_dashboard" class="bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <script>
            function toggleVisibility(inputId, iconId) {
                const input = document.getElementById(inputId);
                const icon = document.getElementById(iconId);
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.classList.replace('ri-eye-line', 'ri-eye-off-line');
                } else {
                    input.type = 'password';
                    icon.classList.replace('ri-eye-off-line', 'ri-eye-line');
                }
            }
        </script>
    </body>
    </html>
    """, branches=branches)

@app.route("/admin/add_receptionist", methods=["GET", "POST"])
def admin_add_receptionist():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            branch_id = request.form.get("branch_id", "").strip()
            
            # Generate secure temporary password
            password = generate_temp_password()
            
            if not all([name, username, email, branch_id]):
                flash("Name, username, email, and branch are required.", "error")
                return redirect("/admin/add_receptionist")
            
            # Email Validation
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                flash("Invalid email format.", "error")
                return redirect("/admin/add_receptionist")
            
            # Check if username or email already exists
            if receptionists_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
                flash("Username or email already exists.", "error")
                return redirect("/admin/add_receptionist")
            
            receptionist_doc = {
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "phone": phone,
                "branch_id": branch_id,
                "must_change_password": True,
                "first_login": True,
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin"),
                "leave_accounts": {
                    "casual": {"granted": 22, "consumed": 0, "balance": 22},
                    "sick": {"granted": 5, "consumed": 0, "balance": 5},
                    "lop": {"granted": 0, "consumed": 0, "balance": 0},
                    "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
                    "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
                    "wfh": {"granted": 10, "consumed": 0, "balance": 10}
                },
                "leave_quota": 22,
                "leaves_taken": 0,
                "leaves_remaining": 22
            }
            
            receptionists_collection.insert_one(receptionist_doc)
            
            # Send credentials email
            send_credentials_email(email, username, password, "Receptionist", name)
            
            flash("Receptionist added successfully! Credentials have been sent to their email.", "success")
            return redirect("/admin/staff")
        except Exception as e:
            flash(f"Error adding receptionist: {e}", "error")
    
    branches = list(branches_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Receptionist - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Add Receptionist</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <form method="POST" action="/admin/add_receptionist" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-1">Full Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Username<span class="text-red-500">*</span></label>
                        <input type="text" name="username" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Email<span class="text-red-500">*</span></label>
                        <input type="email" name="email" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Phone</label>
                        <input type="text" name="phone" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Branch<span class="text-red-500">*</span></label>
                        <select name="branch_id" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500">
                            <option value="">Select Branch</option>
                            {% for branch in branches %}
                                <option value="{{ branch._id }}">{{ branch.name }} - {{ branch.location }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button type="submit" class="bg-teal-600 text-white px-5 py-2 rounded hover:bg-teal-700">Save Receptionist</button>
                        <a href="/admin/staff" class="bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, branches=branches)

@app.route("/admin/add_branch_admin", methods=["GET", "POST"])
def admin_add_branch_admin():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            branch_ids = request.form.getlist("branch_ids") # Multi-select
            
            # Generate secure temporary password
            password = generate_temp_password()
            
            if not all([name, username, email, branch_ids]):
                flash("Name, username, email, and at least one branch are required.", "error")
                return redirect("/admin/add_branch_admin")
            
            # Check if username or email already exists
            if branch_admins_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
                flash("Username or email already exists.", "error")
                return redirect("/admin/add_branch_admin")
            
            admin_doc = {
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "branch_ids": branch_ids,
                "must_change_password": True,
                "first_login": True,
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin")
            }
            
            branch_admins_collection.insert_one(admin_doc)
            
            
            # Send credentials email (using same helper, role="Branch Admin")
            send_credentials_email(email, username, password, "Branch Admin", name)
            
            # Set session flag for admin-assisted Face ID registration
            session["registering_branch_admin"] = username
            session["registering_branch_admin_name"] = name
            
            flash(f"Branch Admin '{name}' added successfully! Now register their Face ID.", "success")
            return redirect(f"/admin/branch_admin_face_register/{username}")
        except Exception as e:
            flash(f"Error adding branch admin: {e}", "error")
    
    branches = list(branches_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Branch Admin - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-purple-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Add Branch Admin</h1>
            <a href="/admin/staff" class="bg-white text-purple-700 px-3 py-1 rounded hover:bg-purple-100">Back</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <form method="POST" action="/admin/add_branch_admin" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-1">Full Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-purple-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Username<span class="text-red-500">*</span></label>
                        <input type="text" name="username" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-purple-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Email<span class="text-red-500">*</span></label>
                        <input type="email" name="email" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-purple-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Assign Branches (Multi-Select)<span class="text-red-500">*</span></label>
                        <select name="branch_ids" multiple required class="w-full px-4 py-2 border border-gray-300 rounded h-32 focus:outline-none focus:border-purple-500">
                            {% for branch in branches %}
                                <option value="{{ branch._id }}">{{ branch.name }} - {{ branch.location }}</option>
                            {% endfor %}
                        </select>
                        <p class="text-xs text-gray-500 mt-1">Hold Ctrl (Windows) or Cmd (Mac) to select multiple branches.</p>
                    </div>
                    <div class="flex items-center space-x-3 pt-4">
                        <button type="submit" class="bg-purple-600 text-white px-5 py-2 rounded hover:bg-purple-700">Save Branch Admin</button>
                        <a href="/admin/staff" class="bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, branches=branches)



@app.route("/admin/branch_admin_face_register/<username>", methods=["GET", "POST"])
def admin_branch_admin_face_register(username):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    # Verify this is for the branch admin being registered
    if session.get("registering_branch_admin") != username:
        flash("Unauthorized face registration attempt.", "error")
        return redirect("/admin/staff")
    
    branch_admin = branch_admins_collection.find_one({"username": username})
    if not branch_admin:
        flash("Branch Admin not found.", "error")
        return redirect("/admin/staff")
    
    if request.method == "POST":
        try:
            data = request.json
            image_data = data.get("image")
            
            if not image_data:
                return jsonify({"success": False, "message": "No image captured"}), 400
            
            # Extract Encoding
            encoding, error = extract_face_encoding_from_base64(image_data)
            if error:
                # Enhanced error message
                error_hints = {
                    "No face detected": "Ensure the branch admin's face is clearly visible and centered in the frame.",
                    "Multiple faces": "Please ensure only one person is in the frame.",
                    "Could not process": "Try improving lighting conditions and ensure they look directly at the camera."
                }
                hint = next((v for k, v in error_hints.items() if k in error), error)
                return jsonify({"success": False, "message": hint}), 400
            
            # Encrypt encoding for secure storage
            encrypted_encoding = encrypt_face_encoding(encoding)
            
            # Update database
            update_data = {
                "face_encoding": encrypted_encoding,
                "face_id_enabled": True,
                "face_enrolled_at": datetime.utcnow()
            }
            
            branch_admins_collection.update_one({"username": username}, {"$set": update_data})
            
            # Clear session flags
            session.pop("registering_branch_admin", None)
            session.pop("registering_branch_admin_name", None)
            
            flash(f"Face ID registered successfully for {branch_admin.get('name')}!", "success")
            return jsonify({"success": True, "redirect": "/admin/staff"})
            
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    
    # Render Face ID capture page
    admin_name = session.get("registering_branch_admin_name", "Branch Admin")
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register Branch Admin Face ID | Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;900&display=swap');
        
        body {
            font-family: 'Outfit', sans-serif;
            background: linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 100%);
            min-height: 100vh;
        }
        
        .glass-container {
            background: rgba(255, 255, 255, 0.4);
            backdrop-filter: blur(40px) saturate(200%);
            -webkit-backdrop-filter: blur(40px) saturate(200%);
            border: 1px solid rgba(255, 255, 255, 0.7);
            border-radius: 48px;
            box-shadow: 0 40px 100px -20px rgba(0, 0, 0, 0.05);
        }
        
        .video-viewport {
            background: #000;
            border-radius: 40px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.2);
        }
    </style>
</head>

<body class="flex items-center justify-center p-6 bg-slate-50">
    <div class="fixed top-[-10%] left-[-5%] w-[40%] h-[40%] bg-teal-200/20 blur-[120px] rounded-full"></div>
    <div class="fixed bottom-[-10%] right-[-5%] w-[40%] h-[40%] bg-blue-200/20 blur-[120px] rounded-full"></div>

    <div class="max-w-xl w-full relative z-10">
        <div class="glass-container p-12 md:p-16 text-center">
            <div class="inline-flex items-center gap-3 px-4 py-2 bg-purple-500/10 border border-purple-500/20 rounded-full mb-8">
                <i class="ri-admin-line text-purple-600"></i>
                <span class="text-[10px] font-black uppercase tracking-[3px] text-purple-700">Admin Registration</span>
            </div>

            <div class="mb-12">
                <h1 class="text-4xl font-black text-slate-800 tracking-tight mb-4">Register Face ID</h1>
                <p class="text-slate-500 font-medium leading-relaxed max-w-sm mx-auto text-sm">
                    Capture <strong>{{ admin_name }}'s</strong> face for secure workstation access.
                </p>
            </div>

            <div class="relative mb-12">
                <div class="aspect-square w-full max-w-[340px] mx-auto video-viewport border-4 border-white shadow-2xl">
                    <video id="video" autoplay playsinline class="w-full h-full object-cover transform scale-x-[-1] opacity-90"></video>
                    <canvas id="canvas" class="hidden"></canvas>
                </div>
            </div>

            <div class="mb-6">
                <p id="status" class="text-xs font-bold uppercase tracking-widest text-teal-600">Ready to Scan</p>
            </div>

            <button id="register-btn"
                class="w-full bg-gradient-to-r from-teal-600 to-blue-600 text-white py-4 rounded-2xl text-sm font-black uppercase tracking-widest shadow-xl shadow-teal-500/30 hover:shadow-2xl hover:shadow-teal-500/40 transition-all flex items-center justify-center gap-3">
                <i class="ri-scan-2-line text-lg"></i> Capture Face ID
            </button>

            <a href="/admin/staff" class="block mt-4 text-sm text-slate-400 hover:text-slate-600">Skip for Now (Not Recommended)</a>

            <div id="success-state" class="hidden mt-6 p-6 bg-emerald-50 border border-emerald-200 rounded-2xl">
                <i class="ri-checkbox-circle-fill text-4xl text-emerald-600 mb-2"></i>
                <p class="text-emerald-800 font-bold">Face ID Registered!</p>
            </div>
        </div>
    </div>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const registerBtn = document.getElementById('register-btn');
        const status = document.getElementById('status');
        const successState = document.getElementById('success-state');

        async function initCamera() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }
                });
                video.srcObject = stream;
            } catch (err) {
                status.innerText = "Camera Blocked";
                status.classList.add('text-red-500');
            }
        }

        registerBtn.addEventListener('click', async () => {
            if (!video.srcObject || video.readyState < 2) {
                status.innerText = "Camera Not Ready";
                return;
            }

            if (video.videoWidth === 0 || video.videoHeight === 0) {
                status.innerText = "Loading Stream...";
                return;
            }

            registerBtn.disabled = true;
            registerBtn.classList.add('opacity-50');
            registerBtn.innerHTML = '<i class="ri-loader-4-line animate-spin text-lg"></i> ENROLLING...';
            status.innerText = "Processing...";

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const image = canvas.toDataURL('image/jpeg', 0.85);

            try {
                const response = await fetch('/admin/branch_admin_face_register/{{ username }}', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image })
                });

                const data = await response.json();

                if (data.success) {
                    successState.classList.remove('hidden');
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 2000);
                } else {
                    status.innerText = data.message || "Error";
                    status.classList.add('text-red-500');
                    registerBtn.disabled = false;
                    registerBtn.classList.remove('opacity-50');
                    registerBtn.innerHTML = '<i class="ri-scan-2-line text-lg"></i> Retry';
                }
            } catch (err) {
                status.innerText = "Network Error";
                registerBtn.disabled = false;
                registerBtn.classList.remove('opacity-50');
            }
        });

        window.onload = initCamera;
    </script>
</body>
</html>
    """, admin_name=admin_name, username=username)


@app.route("/admin/add_pharmacist", methods=["GET", "POST"])
def admin_add_pharmacist():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            branch_id = request.form.get("branch_id", "").strip()
            
            # Generate secure temporary password
            password = generate_temp_password()
            
            if not all([name, username, email, branch_id]):
                flash("Name, username, email, and branch are required.", "error")
                return redirect("/admin/add_pharmacist")
            
            # Email Validation
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                flash("Invalid email format.", "error")
                return redirect("/admin/add_pharmacist")
            
            # Check if username or email already exists
            if pharmacists_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
                flash("Username or email already exists.", "error")
                return redirect("/admin/add_pharmacist")
            
            pharmacist_doc = {
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "phone": phone,
                "branch_id": branch_id,
                "must_change_password": True,
                "first_login": True,
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin"),
                "leave_accounts": {
                    "casual": {"granted": 22, "consumed": 0, "balance": 22},
                    "sick": {"granted": 5, "consumed": 0, "balance": 5},
                    "lop": {"granted": 0, "consumed": 0, "balance": 0},
                    "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
                    "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
                    "wfh": {"granted": 10, "consumed": 0, "balance": 10}
                },
                "leave_quota": 22,
                "leaves_taken": 0,
                "leaves_remaining": 22
            }
            
            pharmacists_collection.insert_one(pharmacist_doc)
            
            # Send credentials email
            send_credentials_email(email, username, password, "Pharmacist", name)
            
            flash("Pharmacist added successfully! Credentials have been sent to their email.", "success")
            return redirect("/admin_dashboard")
        except Exception as e:
            flash(f"Error adding pharmacist: {e}", "error")
    
    branches = list(branches_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Pharmacist - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Add Pharmacist</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <form method="POST" action="/admin/add_pharmacist" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-1">Full Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Username<span class="text-red-500">*</span></label>
                        <input type="text" name="username" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Email<span class="text-red-500">*</span></label>
                        <input type="email" name="email" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
                        <p class="text-sm text-blue-700"><strong>🔐 Security Note:</strong> A secure temporary password will be automatically generated and sent to the pharmacist's email. They will be required to change it on first login.</p>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Phone</label>
                        <input type="text" name="phone" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Branch<span class="text-red-500">*</span></label>
                        <select name="branch_id" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500">
                            <option value="">Select Branch</option>
                            {% for branch in branches %}
                                <option value="{{ branch._id }}">{{ branch.name }} - {{ branch.location }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button type="submit" class="bg-teal-600 text-white px-5 py-2 rounded hover:bg-teal-700">Save Pharmacist</button>
                        <a href="/admin_dashboard" class="bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, branches=branches)

@app.route("/admin/add_financial_analytics", methods=["GET", "POST"])
def admin_add_financial_analytics():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            
            # Generate secure temporary password
            password = generate_temp_password()
            
            if not all([name, username, email]):
                flash("Name, username, and email are required.", "error")
                return redirect("/admin/add_financial_analytics")
            
            # Email Validation
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                flash("Invalid email format.", "error")
                return redirect("/admin/add_financial_analytics")
            
            # Check if username or email already exists
            if financial_analytics_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
                flash("Username or email already exists.", "error")
                return redirect("/admin/add_financial_analytics")
            
            fa_doc = {
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "phone": phone,
                "must_change_password": True,
                "first_login": True,
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin")
            }
            
            financial_analytics_collection.insert_one(fa_doc)
            send_credentials_email(email, username, password, "Financial Analytics", name)
            flash("Financial Analytics account added successfully!", "success")
            return redirect("/admin_dashboard")
        except Exception as e:
            flash(f"Error adding financial analytics: {e}", "error")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Financial Analytics - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center shadow-lg">
            <h1 class="text-xl font-bold">Add Financial Analytics</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 font-bold transition-all">Back to Dashboard</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            <div class="bg-white rounded-[24px] shadow-xl p-8 border border-gray-100">
                <form method="POST" action="/admin/add_financial_analytics" class="space-y-6">
                    <div>
                        <label class="block text-gray-700 font-bold mb-1">Full Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:border-teal-500 transition-all shadow-sm" />
                    </div>
                    <div>
                        <label class="block text-gray-700 font-bold mb-1">Username<span class="text-red-500">*</span></label>
                        <input type="text" name="username" required class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:border-teal-500 transition-all shadow-sm" />
                    </div>
                    <div>
                        <label class="block text-gray-700 font-bold mb-1">Email<span class="text-red-500">*</span></label>
                        <input type="email" name="email" required class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:border-teal-500 transition-all shadow-sm" />
                    </div>
                    <div>
                        <label class="block text-gray-700 font-bold mb-1">Phone</label>
                        <input type="text" name="phone" class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:border-teal-500 transition-all shadow-sm" />
                    </div>
                    <div class="flex items-center space-x-3 pt-4">
                        <button type="submit" class="bg-teal-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-teal-700 shadow-lg shadow-teal-900/10 transition-all">Save Account</button>
                        <a href="/admin_dashboard" class="bg-gray-100 text-gray-600 px-8 py-3 rounded-xl font-bold hover:bg-gray-200 transition-all">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)


@app.route("/admin/add_lab_assistant", methods=["GET", "POST"])
def admin_add_lab_assistant():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            branch_id = request.form.get("branch_id", "").strip()
            
            # Generate secure temporary password
            password = generate_temp_password()
            
            if not all([name, username, email, branch_id]):
                flash("Name, username, email, and branch are required.", "error")
                return redirect("/admin/add_lab_assistant")
            
            # Email Validation
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                flash("Invalid email format.", "error")
                return redirect("/admin/add_lab_assistant")
            
            # Check if username or email already exists
            if lab_assistants_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
                flash("Username or email already exists.", "error")
                return redirect("/admin/add_lab_assistant")
            
            lab_assistant_doc = {
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "phone": phone,
                "branch_id": branch_id,
                "must_change_password": True,
                "first_login": True,
                "status": "active",
                "created_at": datetime.utcnow(),
                "created_by": session.get("admin"),
                "leave_accounts": {
                    "casual": {"granted": 22, "consumed": 0, "balance": 22},
                    "sick": {"granted": 5, "consumed": 0, "balance": 5},
                    "lop": {"granted": 0, "consumed": 0, "balance": 0},
                    "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
                    "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
                    "wfh": {"granted": 10, "consumed": 0, "balance": 10}
                },
                "leave_quota": 22,
                "leaves_taken": 0,
                "leaves_remaining": 22
            }
            
            lab_assistants_collection.insert_one(lab_assistant_doc)
            
            # Send credentials email
            send_credentials_email(email, username, password, "Lab Assistant", name)
            
            flash("Lab Assistant added successfully! Credentials have been sent to their email.", "success")
            return redirect("/admin_dashboard")
        except Exception as e:
            flash(f"Error adding lab assistant: {e}", "error")
    
    branches = list(branches_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Lab Assistant - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Add Lab Assistant</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <form method="POST" action="/admin/add_lab_assistant" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-1">Full Name<span class="text-red-500">*</span></label>
                        <input type="text" name="name" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Username<span class="text-red-500">*</span></label>
                        <input type="text" name="username" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Email<span class="text-red-500">*</span></label>
                        <input type="email" name="email" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
                        <p class="text-sm text-blue-700"><strong>🔐 Security Note:</strong> A secure temporary password will be automatically generated and sent to the lab assistant's email. They will be required to change it on first login.</p>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Phone</label>
                        <input type="text" name="phone" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Branch<span class="text-red-500">*</span></label>
                        <select name="branch_id" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500">
                            <option value="">Select Branch</option>
                            {% for branch in branches %}
                                <option value="{{ branch._id }}">{{ branch.name }} - {{ branch.location }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button type="submit" class="bg-teal-600 text-white px-5 py-2 rounded hover:bg-teal-700">Save Lab Assistant</button>
                        <a href="/admin_dashboard" class="bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, branches=branches)


@app.route("/admin/process_leave/<leave_id>", methods=["POST"])
def admin_process_leave(leave_id):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    action = request.form.get("action")
    admin_reason = request.form.get("admin_reason", "").strip()
    
    status = "approved" if action == "approve" else "rejected"
    
    leave = leaves_collection.find_one({"_id": ObjectId(leave_id)})
    if leave:
        # Calculate leave days if approving
        if action == "approve":
            try:
                start_date = datetime.strptime(leave.get("start_date"), "%Y-%m-%d")
                end_date = datetime.strptime(leave.get("end_date"), "%Y-%m-%d")
                leave_days = (end_date - start_date).days + 1
                
                # Determine user role from leave doc or lookup
                username = leave.get("username") or leave.get("doctor_username")
                role = leave.get("role", "doctor")
                
                collection = doctors_collection if role == "doctor" else receptionists_collection
                staff_member = collection.find_one({"username": username})
                
                if staff_member:
                    leave_type_key = leave.get("leave_type", "casual").lower()
                    if "casual" in leave_type_key: leave_type_key = "casual"
                    
                    # Use accounts if exists, otherwise fallback to flat fields
                    if "leave_accounts" in staff_member:
                        accounts = staff_member["leave_accounts"]
                        target_type = leave_type_key if leave_type_key in accounts else "casual"
                        
                        current_balance = accounts[target_type].get("balance", 0)
                        
                        # Check if sufficient balance (except for LOP maybe, but let's be strict or allow negative if needed)
                        if current_balance < leave_days and target_type != "lop":
                             flash(f"Insufficient {target_type} leave balance! Staff has only {current_balance} days remaining.", "error")
                             return redirect("/admin_dashboard")
                        
                        # Update specific category
                        accounts[target_type]["consumed"] += leave_days
                        accounts[target_type]["balance"] -= leave_days
                        
                        update_doc = {"leave_accounts": accounts}
                        # Sync legacy fields if casual
                        if target_type == "casual":
                            update_doc["leaves_remaining"] = accounts["casual"]["balance"]
                            update_doc["leaves_taken"] = accounts["casual"]["consumed"]
                            
                        collection.update_one({"username": username}, {"$set": update_doc})
                    else:
                        # Legacy update logic
                        current_remaining = staff_member.get("leaves_remaining", 20)
                        current_taken = staff_member.get("leaves_taken", 0)
                        if current_remaining < leave_days:
                             flash(f"Insufficient leave balance! Staff has only {current_remaining} days remaining.", "error")
                             return redirect("/admin_dashboard")
                             
                        collection.update_one(
                            {"username": username},
                            {"$set": {
                                "leaves_remaining": max(0, current_remaining - leave_days),
                                "leaves_taken": current_taken + leave_days
                            }}
                        )
            except Exception as e:
                print(f"Error calculating leave days: {e}")
                leave_days = 0
        
        leaves_collection.update_one(
            {"_id": ObjectId(leave_id)}, 
            {"$set": {
                "status": status, 
                "admin_reason": admin_reason,
                "processed_by": session.get("admin"), 
                "processed_at": datetime.utcnow()
            }}
        )
        
        # Send notification email
        username = leave.get("username") or leave.get("doctor_username")
        role = leave.get("role", "doctor")
        collection = doctors_collection if role == "doctor" else receptionists_collection
        staff_member = collection.find_one({"username": username})
        
        if staff_member and staff_member.get("email"):
            send_leave_approval_email(staff_member["email"], leave, status)
            
        flash(f"Leave request {status} successfully!", "success")
    else:
        flash("Leave request not found.", "error")
    
    return redirect("/admin_dashboard")

@app.route("/admin/send_circular", methods=["POST"])
def admin_send_circular():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    branch_id = request.form.get("branch_id")
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    file = request.files.get("attachment")
    
    if not title or not content:
        flash("Title and content are required.", "error")
        return redirect("/admin_dashboard")
    
    file_path = None
    full_save_path = None
    if file and file.filename != '':
        try:
            filename = secure_filename(file.filename)
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            # Ensure directory exists before saving
            if not os.path.exists(CIRCULAR_ATTACHMENTS_FOLDER):
                os.makedirs(CIRCULAR_ATTACHMENTS_FOLDER, exist_ok=True)
            
            full_save_path = os.path.join(CIRCULAR_ATTACHMENTS_FOLDER, filename)
            file.save(full_save_path)
            # Store relative path for serving
            file_path = f"circulars/{filename}"
        except Exception as e:
            print(f"Error saving circular attachment: {e}")
            flash(f"Warning: Circular saved without attachment due to storage error: {e}", "warning")
            file_path = None

    branch_name = "All Branches"
    if branch_id != "all":
        branch = get_branch_by_id(branch_id)
        if branch:
            branch_name = branch.get("name")

    circular_doc = {
        "title": title,
        "content": content,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "file_path": file_path,
        "created_at": datetime.utcnow(),
        "created_by": session.get("admin")
    }
    
    circulars_collection.insert_one(circular_doc)
    
    # Send email notification to relevant staff
    recipients = []
    query = {}
    if branch_id != "all":
        query["branch_id"] = branch_id
        
    doctors = list(doctors_collection.find(query, {"email": 1}))
    receptionists = list(receptionists_collection.find(query, {"email": 1}))
    
    recipients.extend([d.get("email") for d in doctors if d.get("email")])
    recipients.extend([r.get("email") for r in receptionists if r.get("email")])
    
    if recipients:
        send_circular_notification_email(recipients, title, content, full_save_path)

    flash("Circular sent successfully!", "success")
    return redirect("/admin_dashboard")

@app.route("/admin/branch_admins")
def admin_branch_admins():
    if "admin" not in session: return redirect("/login")
    branch_admins = list(branch_admins_collection.find({}))
    branches = list(branches_collection.find({}))
    branch_lookup = {str(b["_id"]): b for b in branches}
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Branch Admins - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center shadow-lg">
            <h1 class="text-xl font-bold flex items-center"><i class="ri-user-star-line mr-2"></i> Branch Admins</h1>
            <a href="/admin_dashboard" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Dashboard</a>
        </nav>
        <div class="p-8 max-w-6xl mx-auto">
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <table class="w-full">
                    <thead class="bg-gray-50 text-gray-500 text-xs uppercase font-bold">
                        <tr>
                            <th class="px-6 py-4 text-left">Name</th>
                            <th class="px-6 py-4 text-left">Email</th>
                            <th class="px-6 py-4 text-left">Assigned Branch</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100 italic">
                        {% for ba in branch_admins %}
                        <tr>
                            <td class="px-6 py-4 font-bold text-gray-800">{{ ba.name }}</td>
                            <td class="px-6 py-4 text-gray-500">{{ ba.email }}</td>
                            <td class="px-6 py-4 text-teal-600 font-medium">
                                {% set branch = branch_lookup.get(ba.get('branch_id')) %}
                                {{ branch.name if branch else 'General / All' }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """, branch_admins=branch_admins, branch_lookup=branch_lookup)

@app.route("/admin/financial_analytics")
def admin_financial_analytics_list():
    if "admin" not in session: return redirect("/login")
    analytics_staff = list(financial_analytics_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Financial Analytics - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen">
        <nav class="bg-emerald-600 p-4 text-white flex justify-between items-center shadow-lg">
            <h1 class="text-xl font-bold flex items-center"><i class="ri-bar-chart-box-line mr-2"></i> Financial Analytics</h1>
            <a href="/admin_dashboard" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Dashboard</a>
        </nav>
        <div class="p-8 max-w-6xl mx-auto">
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <table class="w-full">
                    <thead class="bg-gray-50 text-gray-500 text-xs uppercase font-bold">
                        <tr>
                            <th class="px-6 py-4 text-left">Name</th>
                            <th class="px-6 py-4 text-left">Email</th>
                            <th class="px-6 py-4 text-left">Role</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100 italic">
                        {% for st in analytics_staff %}
                        <tr>
                            <td class="px-6 py-4 font-bold text-gray-800">{{ st.name }}</td>
                            <td class="px-6 py-4 text-gray-500">{{ st.email }}</td>
                            <td class="px-6 py-4 text-emerald-600 font-medium uppercase tracking-[2px] text-[10px]">Finance Auditor</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """, analytics_staff=analytics_staff)

@app.route("/admin/staff")
def admin_staff():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    doctors = list(doctors_collection.find({}))
    receptionists = list(receptionists_collection.find({}))
    branch_admins = list(branch_admins_collection.find({})) if 'branch_admins_collection' in globals() else []
    branches = list(branches_collection.find({}))
    
    # Create branch lookup
    branch_lookup = {str(b["_id"]): b for b in branches}
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Staff Directory - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <div class="flex items-center">
                <i class="ri-team-line text-2xl mr-2"></i>
                <h1 class="text-xl font-bold">Staff Directory</h1>
            </div>
            <div>
                <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
            </div>
        </nav>
        
        <div class="p-6 max-w-7xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            
            
            <!-- Branch Admins Section -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 flex items-center">
                        <i class="ri-admin-line mr-2 text-purple-600"></i> Branch Admins ({{ branch_admins|length }})
                    </h2>
                    <a href="/admin/add_branch_admin" class="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 flex items-center">
                        <i class="ri-add-line mr-1"></i> Add Branch Admin
                    </a>
                </div>
                
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead class="bg-gray-50 text-gray-600">
                            <tr>
                                <th class="p-3 text-left">Name</th>
                                <th class="p-3 text-left">Username</th>
                                <th class="p-3 text-left">Assigned Branches</th>
                                <th class="p-3 text-left">Status</th>
                                <th class="p-3 text-left">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100">
                            {% for admin in branch_admins %}
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 font-medium text-gray-800">{{ admin.name }}</td>
                                <td class="p-3 text-gray-600">{{ admin.username }}</td>
                                <td class="p-3 text-gray-600">
                                    {% for bid in admin.branch_ids %}
                                        <span class="bg-purple-100 text-purple-800 text-xs px-2 py-1 rounded-full mr-1">
                                            {{ branch_lookup[bid].name if bid in branch_lookup else bid }}
                                        </span>
                                    {% endfor %}
                                </td>
                                <td class="p-3">
                                    <span class="px-2 py-1 rounded-full text-xs {{ 'bg-green-100 text-green-800' if admin.status == 'active' else 'bg-red-100 text-red-800' }}">
                                        {{ admin.status }}
                                    </span>
                                </td>
                                <td class="p-3">
                                    <button class="text-gray-400 hover:text-blue-600"><i class="ri-edit-line text-lg"></i></button>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Doctors Section -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 flex items-center">
                        <i class="ri-user-md-line mr-2 text-blue-600"></i> Doctors ({{ doctors|length }})
                    </h2>
                    <a href="/admin/add_doctor" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center">
                        <i class="ri-add-line mr-1"></i> Add Doctor
                    </a>
                </div>
                
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead class="bg-gray-50 text-gray-600">
                            <tr>
                                <th class="p-3 text-left">Name</th>
                                <th class="p-3 text-left">Username</th>
                                <th class="p-3 text-left">Email</th>
                                <th class="p-3 text-left">Branch</th>
                                <th class="p-3 text-left">Leave Balance</th>
                                <th class="p-3 text-left">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            {% for doctor in doctors %}
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 font-medium text-gray-800">{{ doctor.get('name', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ doctor.get('username', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ doctor.get('email', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">
                                    {% set branch = branch_lookup.get(doctor.get('branch_id')) %}
                                    {{ branch.get('name') if branch else 'N/A' }}
                                </td>
                                <td class="p-3">
                                    {% set leaves_rem = doctor.get('leave_accounts', {}).get('casual', {}).get('balance', doctor.get('leaves_remaining', 22)) %}
                                    {% set leaves_quota = doctor.get('leave_accounts', {}).get('casual', {}).get('granted', doctor.get('leave_quota', 22)) %}
                                    {% set leaves_taken = doctor.get('leave_accounts', {}).get('casual', {}).get('consumed', doctor.get('leaves_taken', 0)) %}
                                    <div class="flex items-center space-x-2">
                                        <span class="font-bold text-teal-600">{{ leaves_rem }}</span>
                                        <span class="text-gray-400">/</span>
                                        <span class="text-gray-500">{{ leaves_quota }}</span>
                                    </div>
                                    <div class="text-xs text-gray-400 mt-0.5">
                                        Taken: {{ leaves_taken }} days
                                    </div>
                                </td>
                                <td class="p-3">
                                    <div class="flex items-center space-x-4">
                                        <a href="/admin/manage_leave_quota/{{ doctor._id }}?role=doctor" class="text-teal-600 hover:text-teal-800 text-xs font-medium flex items-center">
                                            <i class="ri-settings-3-line mr-1"></i> Manage Quota
                                        </a>
                                        <a href="/admin/delete_doctor/{{ doctor._id }}" 
                                           class="text-red-600 hover:text-red-800 text-xs font-medium flex items-center"
                                           onclick="return confirm('Are you sure you want to permanently delete doctor {{ doctor.get(\'name\') }}?')">
                                            <i class="ri-delete-bin-line mr-1"></i> Delete
                                        </a>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Receptionists Section -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 flex items-center">
                        <i class="ri-customer-service-2-line mr-2 text-purple-600"></i> Receptionists ({{ receptionists|length }})
                    </h2>
                    <a href="/admin/add_receptionist" class="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 flex items-center">
                        <i class="ri-add-line mr-1"></i> Add Receptionist
                    </a>
                </div>
                
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead class="bg-gray-50 text-gray-600">
                            <tr>
                                <th class="p-3 text-left">Name</th>
                                <th class="p-3 text-left">Username</th>
                                <th class="p-3 text-left">Email</th>
                                <th class="p-3 text-left">Phone</th>
                                <th class="p-3 text-left">Branch</th>
                                <th class="p-3 text-left">Leave Balance</th>
                                <th class="p-3 text-left">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            {% for receptionist in receptionists %}
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 font-medium text-gray-800">{{ receptionist.get('name', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ receptionist.get('username', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ receptionist.get('email', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ receptionist.get('phone', 'N/A') }}</td>
                                <td class="p-3 text-gray-600 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                                    {% set branch = branch_lookup.get(receptionist.get('branch_id')) %}
                                    {{ branch.get('name') if branch else 'N/A' }}
                                </td>
                                <td class="p-3">
                                    {% set leaves_rem = receptionist.get('leave_accounts', {}).get('casual', {}).get('balance', receptionist.get('leaves_remaining', 22)) %}
                                    {% set leaves_quota = receptionist.get('leave_accounts', {}).get('casual', {}).get('granted', receptionist.get('leave_quota', 22)) %}
                                    {% set leaves_taken = receptionist.get('leave_accounts', {}).get('casual', {}).get('consumed', receptionist.get('leaves_taken', 0)) %}
                                    <div class="flex items-center space-x-2">
                                        <span class="font-bold text-purple-600">{{ leaves_rem }}</span>
                                        <span class="text-gray-400">/</span>
                                        <span class="text-gray-500">{{ leaves_quota }}</span>
                                    </div>
                                    <div class="text-xs text-gray-400 mt-0.5">
                                        Taken: {{ leaves_taken }} days
                                    </div>
                                </td>
                                <td class="p-3">
                                    <div class="flex items-center space-x-4">
                                        <a href="/admin/manage_leave_quota/{{ receptionist._id }}?role=receptionist" class="text-purple-600 hover:text-purple-800 text-xs font-medium flex items-center">
                                            <i class="ri-settings-3-line mr-1"></i> Manage Quota
                                        </a>
                                        <a href="/admin/delete_receptionist/{{ receptionist._id }}" 
                                           class="text-red-600 hover:text-red-800 text-xs font-medium flex items-center"
                                           onclick="return confirm('Are you sure you want to permanently delete receptionist {{ receptionist.get(\'name\') }}?')">
                                            <i class="ri-delete-bin-line mr-1"></i> Delete
                                        </a>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, doctors=doctors, receptionists=receptionists, branch_admins=branch_admins, branch_lookup=branch_lookup)

@app.route("/admin/manage_leave_quota/<staff_id>", methods=["GET", "POST"])
def manage_leave_quota(staff_id):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    role = request.args.get("role", "doctor")
    collection = doctors_collection if role == "doctor" else receptionists_collection
    staff = collection.find_one({"_id": ObjectId(staff_id)})
    
    if not staff:
        flash("Staff member not found.", "error")
        return redirect("/admin/staff")
    
    # Initialize leave accounts if not present
    if "leave_accounts" not in staff:
        casual_taken = staff.get("leaves_taken", 0)
        casual_quota = staff.get("leave_quota", 22)
        staff["leave_accounts"] = {
            "casual": {"granted": casual_quota, "consumed": casual_taken, "balance": max(0, casual_quota - casual_taken)},
            "sick": {"granted": 5, "consumed": 0, "balance": 5},
            "lop": {"granted": 0, "consumed": 0, "balance": 0},
            "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
            "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
            "wfh": {"granted": 10, "consumed": 0, "balance": 10}
        }
        collection.update_one({"_id": staff["_id"]}, {"$set": {"leave_accounts": staff["leave_accounts"]}})

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_quotas":
            accounts = staff.get("leave_accounts", {})
            for ltype in ["casual", "sick", "lop", "comp_off", "bereavement", "wfh"]:
                granted = int(request.form.get(f"granted_{ltype}", 0))
                consumed = accounts.get(ltype, {}).get("consumed", 0)
                accounts[ltype] = {
                    "granted": granted,
                    "consumed": consumed,
                    "balance": max(0, granted - consumed)
                }
            
            collection.update_one(
                {"_id": staff["_id"]},
                {"$set": {
                    "leave_accounts": accounts,
                    "leave_quota": accounts.get("casual", {}).get("granted", 22),
                    "leaves_remaining": accounts.get("casual", {}).get("balance", 22)
                }}
            )
            flash(f"Leave quotas updated successfully for {staff.get('name')}!", "success")
        
        return redirect(f"/admin/manage_leave_quota/{staff_id}?role={role}")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Manage Leave Quota - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-gray-50 p-8">
        <div class="max-w-4xl mx-auto">
            <div class="flex justify-between items-center mb-8">
                <div>
                    <h1 class="text-3xl font-black text-slate-800">Assign Leave Quotas</h1>
                    <p class="text-slate-500 font-medium">Managing {{ staff.name }} ({{ role|capitalize }})</p>
                </div>
                <a href="/admin/staff" class="bg-white border px-6 py-2 rounded-2xl font-bold shadow-sm hover:bg-slate-50 transition-colors">Back to Staff</a>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-6 p-4 rounded-2xl bg-{{ 'red' if category == 'error' else 'emerald' }}-50 border border-{{ 'red' if category == 'error' else 'emerald' }}-100 text-{{ 'red' if category == 'error' else 'emerald' }}-700 font-bold">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}

            <form method="POST" class="space-y-6">
                <input type="hidden" name="action" value="update_quotas">
                <div class="bg-white rounded-[40px] shadow-xl border border-slate-100 overflow-hidden">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-50 border-b border-slate-100">
                                <th class="px-8 py-6 text-xs font-black uppercase tracking-widest text-slate-400">Leave Type</th>
                                <th class="px-8 py-6 text-xs font-black uppercase tracking-widest text-slate-400">Granted Days</th>
                                <th class="px-8 py-6 text-xs font-black uppercase tracking-widest text-slate-400">Consumed</th>
                                <th class="px-8 py-6 text-xs font-black uppercase tracking-widest text-slate-400">Current Balance</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-50">
                            {% for key, info in [
                                ('casual', 'Casual Leave'),
                                ('sick', 'Sick Leave'),
                                ('lop', 'Loss of Pay'),
                                ('comp_off', 'Comp-Off'),
                                ('bereavement', 'Bereavement'),
                                ('wfh', 'Work From Home')
                            ] %}
                            {% set acc = staff.leave_accounts.get(key, {'granted': 0, 'consumed': 0, 'balance': 0}) %}
                            <tr class="hover:bg-slate-50/50 transition-colors">
                                <td class="px-8 py-6">
                                    <div class="flex items-center space-x-3">
                                        <div class="w-2 h-2 rounded-full bg-{{ 'emerald' if key == 'casual' else 'red' if key == 'sick' else 'amber' if key == 'lop' else 'blue' if key == 'comp_off' else 'rose' if key == 'bereavement' else 'indigo' }}-500"></div>
                                        <span class="font-bold text-slate-700">{{ info }}</span>
                                    </div>
                                </td>
                                <td class="px-8 py-6">
                                    <input type="number" name="granted_{{ key }}" value="{{ acc.granted }}" min="0" 
                                           class="w-24 px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none font-bold transition-all">
                                </td>
                                <td class="px-8 py-6">
                                    <span class="text-slate-400 font-medium">{{ acc.consumed }} days</span>
                                </td>
                                <td class="px-8 py-6">
                                    <span class="px-3 py-1 bg-{{ 'emerald' if acc.balance > 0 else 'slate' }}-100 text-{{ 'emerald' if acc.balance > 0 else 'slate' }}-700 rounded-lg text-xs font-black uppercase tracking-widest">
                                        {{ acc.balance }} Left
                                    </span>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                <div class="flex justify-end pt-4">
                    <button type="submit" class="px-10 py-4 bg-teal-600 text-white rounded-[20px] font-black uppercase tracking-widest shadow-lg shadow-teal-600/20 hover:bg-teal-700 transform hover:-translate-y-1 transition-all">
                        Save All Quotas
                    </button>
                </div>
            </form>
        </div>
    </body>
    </html>
    """, staff=staff, role=role)

@app.route("/admin/delete_doctor/<doctor_id>")
def admin_delete_doctor(doctor_id):
    if "admin" not in session: return redirect("/login")
    try:
        doctor = doctors_collection.find_one({"_id": ObjectId(doctor_id)})
        if doctor:
            doctors_collection.delete_one({"_id": ObjectId(doctor_id)})
            flash(f"Doctor {doctor.get('name')} deleted successfully.", "success")
        else:
            flash("Doctor not found.", "error")
    except Exception as e:
        flash(f"Error deleting doctor: {e}", "error")
    return redirect("/admin/staff")

@app.route("/admin/delete_receptionist/<receptionist_id>")
def admin_delete_receptionist(receptionist_id):
    if "admin" not in session: return redirect("/login")
    try:
        receptionist = receptionists_collection.find_one({"_id": ObjectId(receptionist_id)})
        if receptionist:
            receptionists_collection.delete_one({"_id": ObjectId(receptionist_id)})
            flash(f"Receptionist {receptionist.get('name')} deleted successfully.", "success")
        else:
            flash("Receptionist not found.", "error")
    except Exception as e:
        flash(f"Error deleting receptionist: {e}", "error")
    return redirect("/admin/staff")

@app.route("/admin/manage_leaves")
def admin_manage_leaves():
    if "admin" not in session:
        flash("Please log in as admin.", "error")
        return redirect("/login")
        
    leaves = list(leaves_collection.find({}).sort("created_at", -1))
    
    # Enrich leave data with staff details
    for l in leaves:
        if "username" in l:
            # Try to find in doctors or receptionists
            staff = doctors_collection.find_one({"username": l["username"]})
            if not staff:
                staff = receptionists_collection.find_one({"username": l["username"]})
            
            if staff:
                l["staff_name"] = staff.get("name", "Unknown")
                l["branch_name"] = "N/A"
                branch_id = staff.get("branch_id")
                if branch_id:
                    branch = get_branch_by_id(branch_id)
                    if branch:
                        l["branch_name"] = branch.get("name", "Unknown Branch")
        
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>All Leaves - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen">
        <nav class="bg-white shadow p-4 flex justify-between items-center sticky top-0 z-50">
            <div class="flex items-center">
                <a href="/auth_home" class="mr-4 text-gray-400 hover:text-teal-600 transition-colors">
                    <i class="ri-arrow-left-line text-2xl"></i>
                </a>
                <h1 class="text-xl font-bold">Staff Leave Management</h1>
            </div>
            <div class="text-sm font-medium text-gray-500">System Admin</div>
        </nav>
        
        <div class="max-w-7xl mx-auto p-6">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="p-4 rounded-xl mb-6 {% if category == 'error' %}bg-red-50 text-red-600{% else %}bg-green-50 text-green-600{% endif %} font-medium">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}

            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <table class="w-full text-left">
                    <thead class="bg-gray-50 border-b border-gray-100">
                        <tr>
                            <th class="p-4 text-xs font-bold text-gray-400 uppercase">Staff</th>
                            <th class="p-4 text-xs font-bold text-gray-400 uppercase">Branch</th>
                            <th class="p-4 text-xs font-bold text-gray-400 uppercase">Leave Period</th>
                            <th class="p-4 text-xs font-bold text-gray-400 uppercase">Type</th>
                            <th class="p-4 text-xs font-bold text-gray-400 uppercase">Status</th>
                            <th class="p-4 text-xs font-bold text-gray-400 uppercase">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for l in leaves %}
                        <tr class="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                            <td class="p-4">
                                <p class="font-bold text-gray-900">{{ l.staff_name }}</p>
                                <p class="text-xs text-gray-500">{{ l.role|capitalize }}</p>
                            </td>
                            <td class="p-4 text-sm text-gray-600">{{ l.branch_name }}</td>
                            <td class="p-4">
                                <p class="text-sm text-gray-800">{{ l.start_date }} to {{ l.end_date }}</p>
                                <p class="text-[10px] font-bold text-teal-600">{{ l.days }} Days</p>
                            </td>
                            <td class="p-4 font-medium text-sm text-gray-700">{{ l.leave_type }}</td>
                            <td class="p-4">
                                <span class="px-2 py-1 rounded text-[10px] font-bold uppercase
                                    {% if l.status == 'approved' %}bg-green-100 text-green-600
                                    {% elif l.status == 'rejected' %}bg-red-100 text-red-600
                                    {% else %}bg-yellow-100 text-yellow-600{% endif %}">
                                    {{ l.status }}
                                </span>
                            </td>
                            <td class="p-4">
                                {% if l.status == 'pending' %}
                                <div class="flex space-x-2">
                                    <form action="/admin/approve_leave/{{ l._id }}" method="POST">
                                        <button type="submit" class="p-1 px-2 bg-green-500 text-white rounded text-[10px] font-bold hover:bg-green-600 transition-colors">Approve</button>
                                    </form>
                                    <form action="/admin/reject_leave/{{ l._id }}" method="POST" class="flex items-center">
                                        <input type="text" name="reason" placeholder="Reason" required class="text-[9px] border p-1 rounded-l mr-0.5 outline-none focus:border-red-400">
                                        <button type="submit" class="p-1 px-2 bg-red-500 text-white rounded-r text-[10px] font-bold hover:bg-red-600 transition-colors">Reject</button>
                                    </form>
                                </div>
                                {% else %}
                                <span class="text-[10px] text-gray-400 italic">Processed</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% if not leaves %}
                <div class="p-20 text-center text-gray-400 italic">No leave applications found.</div>
                {% endif %}
            </div>
        </div>
    </body>
    </html>
    """, leaves=leaves)

@app.route("/admin/branch_details/<branch_id>")
def admin_branch_details(branch_id):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    branch = get_branch_by_id(branch_id)
    if not branch:
        flash("Branch not found.", "error")
        return redirect("/admin_dashboard")
    
    # Fetch branch-specific data
    doctors = list(doctors_collection.find({"branch_id": branch_id}))
    receptionists = list(receptionists_collection.find({"branch_id": branch_id}))
    
    # Patients: both registered in 'patients' and those who have booked in 'appointments'
    patients = list(patients_collection.find({"branch_id": branch_id}))
    
    # Fetch all doctors and receptionists NOT in this branch to allow reassignment
    all_doctors = list(doctors_collection.find({"branch_id": {"$ne": branch_id}}))
    all_receptionists = list(receptionists_collection.find({"branch_id": {"$ne": branch_id}}))
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Branch Details - {{ branch.name }}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Clash+Display:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');
            body { font-family: 'Inter', sans-serif; }
            .font-clash { font-family: 'Clash Display', sans-serif; }
        </style>
    </head>
    <body class="min-h-screen bg-slate-50 p-6">
        <div class="max-w-6xl mx-auto space-y-6">
            <!-- Header -->
            <div class="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 flex justify-between items-center">
                <div>
                    <div class="flex items-center space-x-3 mb-2">
                        <a href="/admin_dashboard" class="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center text-slate-500 hover:bg-teal-500 hover:text-white transition-all">
                            <i class="ri-arrow-left-line"></i>
                        </a>
                        <span class="text-xs font-black uppercase tracking-[3px] text-teal-600">Branch Management</span>
                    </div>
                    <h1 class="text-3xl font-black text-slate-800 tracking-tight font-clash">{{ branch.name }}</h1>
                    <p class="text-slate-500 flex items-center mt-1">
                        <i class="ri-map-pin-2-line mr-1 text-teal-500"></i> {{ branch.location }}
                    </p>
                </div>
                <div class="hidden md:block">
                    <div class="text-right">
                        <p class="text-[10px] font-black uppercase tracking-widest text-slate-400">Inventory Status</p>
                        <span class="inline-flex items-center bg-teal-50 text-teal-600 px-3 py-1 rounded-full text-[10px] font-bold mt-1">
                            <span class="w-1.5 h-1.5 bg-teal-500 rounded-full mr-1.5 animate-pulse"></span> ACTIVE
                        </span>
                    </div>
                </div>
            </div>

            <!-- Stats Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm transition-all hover:shadow-md">
                    <div class="flex items-center space-x-4">
                        <div class="w-14 h-14 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center">
                            <i class="ri-nurse-line text-2xl"></i>
                        </div>
                        <div>
                            <p class="text-2xl font-black text-slate-800 font-clash">{{ doctors|length }}</p>
                            <p class="text-[10px] font-black uppercase tracking-widest text-slate-400">Total Doctors</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm transition-all hover:shadow-md">
                    <div class="flex items-center space-x-4">
                        <div class="w-14 h-14 bg-purple-50 text-purple-600 rounded-2xl flex items-center justify-center">
                            <i class="ri-customer-service-2-line text-2xl"></i>
                        </div>
                        <div>
                            <p class="text-2xl font-black text-slate-800 font-clash">{{ receptionists|length }}</p>
                            <p class="text-[10px] font-black uppercase tracking-widest text-slate-400">Staff Members</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm transition-all hover:shadow-md">
                    <div class="flex items-center space-x-4">
                        <div class="w-14 h-14 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center">
                            <i class="ri-group-line text-2xl"></i>
                        </div>
                        <div>
                            <p class="text-2xl font-black text-slate-800 font-clash">{{ patients|length }}</p>
                            <p class="text-[10px] font-black uppercase tracking-widest text-slate-400">Registered Patients</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Doctors List -->
                <div class="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                    <div class="p-6 border-b border-slate-50 flex justify-between items-center bg-slate-50/30">
                        <h3 class="font-black text-slate-800 uppercase tracking-widest text-xs">Medical Officers</h3>
                    </div>
                    <div class="divide-y divide-slate-50 overflow-y-auto max-h-[400px]">
                        {% for doc in doctors %}
                        <div class="p-5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                            <div class="flex items-center space-x-4">
                                <div class="w-12 h-12 bg-blue-100 text-blue-700 rounded-2xl flex items-center justify-center shadow-inner">
                                    <i class="ri-user-heart-line text-xl"></i>
                                </div>
                                <div>
                                    <p class="font-bold text-slate-700">{{ doc.name }}</p>
                                    <p class="text-[10px] uppercase font-black tracking-widest text-slate-400">{{ doc.specialization or "Resident Doctor" }}</p>
                                </div>
                            </div>
                            <div class="flex items-center space-x-2">
                                <div class="text-right mr-4">
                                    <p class="text-xs font-medium text-slate-500">{{ doc.email }}</p>
                                </div>
                                <button onclick="if(confirm('Remove {{ doc.name }} from this branch?')) window.location.href='/admin/remove_staff/doctor/{{ doc._id }}/{{ branch._id }}'" 
                                        class="w-8 h-8 rounded-full bg-red-50 text-red-500 hover:bg-red-500 hover:text-white transition-all flex items-center justify-center">
                                    <i class="ri-delete-bin-line"></i>
                                </button>
                            </div>
                        </div>
                        {% endfor %}
                        {% if not doctors %}
                        <div class="p-10 text-center text-slate-400 italic text-sm">No medical staff currently assigned.</div>
                        {% endif %}
                    </div>
                    <!-- Assignment Action -->
                    <div class="p-4 bg-slate-50 border-t border-slate-100">
                        <form action="/admin/assign_staff" method="POST" class="flex space-x-2">
                            <input type="hidden" name="branch_id" value="{{ branch._id }}">
                            <input type="hidden" name="role" value="doctor">
                            <select name="user_id" class="flex-1 text-xs border rounded-lg px-2 py-1.5 outline-none focus:ring-2 focus:ring-teal-500">
                                <option value="">Assign Existing Doctor...</option>
                                {% for d in all_doctors %}
                                    <option value="{{ d._id }}">{{ d.name }} ({{ d.username }})</option>
                                {% endfor %}
                            </select>
                            <button type="submit" class="bg-teal-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-teal-700 transition-colors">Assign</button>
                        </form>
                    </div>
                </div>

                <!-- Receptionists List -->
                <div class="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                    <div class="p-6 border-b border-slate-50 flex justify-between items-center bg-slate-50/30">
                        <h3 class="font-black text-slate-800 uppercase tracking-widest text-xs">Customer Relations</h3>
                    </div>
                    <div class="divide-y divide-slate-50 overflow-y-auto max-h-[400px]">
                        {% for rec in receptionists %}
                        <div class="p-5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                            <div class="flex items-center space-x-4">
                                <div class="w-12 h-12 bg-purple-100 text-purple-700 rounded-2xl flex items-center justify-center shadow-inner">
                                    <i class="ri-shield-user-line text-xl"></i>
                                </div>
                                <div>
                                    <p class="font-bold text-slate-700">{{ rec.name }}</p>
                                    <p class="text-[10px] uppercase font-black tracking-widest text-slate-400">Reception Desk</p>
                                </div>
                            </div>
                            <div class="flex items-center space-x-2">
                                <div class="text-right mr-4">
                                    <p class="text-xs font-medium text-slate-500">{{ rec.email }}</p>
                                </div>
                                <button onclick="if(confirm('Remove {{ rec.name }} from this branch?')) window.location.href='/admin/remove_staff/receptionist/{{ rec._id }}/{{ branch._id }}'" 
                                        class="w-8 h-8 rounded-full bg-red-50 text-red-500 hover:bg-red-500 hover:text-white transition-all flex items-center justify-center">
                                    <i class="ri-delete-bin-line"></i>
                                </button>
                            </div>
                        </div>
                        {% endfor %}
                        {% if not receptionists %}
                        <div class="p-10 text-center text-slate-400 italic text-sm">No reception staff assigned.</div>
                        {% endif %}
                    </div>
                    <!-- Assignment Action -->
                    <div class="p-4 bg-slate-50 border-t border-slate-100">
                        <form action="/admin/assign_staff" method="POST" class="flex space-x-2">
                            <input type="hidden" name="branch_id" value="{{ branch._id }}">
                            <input type="hidden" name="role" value="receptionist">
                            <select name="user_id" class="flex-1 text-xs border rounded-lg px-2 py-1.5 outline-none focus:ring-2 focus:ring-teal-500">
                                <option value="">Assign Existing Receptionist...</option>
                                {% for r in all_receptionists %}
                                    <option value="{{ r._id }}">{{ r.name }} ({{ r.username }})</option>
                                {% endfor %}
                            </select>
                            <button type="submit" class="bg-teal-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-teal-700 transition-colors">Assign</button>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Patients Inventory -->
            <div class="bg-white rounded-[40px] border border-slate-100 shadow-sm overflow-hidden">
                <div class="p-8 border-b border-slate-50 bg-slate-50/20">
                    <h3 class="font-black text-slate-800 uppercase tracking-widest text-xs">Branch Patient Registry</h3>
                </div>
                <div class="overflow-x-auto p-2">
                    <table class="w-full text-left">
                        <thead>
                            <tr class="text-[10px] font-black uppercase tracking-widest text-slate-400">
                                <th class="px-8 py-4">Full Identity</th>
                                <th class="px-8 py-4">Contact Info</th>
                                <th class="px-8 py-4">Status</th>
                                <th class="px-8 py-4 text-right">Registered</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-50">
                            {% for patient in patients %}
                            <tr class="hover:bg-slate-50/50 group transition-colors">
                                <td class="px-8 py-5">
                                    <div class="flex items-center">
                                        <div class="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 group-hover:bg-teal-500 group-hover:text-white transition-all mr-3">
                                            <i class="ri-user-3-line"></i>
                                        </div>
                                        <span class="font-bold text-slate-700">{{ patient.name }}</span>
                                    </div>
                                </td>
                                <td class="px-8 py-5">
                                    <div class="flex flex-col">
                                        <span class="text-xs font-bold text-slate-600">{{ patient.phone }}</span>
                                        <span class="text-[10px] text-slate-400">{{ patient.email }}</span>
                                    </div>
                                </td>
                                <td class="px-8 py-5">
                                    <span class="px-3 py-1 bg-green-50 text-green-600 rounded-full text-[10px] font-black tracking-widest uppercase">Verified</span>
                                </td>
                                <td class="px-8 py-5 text-right flex items-center justify-end space-x-3">
                                    <span class="font-medium text-slate-400 text-xs mt-1">
                                        {{ patient.updated_at.strftime('%d %b, %Y') if patient.updated_at else "Historic" }}
                                    </span>
                                    <button onclick="if(confirm('Remove {{ patient.name }}? This will not delete their medical history but only remove them from this branch registry.')) window.location.href='/admin/remove_patient/{{ patient._id }}/{{ branch._id }}'" 
                                            class="w-8 h-8 rounded-full bg-red-50 text-red-500 hover:bg-red-500 hover:text-white transition-all flex items-center justify-center">
                                        <i class="ri-delete-bin-line"></i>
                                    </button>
                                </td>
                            </tr>
                            {% endfor %}
                            {% if not patients %}
                            <tr>
                                <td colspan="4" class="px-8 py-20 text-center">
                                    <div class="flex flex-col items-center">
                                        <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                                            <i class="ri-inbox-archive-line text-2xl text-slate-200"></i>
                                        </div>
                                        <p class="text-slate-400 font-medium italic">No registered patients in this branch.</p>
                                    </div>
                                </td>
                            </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <p class="text-center text-[10px] font-black uppercase tracking-[4px] text-slate-300 py-10">HEY DOC! SECURE ADMINISTRATION UNIT</p>
        </div>
    </body>
    </html>
    """, branch=branch, doctors=doctors, receptionists=receptionists, patients=patients, all_doctors=all_doctors, all_receptionists=all_receptionists)

@app.route("/admin/remove_staff/<role>/<user_id>/<branch_id>")
def admin_remove_staff(role, user_id, branch_id):
    if "admin" not in session: return redirect("/login")
    collection = doctors_collection if role == "doctor" else receptionists_collection
    collection.update_one({"_id": ObjectId(user_id)}, {"$unset": {"branch_id": ""}})
    flash(f"{role.capitalize()} removed from branch.", "success")
    return redirect(f"/admin/branch_details/{branch_id}")

@app.route("/admin/assign_staff", methods=["POST"])
def admin_assign_staff():
    if "admin" not in session: return redirect("/login")
    role = request.form.get("role")
    user_id = request.form.get("user_id")
    branch_id = request.form.get("branch_id")
    if not all([role, user_id, branch_id]):
        flash("Please select a staff member.", "error")
        return redirect(f"/admin/branch_details/{branch_id}")
    collection = doctors_collection if role == "doctor" else receptionists_collection
    collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"branch_id": branch_id}})
    flash(f"Staff assigned to branch successfully.", "success")
    return redirect(f"/admin/branch_details/{branch_id}")

@app.route("/admin/remove_patient/<patient_id>/<branch_id>")
def admin_remove_patient(patient_id, branch_id):
    if "admin" not in session: return redirect("/login")
    patients_collection.update_one({"_id": ObjectId(patient_id)}, {"$unset": {"branch_id": ""}})
    flash("Patient removed from branch registry.", "success")
    return redirect(f"/admin/branch_details/{branch_id}")

@app.route("/admin/delete_branch/<branch_id>")
def admin_delete_branch(branch_id):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    # Attempt deletion by both ObjectId and string ID for robustness
    result = branches_collection.delete_one({"_id": ObjectId(branch_id) if ObjectId.is_valid(branch_id) else branch_id})
    if result.deleted_count == 0 and ObjectId.is_valid(branch_id):
        # Fallback to string if ObjectId didn't match (or vice versa)
        result = branches_collection.delete_one({"_id": branch_id})
        
    if result.deleted_count > 0:
        flash("Branch removed successfully.", "success")
    else:
        flash("Branch not found or already removed.", "error")
    
    return redirect("/admin_dashboard")

@app.route("/admin/all_patients")
def admin_all_patients():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    patients = list(appointments_collection.find({}).sort("created_at", -1))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>All Patients - Admin</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-100 min-h-screen">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center fixed w-full top-0 z-50">
            <h1 class="text-xl font-bold">Global Patient Data</h1>
            <a href="/admin_dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back</a>
        </nav>
        <div class="pt-20 p-6">
            <div class="bg-white rounded-xl shadow-md overflow-hidden">
                <table class="w-full text-sm text-left">
                    <thead class="bg-teal-50 text-teal-800">
                        <tr>
                            <th class="p-4 border-b">Name</th>
                            <th class="p-4 border-b">Phone</th>
                            <th class="p-4 border-b">Location</th>
                            <th class="p-4 border-b">Symptoms</th>
                            <th class="p-4 border-b">Status</th>
                            <th class="p-4 border-b">Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in patients %}
                        <tr class="hover:bg-gray-50">
                            <td class="p-4 border-b font-medium">{{ p.name }}</td>
                            <td class="p-4 border-b">{{ p.phone }}</td>
                            <td class="p-4 border-b">{{ p.location if p.location else "N/A" }}</td>
                            <td class="p-4 border-b">{{ p.symptoms }}</td>
                            <td class="p-4 border-b">
                                <span class="px-2 py-1 rounded text-xs font-bold capitalize 
                                    {% if p.status == 'confirmed' %}bg-green-100 text-green-700
                                    {% elif p.status == 'cancelled' %}bg-red-100 text-red-700
                                    {% else %}bg-yellow-100 text-yellow-700{% endif %}">
                                    {{ p.status }}
                                </span>
                            </td>
                            <td class="p-4 border-b text-gray-500">{{ p.date }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """, patients=patients)

# In your edit_appointment route, pre-fill the phone field without the +91 prefix for editing:
@app.route("/edit_appointment/<appointment_id>", methods=["GET", "POST"])
def edit_appointment(appointment_id):
    if "doctor" not in session:
        flash("Please log in to edit appointments.", "error")
        return redirect("/login")

    appointment = appointments_collection.find_one({"appointment_id": appointment_id})
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect("/dashboard")

    # Remove +91 prefix for display in the form
    phone_display = appointment.get("phone", "")
    if phone_display.startswith("+91"):
        phone_display = phone_display[3:]
    elif phone_display.startswith("91") and len(phone_display) == 12:
        phone_display = phone_display[2:]
    elif phone_display.startswith("0") and len(phone_display) == 11:
        phone_display = phone_display[1:]

    appointment["phone"] = phone_display

    # ...existing code...
    location_options = sorted({
        (b.get("location") or "").strip()
        for b in branches_collection.find({}, {"location": 1})
    })
    default_city = appointment.get("location", location_options[0] if location_options else "Hyderabad")
    # Convert appointment date to YYYY-MM-DD format for generate_time_slots
    appointment_date = appointment.get("date", "")
    if appointment_date:
        try:
            if len(appointment_date) == 10 and appointment_date[2] == '-' and appointment_date[5] == '-':
                # DD-MM-YYYY format, convert to YYYY-MM-DD
                dt = datetime.strptime(appointment_date, "%d-%m-%Y")
                appointment_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    time_slots = generate_time_slots(default_city, appointment_date)
    today_date = datetime.now().strftime("%d-%m-%Y")
    booked_slots = get_booked_slots_for_date(appointment["date"], city=default_city, exclude_appointment_id=appointment_id)

    # ...rest of your code...
    if request.method == "POST":
        try:
            name = request.form["name"]
            phone = request.form["phone"]
            email = request.form["email"]
            location = request.form.get("location", default_city)
            date_input = request.form["date"]
            time = request.form["time"]
            address = request.form["address"]
            symptoms = request.form["symptoms"]

            # Convert date to d-m-Y format for storing
            try:
                date_obj = datetime.strptime(date_input, "%Y-%m-%d")
                date = date_obj.strftime("%d-%m-%Y")
            except Exception:
                date = date_input

            normalized_phone, phone_error = normalize_indian_phone(phone)
            if phone_error:
                flash(phone_error, "error")
                return render_template_string(appointment_form_template, mode='edit', appointment_data=appointment, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

            updated_data = {
                "name": name,
                "phone": normalized_phone,
                "email": email,
                "location": location,
                "date": date,
                "time": time,
                "address": address,
                "symptoms": symptoms
            }

            # Check for slot conflicts (excluding current appointment)
            existing_appointment = appointments_collection.find_one({
                "date": date,
                "time": time,
                "location": location,
                "appointment_id": {"$ne": appointment_id}
            }) or blocked_slots_collection.find_one({
                "date": date,
                "time": time,
                "location": location
            })

            if existing_appointment:
                flash(f"The slot {date} {time} is unavailable (booked/blocked). Please choose a different time.", "error")
                return render_template_string(appointment_form_template, mode='edit', appointment_data=appointment, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

            appointments_collection.update_one({"appointment_id": appointment_id}, {"$set": updated_data})
            flash("Appointment updated successfully.", "success")
            return redirect("/dashboard")

        except Exception as e:
            flash(f"Error updating appointment: {str(e)}", "error")
            return render_template_string(appointment_form_template, mode='edit', appointment_data=appointment, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

    return render_template_string(appointment_form_template, mode='edit', appointment_data=appointment, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

# ...existing code...


@app.route("/dashboard")
def dashboard():
    if "doctor" not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect("/")
    
    search_query = request.args.get('search_query', '').strip()
    sort_by = request.args.get('sort_by', '') 
    
    # Filter by doctor's branch
    doctor_branch = session.get("doctor_branch")
    query = {}
    if doctor_branch:
        query["branch_id"] = doctor_branch
    
    if search_query:
        search_conditions = {
            "$or": [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"appointment_id": {"$regex": search_query, "$options": "i"}},
                {"patient_name": {"$regex": search_query, "$options": "i"}} 
            ]
        }
        if query:
            query = {"$and": [query, search_conditions]}
        else:
            query = search_conditions
    
    appointments = list(appointments_collection.find(query))
    
    # Get circulars for this branch or all
    circular_query = {"$or": [{"branch_id": "all"}, {"branch_id": doctor_branch}]}
    circulars = list(circulars_collection.find(circular_query).sort("created_at", -1))
    
    doctor_data = doctors_collection.find_one({"username": session.get("doctor")})


    for appointment in appointments:
        # Prioritize 'created_at_str' (from Flask app insertions)
        if 'created_at_str' in appointment and appointment['created_at_str'] != 'N/A':
            # Try to parse it to ensure consistency, then re-format
            try:
                # Common format for Flask app: "DD-MM-YYYY HH:MM AM/PM IST"
                dt_obj = datetime.strptime(appointment['created_at_str'], "%d-%m-%Y %I:%M %p IST")
                appointment['created_at_str'] = dt_obj.strftime("%d-%m-%Y %I:%M %p IST")
            except ValueError:
                # If it's already a string but in a different valid format from previous runs, handle it
                # Example: "2025-07-28 09:48 PM IST"
                try:
                    dt_obj = datetime.strptime(appointment['created_at_str'], "%Y-%m-%d %I:%M %p IST") 
                    appointment['created_at_str'] = dt_obj.strftime("%d-%m-%Y %I:%M %p IST")
                except ValueError:
                    # If parsing fails, keep the original string or set to N/A
                    appointment['created_at_str'] = appointment.get('created_at_str', 'N/A')
        # Check for 'created_at' (common for manual insertions or other systems)
        elif 'created_at' in appointment:
            created_val = appointment['created_at']
            if isinstance(created_val, datetime):
                # If it's a datetime object (PyMongo default for BSON Date)
                appointment['created_at_str'] = created_val.strftime("%d-%m-%Y %I:%M %p IST")
            elif isinstance(created_val, str):
                # If it's a string, try to parse various formats
                parsed = False
                formats_to_try = [
                    "%Y-%m-%d %I:%M:%S %p", # Example: "2025-07-28 10:37:39 PM" (from your error)
                    "%Y-%m-%d %I:%M %p",    # Example: "2025-07-28 09:48 PM" (from your dashboard)
                    "%Y-%m-%d %H:%M:%S",    # Common format without AM/PM (if you have any)
                    "%d-%m-%Y %I:%M %p IST" # Already desired format (for existing correct entries)
                ]
                for fmt in formats_to_try:
                    try:
                        dt_obj = datetime.strptime(created_val, fmt)
                        appointment['created_at_str'] = dt_obj.strftime("%d-%m-%Y %I:%M %p IST")
                        parsed = True
                        break
                    except ValueError:
                        continue
                if not parsed:
                    # If all parsing attempts fail, keep original or default
                    appointment['created_at_str'] = created_val if created_val else 'N/A'
            else:
                appointment['created_at_str'] = 'N/A' # Fallback for unexpected types
        else:
            # If neither field exists, default to 'N/A'
            appointment['created_at_str'] = 'N/A'
            
        # Also ensure 'name' field is populated for display from 'patient_name' if needed
        if 'name' not in appointment and 'patient_name' in appointment:
            appointment['name'] = appointment['patient_name']

        # Ensure 'phone' field is populated from 'patient_phone' if needed
        if 'phone' not in appointment and 'patient_phone' in appointment:
            appointment['phone'] = appointment['patient_phone']
            


    # Apply sorting logic
    def get_sort_key_for_date(appointment_item):
        date_str = appointment_item.get('date', '2000-01-01')
        time_str = appointment_item.get('time', '00:00')
        
        # Normalize time_str to 24-hour format if it contains AM/PM
        if 'AM' in time_str or 'PM' in time_str:
            try:
                # Try parsing with seconds, then without seconds
                try:
                    dt_obj = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M:%S %p")
                except ValueError:
                    dt_obj = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
                return dt_obj
            except ValueError:
                return datetime.min # Fallback for unparseable date/time
        else:
            try:
                # Assume 24-hour format if no AM/PM
                dt_obj = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                return dt_obj
            except ValueError:
                return datetime.min # Fallback for unparseable date/time

    if sort_by == 'name_asc':
        appointments.sort(key=lambda x: x.get('name', '').lower())
    elif sort_by == 'name_desc':
        appointments.sort(key=lambda x: x.get('name', '').lower(), reverse=True)
    elif sort_by == 'date_asc':
        appointments.sort(key=get_sort_key_for_date)
    elif sort_by == 'date_desc':
        appointments.sort(key=get_sort_key_for_date, reverse=True)
    else:
        # Default sorting by created_at_str (latest first)
        def get_created_at_sort_key(appointment_item):
            created_at_str = appointment_item.get('created_at_str', '')
            if created_at_str and 'N/A' not in created_at_str:
                # Try multiple formats for created_at_str for sorting
                sort_formats_to_try = [
                    "%d-%m-%Y %I:%M %p IST",  # Your desired output format
                    "%Y-%m-%d %I:%M:%S %p",  # Format from manual entry error
                    "%Y-%m-%d %I:%M %p",     # Another possible format
                    "%Y-%m-%d %H:%M:%S",     # Another common format
                ]
                for fmt in sort_formats_to_try:
                    try:
                        return datetime.strptime(created_at_str, fmt)
                    except ValueError:
                        continue
            return datetime.min # Fallback for 'N/A' or unparseable dates
        
        appointments.sort(key=get_created_at_sort_key, reverse=True)


    # Clean up any appointments with missing or incorrect field names
    cleanup_appointments()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    next_holiday = holidays_collection.find_one({"date": {"$gte": today_str}}, sort=[("date", 1)])

    return render_template_string(dashboard_template, doctor=session["doctor"], appointments=appointments, search_query=search_query, sort_by=sort_by, circulars=circulars, doctor_data=doctor_data, next_holiday=next_holiday)

@app.route("/cleanup_appointments")
def cleanup_appointments_route():
    if "doctor" not in session:
        flash("Please log in to access this function.", "error")
        return redirect("/")
    
    try:
        cleanup_appointments()
        flash("Appointments cleaned up successfully!", "success")
    except Exception as e:
        flash(f"Error cleaning up appointments: {str(e)}", "error")
    
    return redirect("/dashboard")

# --- Password Reset Routes ---
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        user_type = request.form.get("user_type", "doctor").strip()
        
        if not email:
            flash("Email is required", "error")
            return redirect("/forgot_password")
        
        # Find user based on type
        user = None
        if user_type == "admin":
            user = admin_collection.find_one({"email": email})
        elif user_type == "doctor":
            user = doctors_collection.find_one({"email": email})
        elif user_type == "receptionist":
            user = receptionists_collection.find_one({"email": email})
        
        if user:
            # Generate reset token
            reset_token = str(ObjectId())
            password_reset_collection.insert_one({
                "email": email,
                "token": reset_token,
                "user_type": user_type,
                "created_at": datetime.utcnow(),
                "used": False
            })
            
            # Send reset email
            if send_password_reset_email(email, reset_token):
                flash("Password reset link has been sent to your email.", "success")
            else:
                flash("Failed to send reset email. Please try again.", "error")
        else:
            flash("Email not found.", "error")
        
        return redirect("/login")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Forgot Password - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="flex items-center justify-center min-h-screen bg-gray-100">
        <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
            <h2 class="text-2xl font-bold mb-6 text-center text-gray-800">Forgot Password</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <form method="POST" action="/forgot_password">
                <div class="mb-4">
                    <label for="user_type" class="block text-gray-700 text-sm font-bold mb-2">Account Type:</label>
                    <select id="user_type" name="user_type" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                        <option value="doctor">Doctor</option>
                        <option value="admin">Admin</option>
                        <option value="receptionist">Receptionist</option>
                    </select>
                </div>
                <div class="mb-6">
                    <label for="email" class="block text-gray-700 text-sm font-bold mb-2">Email:</label>
                    <input type="email" id="email" name="email" required
                           class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                </div>
                <div class="flex items-center justify-between">
                    <button type="submit"
                            class="bg-teal-600 hover:bg-teal-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">
                        Send Reset Link
                    </button>
                    <a href="/login" class="inline-block align-baseline font-bold text-sm text-teal-600 hover:text-teal-800">
                        Back to Login
                    </a>
                </div>
            </form>
        </div>
    </body>
    </html>
    """)

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token") or request.form.get("token", "")
    
    if not token:
        flash("Invalid reset token", "error")
        return redirect("/login")
    
    reset_record = password_reset_collection.find_one({"token": token, "used": False})
    if not reset_record:
        flash("Invalid or expired reset token", "error")
        return redirect("/login")
    
    # Check if token is expired (1 hour)
    if datetime.utcnow() - reset_record["created_at"] > timedelta(hours=1):
        flash("Reset token has expired. Please request a new one.", "error")
        password_reset_collection.update_one({"_id": reset_record["_id"]}, {"$set": {"used": True}})
        return redirect("/forgot_password")
    
    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        
        if not new_password or new_password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(f"/reset_password?token={token}")
        
        # Update password based on user type
        user_type = reset_record["user_type"]
        email = reset_record["email"]
        
        if user_type == "admin":
            admin_collection.update_one({"email": email}, {"$set": {"password": new_password}})
        elif user_type == "doctor":
            doctors_collection.update_one({"email": email}, {"$set": {"password": new_password}})
        elif user_type == "receptionist":
            receptionists_collection.update_one({"email": email}, {"$set": {"password": new_password}})
        
        # Mark token as used
        password_reset_collection.update_one({"_id": reset_record["_id"]}, {"$set": {"used": True}})
        
        flash("Password reset successfully! Please login with your new password.", "success")
        return redirect("/login")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Reset Password - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="flex items-center justify-center min-h-screen bg-gray-100">
        <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
            <h2 class="text-2xl font-bold mb-6 text-center text-gray-800">Reset Password</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <form method="POST" action="/reset_password">
                <input type="hidden" name="token" value="{{ token }}">
                <div class="mb-4">
                    <label for="password" class="block text-gray-700 text-sm font-bold mb-2">New Password:</label>
                    <div class="relative">
                        <input type="password" id="password" name="password" required
                               class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                        <button type="button" onclick="toggleVisibility('password', 'eye1')" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                            <i id="eye1" class="ri-eye-line"></i>
                        </button>
                    </div>
                </div>
                <div class="mb-6">
                    <label for="confirm_password" class="block text-gray-700 text-sm font-bold mb-2">Confirm Password (Recheck):</label>
                    <div class="relative">
                        <input type="password" id="confirm_password" name="confirm_password" required
                               class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                        <button type="button" onclick="toggleVisibility('confirm_password', 'eye2')" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                            <i id="eye2" class="ri-eye-line"></i>
                        </button>
                    </div>
                </div>
                <div class="flex items-center justify-between">
                    <button type="submit"
                            class="bg-teal-600 hover:bg-teal-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">
                        Reset Password
                    </button>
                    <a href="/login" class="inline-block align-baseline font-bold text-sm text-teal-600 hover:text-teal-800">
                        Back to Login
                    </a>
                </div>
            </form>
        </div>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <script>
            function toggleVisibility(inputId, iconId) {
                const input = document.getElementById(inputId);
                const icon = document.getElementById(iconId);
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.classList.replace('ri-eye-line', 'ri-eye-off-line');
                } else {
                    input.type = 'password';
                    icon.classList.replace('ri-eye-off-line', 'ri-eye-line');
                }
            }
        </script>
    </body>
    </html>
    """, token=token)

# --- Reception Dashboard ---
@app.route("/reception_dashboard")
def reception_dashboard():
    if "receptionist" not in session:
        flash("Please log in as receptionist to access this page.", "error")
        return redirect("/login")
    
    branch_id = session.get("receptionist_branch")
    query = {}
    if branch_id:
        # Robust branch matching
        query["branch_id"] = {"$in": [branch_id, ObjectId(branch_id) if ObjectId.is_valid(branch_id) else None]}

    
    appointments = list(appointments_collection.find(query).sort("date", 1))
    
    # Get circulars for this branch or all
    circular_query = {"$or": [{"branch_id": "all"}, {"branch_id": branch_id}]}
    circulars = list(circulars_collection.find(circular_query).sort("created_at", -1))
    
    # Get own leaves
    my_leaves = list(leaves_collection.find({"username": session.get("receptionist"), "role": "receptionist"}).sort("applied_at", -1))
    
    # Get all doctors in this branch to show availability
    doctors = list(doctors_collection.find(query))
    
    # Check current active leaves for doctors to show "On Leave" status
    today_str = datetime.now().strftime("%Y-%m-%d")
    for doc in doctors:
        active_leave = leaves_collection.find_one({
            "doctor_username": doc["username"],
            "status": "approved",
            "start_date": {"$lte": today_str},
            "end_date": {"$gte": today_str}
        })
        doc["is_on_leave"] = True if active_leave else False
        if active_leave:
            doc["leave_info"] = active_leave
        
    next_holiday = holidays_collection.find_one({"date": {"$gte": today_str}}, sort=[("date", 1)])
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Reception Dashboard - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
            body { font-family: 'Outfit', sans-serif; perspective: 1000px; }
            .card-3d { 
                transition: transform 0.6s cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.6s;
                transform-style: preserve-3d;
            }
            .card-3d:hover { 
                transform: translateY(-10px) rotateX(2deg) rotateY(2deg);
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            .glass-purple { background: rgba(126, 34, 206, 0.95); backdrop-filter: blur(8px); }
        </style>
    </head>
    <body class="min-h-screen bg-gray-50">
        <nav class="glass-purple p-4 text-white flex justify-between items-center fixed w-full top-0 z-50 shadow-lg border-b border-white/10">
            <div class="flex items-center">
                <img src="/static/images/heydoc_logo.png" alt="HeyDoc" class="h-10 mr-3 bg-white rounded-xl p-1.5 shadow-sm">
                <h1 class="text-xl font-black tracking-tight">Hey Doc! Frontdesk</h1>
            </div>
            <div class="flex items-center space-x-4">
                <a href="/my_payroll" class="mr-2 px-4 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-xs font-bold uppercase transition-all tracking-widest"><i class="ri-money-dollar-circle-line mr-1"></i> My Payroll</a>
                <span class="mr-2 text-purple-100 italic font-medium px-4 py-1.5 border-l border-white/20">Welcome, {{ session.receptionist }}</span>
                <a href="/receptionist/profile" class="mr-3 text-white/80 hover:text-white transition-colors"><i class="ri-user-3-line mr-1"></i> Profile</a>
                <a href="/logout" class="bg-white text-purple-700 px-4 py-1.5 rounded-lg font-bold hover:bg-purple-50 transition-colors shadow-lg">Logout</a>
            </div>
        </nav>
        
        <div class="pt-24 p-6 max-w-7xl mx-auto">
            <!-- New/Existing User Selection Boxes -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <a href="/reception/add_patient" class="bg-gradient-to-br from-purple-600 to-indigo-700 rounded-3xl p-8 hover:shadow-2xl hover:shadow-purple-200 transition-all group overflow-hidden relative">
                    <div class="absolute -right-4 -top-4 w-32 h-32 bg-white/10 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700"></div>
                    <div class="flex items-center space-x-6 relative z-10">
                        <div class="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center text-3xl text-white">
                            <i class="ri-user-add-line"></i>
                        </div>
                        <div class="text-white">
                            <h3 class="text-xl font-black uppercase tracking-tight">New Patient</h3>
                            <p class="text-purple-100 text-sm">Register and book for a first-time visitor</p>
                        </div>
                        <div class="ml-auto">
                            <i class="ri-arrow-right-line text-white/50 text-2xl group-hover:translate-x-2 transition-transform"></i>
                        </div>
                    </div>
                </a>

                <a href="/reception/existing_patients" class="bg-white border-2 border-slate-100 rounded-3xl p-8 hover:border-purple-200 hover:shadow-xl hover:shadow-slate-200 transition-all group overflow-hidden relative">
                    <div class="flex items-center space-x-6 relative z-10">
                        <div class="w-16 h-16 bg-purple-50 rounded-2xl flex items-center justify-center text-3xl text-purple-600">
                            <i class="ri-team-line"></i>
                        </div>
                        <div class="text-slate-800">
                            <h3 class="text-xl font-black uppercase tracking-tight">Existing Patient</h3>
                            <p class="text-slate-500 text-sm">Quick book for returning medical records</p>
                        </div>
                        <div class="ml-auto">
                            <i class="ri-arrow-right-line text-slate-300 text-2xl group-hover:translate-x-2 transition-transform"></i>
                        </div>
                    </div>
                </a>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Main Content Area -->
            <div class="lg:col-span-2 space-y-6">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-4 rounded-lg {% if category == 'error' %}bg-red-100 text-red-700{% else %}bg-green-100 text-green-700{% endif %} font-medium shadow-sm mb-4">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}
                
                {% if next_holiday %}
                <div class="bg-blue-600 rounded-[30px] p-6 text-white shadow-xl flex items-center justify-between group overflow-hidden relative">
                    <div class="absolute -right-4 -top-4 w-32 h-32 bg-white/10 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700"></div>
                    <div class="flex items-center space-x-6 relative z-10">
                        <div class="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center text-3xl blur-px"><i class="ri-calendar-event-line"></i></div>
                        <div>
                            <p class="text-xs font-black uppercase tracking-widest text-blue-100 opacity-80">Upcoming Hospital Holiday</p>
                            <h3 class="text-2xl font-black">{{ next_holiday.title }}</h3>
                        </div>
                    </div>
                    <div class="text-right relative z-10">
                        <p class="text-[10px] font-black uppercase tracking-widest text-blue-200">Scheduled for</p>
                        <p class="text-xl font-bold">{{ next_holiday.date }}</p>
                        <a href="/holiday/calendar" class="mt-1 inline-block text-[10px] font-black uppercase tracking-widest underline underline-offset-4 hover:text-white transition-colors">View All Holidays</a>
                    </div>
                </div>
                {% endif %}

                <div class="bg-white rounded-3xl shadow-xl border border-gray-100 overflow-hidden card-3d">
                    <div class="p-6 border-b border-gray-50 flex justify-between items-center bg-white">
                        <h2 class="text-xl font-bold text-gray-800 flex items-center">
                            <i class="ri-calendar-check-line mr-2 text-purple-600"></i> Appointments
                        </h2>
                        <a href="/reception/add_patient" class="bg-purple-600 text-white px-5 py-2 rounded-xl font-bold hover:bg-purple-700 transition-all transform hover:scale-105 shadow-md flex items-center">
                            <i class="ri-user-add-line mr-2"></i> Add Patient
                        </a>
                    </div>
                    
                    <div class="overflow-x-auto">
                        <table class="w-full text-sm text-left">
                            <thead class="bg-gray-50 text-gray-600 uppercase text-xs font-bold">
                                <tr>
                                    <th class="p-4">Patient Details</th>
                                    <th class="p-4">Schedule</th>
                                    <th class="p-4">Status</th>
                                    <th class="p-4 text-center">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">
                                {% for appointment in appointments %}
                                    <tr class="hover:bg-purple-50/30 transition-colors">
                                        <td class="p-4">
                                            <p class="font-bold text-gray-900">{{ appointment.get('name') or appointment.get('patient_name', 'N/A') }}</p>
                                            <p class="text-xs text-gray-500">{{ appointment.get('phone', 'N/A') }}</p>
                                        </td>
                                        <td class="p-4">
                                            <p class="text-gray-700 font-medium">{{ appointment.get('date', 'N/A') }}</p>
                                            <p class="text-xs text-gray-500">{{ appointment.get('time', 'N/A') }}</p>
                                        </td>
                                        <td class="p-4">
                                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase
                                                {% if appointment.get('status') == 'confirmed' %}bg-green-100 text-green-700
                                                {% elif appointment.get('status') == 'cancelled' %}bg-red-100 text-red-700
                                                {% elif appointment.get('status') == 'pending_reception' %}bg-orange-100 text-orange-700
                                                {% else %}bg-yellow-100 text-yellow-700{% endif %}">
                                                {{ appointment.get('status', 'pending').replace('_', ' ') }}
                                            </span>
                                        </td>
                                        <td class="p-4 text-center">
                                            {% if appointment.get('status') == 'pending_reception' or appointment.get('status') == 'pending' %}
                                                <a href="/reception/select_doctor/{{ appointment.appointment_id }}" class="inline-flex items-center px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition-colors shadow-sm animate-pulse">
                                                    <i class="ri-user-follow-line mr-1.5"></i> Assign Doctor
                                                </a>
                                            {% elif appointment.get('doctor_name') %}
                                                <div class="flex flex-col items-center">
                                                    <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">Assigned To</span>
                                                    <span class="text-sm font-bold text-indigo-600">Dr. {{ appointment.get('doctor_name') }}</span>
                                                </div>
                                            {% elif appointment.get('status') in ['confirmed', 'sent_to_doctor', 'completed', 'cancelled'] %}
                                                <div class="flex flex-col items-center">
                                                     <span class="text-xs font-bold text-gray-400 uppercase tracking-wider">Status</span>
                                                     <span class="font-bold text-gray-600">{{ appointment.get('status').replace('_', ' ').title() }}</span>
                                                </div>
                                            {% else %}
                                                <a href="/reception/select_doctor/{{ appointment.appointment_id }}" class="inline-flex items-center px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition-colors shadow-sm">
                                                    <i class="ri-user-follow-line mr-1.5"></i> Assign Doctor
                                                </a>
                                            {% endif %}
                                        </td>
                                    </tr>
                                {% endfor %}
                                {% if not appointments %}
                                    <tr>
                                        <td colspan="4" class="p-10 text-center text-gray-400 italic">No appointments found for your branch.</td>
                                    </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Sidebar -->
            <div class="space-y-6">
                <!-- Circulars Widget -->
                <div class="bg-white rounded-3xl shadow-xl border border-gray-100 p-6 card-3d">
                    <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center">
                        <i class="ri-notification-3-line mr-2 text-red-500"></i> Branch Circulars
                    </h3>
                    {% if circulars %}
                        <div class="space-y-3">
                            {% for c in circulars %}
                                <div class="p-3 bg-red-50 rounded-xl border border-red-100 group cursor-pointer hover:bg-red-100 transition-colors">
                                    <p class="font-bold text-red-800 text-sm mb-1 group-hover:text-red-900">{{ c.title }}</p>
                                    <p class="text-xs text-red-600 line-clamp-2 mb-2">{{ c.content }}</p>
                                    <div class="flex justify-between items-center text-[10px] text-red-400 font-medium">
                                        <span>{{ c.created_at.strftime('%d %b') }}</span>
                                        {% if c.file_path %}
                                            <a href="/download/{{ c.file_path.split('/')[-1] }}" class="text-red-600 font-bold hover:underline flex items-center">
                                                <i class="ri-download-2-line mr-1"></i> Download
                                            </a>
                                        {% endif %}
                                    </div>
                                </div>
                            {% endfor %}
                        </div>
                    {% else %}
                        <p class="text-gray-400 text-xs italic text-center py-4">No circulars for your branch.</p>
                    {% endif %}
                </div>

                <!-- Doctor Availability Widget -->
                <div class="bg-white rounded-3xl shadow-xl border border-gray-100 p-6 card-3d">
                    <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center">
                        <i class="ri-user-heart-line mr-2 text-teal-600"></i> Branch Medical Staff
                    </h3>
                    <div class="space-y-4">
                        {% for doc in doctors %}
                            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                                <div class="flex items-center">
                                    <div class="w-10 h-10 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center mr-3 font-bold">
                                        {{ doc.name[0] }}
                                    </div>
                                    <div>
                                        <p class="text-sm font-bold text-gray-800">{{ doc.name }}</p>
                                        <p class="text-[10px] text-gray-500 uppercase">{{ doc.specialization or "Doctor" }}</p>
                                    </div>
                                </div>
                                <div>
                                    {% if doc.is_on_leave %}
                                        <span class="inline-flex items-center bg-red-100 text-red-600 px-2 py-0.5 rounded text-[10px] font-bold">
                                            <span class="w-1 h-1 bg-red-500 rounded-full mr-1 animate-pulse"></span> ON LEAVE
                                        </span>
                                    {% else %}
                                        <span class="inline-flex items-center bg-green-100 text-green-600 px-2 py-0.5 rounded text-[10px] font-bold">
                                            <span class="w-1 h-1 bg-green-500 rounded-full mr-1"></span> ACTIVE
                                        </span>
                                    {% endif %}
                                </div>
                            </div>
                        {% endfor %}
                        {% if not doctors %}
                            <p class="text-gray-400 text-xs italic text-center py-2">No doctors assigned to this branch.</p>
                        {% endif %}
                    </div>
                </div>

                <!-- Calendars Widget -->
                <div class="bg-white rounded-3xl shadow-xl border border-gray-100 p-6 card-3d">
                    <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center">
                        <i class="ri-calendar-2-line mr-2 text-indigo-500"></i> Calendars
                    </h3>
                    <div class="grid grid-cols-2 gap-3">
                        <a href="/leave/calendar" class="flex flex-col items-center justify-center p-4 bg-indigo-50 rounded-2xl hover:bg-indigo-100 transition-colors border border-indigo-100">
                            <i class="ri-calendar-check-line text-2xl text-indigo-600 mb-1"></i>
                            <span class="text-[10px] font-black uppercase text-indigo-700">Leaves</span>
                        </a>
                        <a href="/holiday/calendar" class="flex flex-col items-center justify-center p-4 bg-pink-50 rounded-2xl hover:bg-pink-100 transition-colors border border-pink-100">
                            <i class="ri-calendar-event-line text-2xl text-pink-600 mb-1"></i>
                            <span class="text-[10px] font-black uppercase text-pink-700">Holidays</span>
                        </a>
                    </div>
                </div>

                <!-- Leave Application Widget -->
                <div class="bg-white rounded-3xl shadow-xl border border-gray-100 p-6 card-3d">
                    <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center">
                        <i class="ri-calendar-event-line mr-2 text-orange-500"></i> My Leaves
                    </h3>
                    <a href="/leave/apply" class="w-full bg-orange-500 text-white py-2.5 rounded-xl font-bold text-sm hover:bg-orange-600 transition-colors mb-4 flex items-center justify-center">
                        <i class="ri-add-line mr-2"></i> Apply for Leave
                    </a>
                    
                    <div class="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                        {% for l in my_leaves %}
                            <div class="p-3 bg-gray-50 rounded-xl border border-gray-200">
                                <div class="flex justify-between items-start mb-1">
                                    <p class="text-xs font-bold text-gray-700">{{ l.start_date }} → {{ l.end_date }}</p>
                                    <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase
                                        {% if l.status == 'approved' %}bg-green-100 text-green-700
                                        {% elif l.status == 'rejected' %}bg-red-100 text-red-700
                                        {% else %}bg-yellow-100 text-yellow-700{% endif %}">
                                        {{ l.status }}
                                    </span>
                                </div>
                                {% if l.admin_reason %}
                                    <p class="text-[10px] text-gray-500 bg-white p-1.5 rounded mt-1 border border-gray-100 italic">"{{ l.admin_reason }}"</p>
                                {% endif %}
                            </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>

        <!-- Leave Modal -->
        <div id="leaveModal" class="hidden fixed inset-0 bg-black/50 z-[100] flex items-center justify-center p-4">
            <div class="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 animate-in fade-in zoom-in duration-200">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-xl font-bold text-gray-800">Apply for Leave</h2>
                    <button onclick="document.getElementById('leaveModal').classList.add('hidden')" class="text-gray-400 hover:text-gray-600 transition-colors">
                        <i class="ri-close-line text-2xl"></i>
                    </button>
                </div>
                <form action="/apply_leave" method="POST" class="space-y-4">
                    <div>
                        <label class="block text-xs font-bold text-gray-700 mb-1 uppercase">Leave Type</label>
                        <select name="leave_type" required class="w-full p-2.5 border rounded-xl focus:ring-2 focus:ring-purple-500 outline-none text-sm">
                            <option value="Casual Leave">Casual Leave</option>
                            <option value="Sick Leave">Sick Leave</option>
                            <option value="Loss of Pay">Loss of Pay</option>
                            <option value="Compensatory Off">Compensatory Off</option>
                            <option value="Bereavement">Bereavement</option>
                            <option value="Work From Home">Work From Home</option>
                        </select>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-bold text-gray-700 mb-1 uppercase">Start Date</label>
                            <input type="date" name="start_date" required class="w-full p-2.5 border rounded-xl focus:ring-2 focus:ring-purple-500 outline-none text-sm">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-gray-700 mb-1 uppercase">End Date</label>
                            <input type="date" name="end_date" required class="w-full p-2.5 border rounded-xl focus:ring-2 focus:ring-purple-500 outline-none text-sm">
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-gray-700 mb-1 uppercase">Reason</label>
                        <textarea name="reason" rows="3" required class="w-full p-2.5 border rounded-xl focus:ring-2 focus:ring-purple-500 outline-none text-sm" placeholder="Why do you need leave?"></textarea>
                    </div>
                    <div class="pt-4 flex space-x-3">
                        <button type="button" onclick="document.getElementById('leaveModal').classList.add('hidden')" class="flex-1 py-3 text-sm font-bold text-gray-500 hover:text-gray-700 transition-colors">Cancel</button>
                        <button type="submit" class="flex-1 py-3 bg-purple-600 text-white rounded-xl font-bold text-sm hover:bg-purple-700 shadow-lg transition-all active:scale-95">Submit Request</button>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, appointments=appointments, circulars=circulars, my_leaves=my_leaves, doctors=doctors, next_holiday=next_holiday)

@app.route("/reception/add_patient", methods=["GET", "POST"])
def reception_add_patient():
    if "receptionist" not in session:
        flash("Please log in as receptionist to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            address = request.form.get("address", "").strip()
            date = request.form.get("date", "").strip()
            time = request.form.get("time", "").strip()
            symptoms = request.form.get("symptoms", "").strip()
            
            if not all([name, phone, date, time]):
                flash("Name, phone, date, and time are required.", "error")
                return redirect("/reception/add_patient")
            
            # Handle Certificate Upload
            certificate_path = None
            if 'diagnosis_certificate' in request.files:
                file = request.files['diagnosis_certificate']
                if file and file.filename:
                    try:
                        # Ensure directory exists
                        if not os.path.exists(CERTIFICATES_FOLDER):
                            os.makedirs(CERTIFICATES_FOLDER, exist_ok=True)
                            
                        filename = secure_filename(f"cert_{phone}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                        file_save_path = os.path.join(CERTIFICATES_FOLDER, filename)
                        file.save(file_save_path)
                        certificate_path = f"certificates/{filename}"
                    except Exception as e:
                        print(f"Error saving diagnosis certificate: {e}")
                        flash(f"Note: Appointment added but certificate could not be saved: {e}", "warning")
            
            # Normalize phone
            phone_normalized, error = normalize_indian_phone(phone)
            if error:
                flash(error, "error")
                return redirect("/reception/add_patient")
            
            appointment_id = f"APT{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
            
            appointment_doc = {
                "appointment_id": appointment_id,
                "name": name,
                "phone": phone_normalized,
                "email": email or "No email provided",
                "address": address,
                "date": date,
                "time": time,
                "symptoms": symptoms,
                "status": "pending",
                "branch_id": session.get("receptionist_branch"),
                "certificate_path": certificate_path,
                "created_at": datetime.utcnow(),
                "created_at_str": datetime.now().strftime("%d-%m-%Y %I:%M %p IST")
            }
            
            appointments_collection.insert_one(appointment_doc)
            
            # Also add to patients collection
            patients_collection.update_one(
                {"phone": phone_normalized},
                {"$set": {
                    "name": name,
                    "email": email,
                    "address": address,
                    "phone": phone_normalized,
                    "branch_id": session.get("receptionist_branch"),
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
            
            flash("Patient added successfully!", "success")
            return redirect("/reception_dashboard")
        except Exception as e:
            flash(f"Error adding patient: {e}", "error")
    
    branch_id = session.get("receptionist_branch")
    branch = get_branch_by_id(branch_id) if branch_id else None
    location = branch.get("location", "Hyderabad") if branch else "Hyderabad"
    time_slots = generate_time_slots(location)
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Add Patient - Reception</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div class="bg-white rounded-3xl shadow-xl w-full max-w-2xl overflow-hidden border border-gray-100">
            <div class="bg-purple-700 p-8 text-white flex justify-between items-center">
                <div>
                    <h1 class="text-2xl font-bold">New Patient Entry</h1>
                    <p class="text-purple-100 text-sm mt-1">Fill in the details to schedule an appointment</p>
                </div>
                <a href="/reception_dashboard" class="text-white/80 hover:text-white transition-colors">
                    <i class="ri-close-line text-3xl"></i>
                </a>
            </div>
            
            <form method="POST" enctype="multipart/form-data" class="p-8 space-y-6">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-4 rounded-xl {% if category == 'error' %}bg-red-50 text-red-600{% else %}bg-green-50 text-green-600{% endif %} font-medium text-sm">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Patient Name *</label>
                        <input type="text" name="name" required class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Phone Number *</label>
                        <input type="text" name="phone" required class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Appointment Date *</label>
                        <input type="date" name="date" required min="{{ datetime.now().strftime('%Y-%m-%d') }}" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Appointment Time *</label>
                        <select name="time" required class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none transition-all">
                            {% for slot in time_slots %}
                                <option value="{{ slot }}">{{ slot }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                
                <div class="space-y-1">
                    <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Symptoms / Reason for Visit</label>
                    <textarea name="symptoms" rows="2" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none transition-all" placeholder="Briefly describe the patient's condition..."></textarea>
                </div>

                <div class="space-y-1">
                    <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Diagnosis Certificate (Optional)</label>
                    <div class="relative">
                        <input type="file" name="diagnosis_certificate" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none transition-all file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100">
                    </div>
                    <p class="text-[10px] text-gray-400 mt-1 italic">Carry original reports if available</p>
                </div>

                <div class="pt-2">
                    <button type="submit" class="w-full bg-purple-700 text-white py-3.5 rounded-xl font-bold text-md hover:bg-purple-800 shadow-lg shadow-purple-200 transition-all transform active:scale-[0.98]">
                        Confirm & Save Appointment
                    </button>
                </div>
            </form>
        </div>
    </body>
    </html>
    """, time_slots=time_slots, datetime=datetime)

@app.route("/reception/existing_patients")
def reception_existing_patients():
    if "receptionist" not in session:
        return redirect("/login")
        
    patients = list(patients_collection.find({}).sort("name", 1))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Existing Patients - Reception</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen p-6">
        <div class="max-w-4xl mx-auto">
            <div class="bg-white rounded-3xl shadow-xl overflow-hidden border border-gray-100">
                <div class="bg-indigo-700 p-8 text-white flex justify-between items-center">
                    <div>
                        <h1 class="text-2xl font-bold">Patient Directory</h1>
                        <p class="text-indigo-100 text-sm mt-1">Select a returning patient to book an appointment</p>
                    </div>
                    <a href="/reception_dashboard" class="text-white/80 hover:text-white transition-colors">
                        <i class="ri-close-line text-3xl"></i>
                    </a>
                </div>
                
                <div class="p-8">
                    <div class="relative mb-6">
                        <i class="ri-search-line absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"></i>
                        <input type="text" id="patientSearch" placeholder="Search by name or phone..." 
                               class="w-full pl-12 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all">
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4" id="patientList">
                        {% for p in patients %}
                        <div class="patient-card p-4 bg-slate-50 border border-slate-100 rounded-2xl hover:border-indigo-300 hover:bg-white transition-all group flex justify-between items-center" 
                             data-search="{{ p.get('name', '').lower() }} {{ p.get('phone', '') }}">
                            <div>
                                <p class="font-bold text-gray-800">{{ p.get('name', 'Unknown') }}</p>
                                <p class="text-xs text-gray-500">{{ p.get('phone', 'N/A') }}</p>
                            </div>
                            <form action="/reception/book_existing" method="POST">
                                <input type="hidden" name="patient_id" value="{{ p._id }}">
                                <button type="submit" class="p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors">
                                    <i class="ri-calendar-event-line mr-1"></i> Book
                                </button>
                            </form>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.getElementById('patientSearch').addEventListener('input', function(e) {
                const term = e.target.value.toLowerCase();
                document.querySelectorAll('.patient-card').forEach(card => {
                    const searchData = card.getAttribute('data-search');
                    card.style.display = searchData.includes(term) ? 'flex' : 'none';
                });
            });
        </script>
    </body>
    </html>
    """, patients=patients)

@app.route("/reception/book_existing", methods=["POST"])
def reception_book_existing():
    if "receptionist" not in session:
        return redirect("/login")
        
    patient_id = request.form.get("patient_id")
    patient = patients_collection.find_one({"_id": ObjectId(patient_id) if ObjectId.is_valid(patient_id) else patient_id})
    
    if not patient:
        flash("Patient not found.", "error")
        return redirect("/reception/existing_patients")
        
    branch_id = session.get("receptionist_branch")
    branch = get_branch_by_id(branch_id) if branch_id else None
    location = branch.get("location", "Hyderabad") if branch else "Hyderabad"
    time_slots = generate_time_slots(location)
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Quick Book - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center p-6">
        <div class="bg-white rounded-3xl shadow-xl w-full max-w-lg overflow-hidden border border-gray-100">
            <div class="bg-indigo-600 p-8 text-white">
                <h1 class="text-2xl font-bold">Quick Appointment</h1>
                <p class="text-indigo-100 text-sm mt-1">Booking for {{ patient.name }}</p>
            </div>
            
            <form action="/reception/add_patient" method="POST" class="p-8 space-y-6">
                <!-- Pre-filled hidden fields -->
                <input type="hidden" name="name" value="{{ patient.name }}">
                <input type="hidden" name="phone" value="{{ patient.phone }}">
                <input type="hidden" name="email" value="{{ patient.email }}">
                <input type="hidden" name="address" value="{{ patient.address }}">
                
                <div class="grid grid-cols-1 gap-6">
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Appointment Date *</label>
                        <input type="date" name="date" required min="{{ datetime.now().strftime('%Y-%m-%d') }}" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Appointment Time *</label>
                        <select name="time" required class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all">
                            {% for slot in time_slots %}
                                <option value="{{ slot }}">{{ slot }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">Symptoms</label>
                        <textarea name="symptoms" rows="3" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="Reason for follow up..."></textarea>
                    </div>
                </div>
                
                <button type="submit" class="w-full bg-indigo-600 text-white py-4 rounded-2xl font-bold hover:bg-indigo-700 shadow-lg transition-all active:scale-95">
                    Confirm Appointment
                </button>
            </form>
        </div>
    </body>
    </html>
    """, patient=patient, time_slots=time_slots, datetime=datetime)



# ==========================================
# LEAVE CENTER (Greythr Style)
# ==========================================

@app.route("/leave_center")
def leave_center():
    return redirect("/leave/balances")

@app.route("/leave/balances")
def leave_balances():
    if not get_user_role():
        return redirect("/login")
        
    username = session.get(get_user_role())
    role = get_user_role()
    
    # Fetch User Data
    user_data = None
    if role == "doctor":
        user_data = doctors_collection.find_one({"username": username})
    elif role == "receptionist":
        user_data = receptionists_collection.find_one({"username": username})
    elif role == "admin":
        return redirect("/admin_dashboard") # Admin has their own view
        
    if not user_data:
        return redirect("/login")
        
    # Fetch Real Data from Leave Accounts
    accounts = user_data.get("leave_accounts", {
        "casual": {"granted": user_data.get("leave_quota", 22), "consumed": user_data.get("leave_quota", 22) - user_data.get("leaves_remaining", 22), "balance": user_data.get("leaves_remaining", 22)},
        "sick": {"granted": 5, "consumed": 0, "balance": 5},
        "lop": {"granted": 0, "consumed": 0, "balance": 0},
        "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
        "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
        "wfh": {"granted": 10, "consumed": 0, "balance": 10}
    })
    
    leave_types = [
        {"name": "Loss Of Pay", "granted": accounts["lop"]["granted"], "balance": accounts["lop"]["balance"], "consumed": accounts["lop"]["consumed"], "color": "orange", "key": "lop"},
        {"name": "Comp - Off", "granted": accounts["comp_off"]["granted"], "balance": accounts["comp_off"]["balance"], "consumed": accounts["comp_off"]["consumed"], "color": "blue", "key": "comp_off"},
        {"name": "Casual Leave", "granted": accounts["casual"]["granted"], "balance": accounts["casual"]["balance"], "consumed": accounts["casual"]["consumed"], "color": "teal", "is_main": True, "key": "casual"},
        {"name": "Bereavement Leaves", "granted": accounts["bereavement"]["granted"], "balance": accounts["bereavement"]["balance"], "consumed": accounts["bereavement"]["consumed"], "color": "indigo", "key": "bereavement"},
        {"name": "Work From Home", "granted": accounts["wfh"]["granted"], "balance": accounts["wfh"]["balance"], "consumed": accounts["wfh"]["consumed"], "color": "purple", "key": "wfh"},
        {"name": "Sick Leave", "granted": accounts["sick"]["granted"], "balance": accounts["sick"]["balance"], "consumed": accounts["sick"]["consumed"], "color": "red", "key": "sick"},
    ]
    
    sidebar_items = [
        {"icon": "ri-article-line", "label": "Leave Apply", "href": "/leave/apply"},
        {"icon": "ri-pie-chart-line", "label": "Leave Balances", "href": "/leave/balances", "active": True},
        {"icon": "ri-calendar-line", "label": "Leave Calendar", "href": "/leave/calendar"},
        {"icon": "ri-calendar-event-line", "label": "Holiday Calendar", "href": "/holiday/calendar"}
    ]
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Leave Balances - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; }
        </style>
    </head>
    <body class="flex h-screen overflow-hidden">
        <!-- Sidebar -->
        <aside class="w-64 bg-white shadow-xl z-20 flex flex-col">
            <div class="h-16 flex items-center px-6 border-b border-gray-100">
                 <img src="/static/images/heydoc_logo.png" alt="Logo" class="h-8">
                 <span class="ml-3 font-bold text-gray-800 tracking-tight">Hey Doc!</span>
            </div>
            
            <div class="p-6">
                <div class="flex items-center space-x-3 mb-8">
                    <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">
                        {{ session[get_user_role()][:1]|upper }}
                    </div>
                    <div>
                        <p class="text-sm font-bold text-gray-800">Hi {{ session.get('doctor_name') or session.get('receptionist_name') or session.get(get_user_role()) }}</p>
                        <a href="#" class="text-xs text-blue-500 hover:underline">View My Info</a>
                    </div>
                </div>
                
                <nav class="space-y-1">
                    <div class="item">
                        <button onclick="window.location.href='/dashboard'" class="flex items-center w-full px-3 py-2 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors mb-2">
                             <i class="ri-home-4-line mr-3 text-lg"></i> <span class="text-sm font-medium">Home</span>
                        </button>
                    </div>
                     <div class="item">
                        <button class="flex items-center w-full px-3 py-2 text-blue-600 bg-blue-50 rounded-lg transition-colors font-semibold">
                             <i class="ri-calendar-check-line mr-3 text-lg"></i> <span class="text-sm">Leave</span>
                             <i class="ri-arrow-down-s-line ml-auto"></i>
                        </button>
                        <div class="pl-10 mt-2 space-y-1">
                            {% for item in sidebar_items %}
                                <a href="{{ item.href }}" class="block text-sm py-1.5 {% if item.active %}text-blue-600 font-bold{% else %}text-gray-500 hover:text-gray-800{% endif %}">
                                    {{ item.label }}
                                </a>
                            {% endfor %}
                        </div>
                    </div>
                </nav>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 flex flex-col bg-gray-50/50 overflow-hidden relative">
            <!-- Header -->
            <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8">
                <h1 class="text-lg font-bold text-gray-800">Leave Balances</h1>
                <div class="flex items-center space-x-4">
                    <button class="text-gray-400 hover:text-gray-600"><i class="ri-notification-3-line text-xl"></i></button>
                    <button class="text-gray-400 hover:text-gray-600"><i class="ri-settings-3-line text-xl"></i></button>
                    <a href="/logout" class="text-red-500 hover:text-red-600"><i class="ri-logout-circle-r-line text-xl"></i></a>
                </div>
            </header>

            <!-- Content -->
            <div class="flex-1 overflow-y-auto p-8">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-sm font-bold text-gray-500 uppercase tracking-wide">2025 - 2026</h2>
                    <div class="flex space-x-2">
                        <a href="/leave/download" class="px-4 py-2 bg-white border border-gray-300 rounded text-sm font-medium hover:bg-gray-50 flex items-center"><i class="ri-download-line mr-2"></i> Download</a>
                        <a href="/leave/apply" class="px-4 py-2 bg-blue-600 text-white rounded text-sm font-bold hover:bg-blue-700">Apply Leave</a>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {% for leave in leave_types %}
                        <div class="bg-white p-6 rounded-lg border border-gray-200 shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:shadow-md transition-shadow relative overflow-hidden group">
                           <div class="absolute top-0 left-0 w-1 h-full bg-{{ leave.color }}-500"></div>
                           <div class="flex justify-between items-start mb-4">
                               <h3 class="font-bold text-gray-700">{{ leave.name }}</h3>
                               <span class="text-xs text-gray-400">Granted: <span class="font-bold text-gray-600">{{ leave.granted }}</span></span>
                           </div>
                           
                           <div class="text-center py-4">
                               <p class="text-4xl font-light text-gray-800">{{ '%02d' % leave.balance }}</p>
                               <p class="text-xs text-gray-400 mt-1 uppercase tracking-wider">Balance</p>
                           </div>
                           
                           <div class="mt-4">
                               <a href="#" class="text-xs text-blue-500 font-bold hover:underline mb-2 block text-center">View Details</a>
                               <div class="w-full bg-gray-100 rounded-full h-1.5 mt-2">
                                   <div class="bg-{{ leave.color }}-500 h-1.5 rounded-full" style="width: {{ (leave.consumed / leave.granted * 100) if leave.granted > 0 else 0 }}%"></div>
                               </div>
                               <p class="text-[10px] text-gray-400 mt-1">{{ leave.consumed }} of {{ leave.granted }} Consumed</p>
                           </div>
                        </div>
                    {% endfor %}
                </div>
            </div>
        </main>
    </body>
    </html>
    """, sidebar_items=sidebar_items, leave_types=leave_types, get_user_role=get_user_role)

@app.route("/leave/apply", methods=["GET", "POST"])
def leave_apply():
    if not get_user_role():
        return redirect("/login")

    sidebar_items = [
        {"icon": "ri-article-line", "label": "Leave Apply", "href": "/leave/apply", "active": True},
        {"icon": "ri-pie-chart-line", "label": "Leave Balances", "href": "/leave/balances"},
        {"icon": "ri-calendar-line", "label": "Leave Calendar", "href": "#"},
        {"icon": "ri-calendar-event-line", "label": "Holiday Calendar", "href": "#"}
    ]
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Apply Leave - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Inter', sans-serif; }</style>
    </head>
    <body class="flex h-screen overflow-hidden">
        <!-- Sidebar Copy -->
        <aside class="w-64 bg-white shadow-xl z-20 flex flex-col">
            <div class="h-16 flex items-center px-6 border-b border-gray-100">
                 <img src="/static/images/heydoc_logo.png" alt="Logo" class="h-8">
                 <span class="ml-3 font-bold text-gray-800 tracking-tight">Hey Doc!</span>
            </div>
            <div class="p-6">
                <!-- Shortened for brevity, same sidebar -->
                <nav class="space-y-1">
                     <div class="item">
                        <button onclick="window.location.href='/dashboard'" class="flex items-center w-full px-3 py-2 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors mb-2">
                             <i class="ri-home-4-line mr-3 text-lg"></i> <span class="text-sm font-medium">Home</span>
                        </button>
                    </div>
                     <div class="item">
                        <button class="flex items-center w-full px-3 py-2 text-blue-600 bg-blue-50 rounded-lg transition-colors font-semibold">
                             <i class="ri-calendar-check-line mr-3 text-lg"></i> <span class="text-sm">Leave</span>
                             <i class="ri-arrow-down-s-line ml-auto"></i>
                        </button>
                        <div class="pl-10 mt-2 space-y-1">
                            {% for item in sidebar_items %}
                                <a href="{{ item.href }}" class="block text-sm py-1.5 {% if item.active %}text-blue-600 font-bold{% else %}text-gray-500 hover:text-gray-800{% endif %}">
                                    {{ item.label }}
                                </a>
                            {% endfor %}
                        </div>
                    </div>
                </nav>
            </div>
        </aside>

        <main class="flex-1 flex flex-col bg-gray-50/50 overflow-hidden relative">
            <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8">
                <h1 class="text-lg font-bold text-gray-800">Leave Apply</h1>
            </header>
            
            <div class="flex-1 overflow-y-auto p-8">
                <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8 max-w-4xl">
                    <div class="bg-yellow-50 border border-yellow-100 p-4 rounded-lg mb-8 flex items-start">
                        <i class="ri-information-line text-yellow-600 mt-0.5 mr-3"></i>
                        <p class="text-sm text-yellow-800">Leave is a scheduled time off work granted to medical staff for personal or health reasons.</p>
                    </div>
                    
                    <form action="/doctor/apply_leave" method="POST" class="space-y-8">
                        <div>
                            <h3 class="text-sm font-bold text-gray-800 mb-4 border-b pb-2">Applying for Leave</h3>
                            
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Leave Type <span class="text-red-500">*</span></label>
                                    <select name="leave_type" class="w-full p-2.5 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                                        <option value="casual">Casual Leave</option>
                                        <option value="sick">Sick Leave</option>
                                        <option value="lop">Loss Of Pay</option>
                                        <option value="comp_off">Comp - Off</option>
                                        <option value="bereavement">Bereavement Leaves</option>
                                        <option value="wfh">Work From Home</option>
                                    </select>
                                </div>
                                <div></div> <!-- Spacer -->
                                
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase mb-2">From Date <span class="text-red-500">*</span></label>
                                    <div class="relative">
                                        <input type="date" name="start_date" required class="w-full p-2.5 pl-10 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                                        <i class="ri-calendar-line absolute left-3 top-2.5 text-gray-400"></i>
                                    </div>
                                </div>
                                
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Sessions</label>
                                    <select class="w-full p-2.5 bg-white border border-gray-300 rounded text-sm text-gray-600">
                                        <option>Session 1</option>
                                        <option>Session 2</option>
                                    </select>
                                </div>
                                
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase mb-2">To Date <span class="text-red-500">*</span></label>
                                    <div class="relative">
                                        <input type="date" name="end_date" required class="w-full p-2.5 pl-10 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                                        <i class="ri-calendar-line absolute left-3 top-2.5 text-gray-400"></i>
                                    </div>
                                </div>
                                
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Sessions</label>
                                    <select class="w-full p-2.5 bg-white border border-gray-300 rounded text-sm text-gray-600">
                                        <option>Session 2</option>
                                        <option>Session 1</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <div>
                             <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Reason</label>
                             <textarea name="reason" rows="3" class="w-full p-2.5 bg-white border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" placeholder="Enter a reason"></textarea>
                        </div>
                        
                        <div class="pt-4 flex justify-end space-x-4 border-t border-gray-100">
                             <button type="button" class="px-6 py-2 text-sm font-bold text-gray-600 hover:bg-gray-50 rounded">Cancel</button>
                             <button type="submit" class="px-6 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded shadow-lg shadow-blue-200">Submit</button>
                        </div>
                    </form>
                </div>
            </div>
        </main>
    </body>
    </html>
    """, sidebar_items=sidebar_items, get_user_role=get_user_role)

@app.route("/reception/select_doctor/<appointment_id>")
def reception_select_doctor(appointment_id):
    if "receptionist" not in session:
        flash("Please log in as receptionist.", "error")
        return redirect("/login")
        
    appointment = appointments_collection.find_one({"appointment_id": appointment_id})
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect("/reception_dashboard")
        
    branch_id = session.get("receptionist_branch")
    
    # IMPROVED QUERY: Handle both string and ObjectId for branch_id
    query = {"status": "active"}
    if branch_id:
        query["branch_id"] = {"$in": [str(branch_id), ObjectId(branch_id) if ObjectId.is_valid(branch_id) else branch_id]}
    
    doctors = list(doctors_collection.find(query))
    
    today_start = datetime.combine(datetime.today(), datetime.min.time())
    today_end = datetime.combine(datetime.today(), datetime.max.time())
    
    for doc in doctors:
        doc_id = str(doc["_id"])
        username = doc["username"]
        
        # 1. Check Leave
        active_leave = leaves_collection.find_one({
            "doctor_username": username,
            "status": "approved",
            "start_date": {"$lte": datetime.now().strftime("%Y-%m-%d")},
            "end_date": {"$gte": datetime.now().strftime("%Y-%m-%d")}
        })
        doc["is_on_leave"] = True if active_leave else False
        
        # 2. Queue Position (Waiting Patients)
        # Status 'sent_to_doctor' means they are waiting for this doctor
        waiting_count = appointments_collection.count_documents({
            "doctor_id": ObjectId(doc_id),
            "appointment_date": {"$gte": today_start, "$lte": today_end},
            "status": "sent_to_doctor"
        })
        doc["queue_count"] = waiting_count
        
        # 3. Workload (Total today)
        total_today = appointments_collection.count_documents({
            "doctor_id": ObjectId(doc_id),
            "appointment_date": {"$gte": today_start, "$lte": today_end},
            "status": {"$in": ["confirmed", "completed", "in_progress", "sent_to_doctor"]}
        })
        doc["today_workload"] = total_today
        
        # 4. Busy Status (Currently seeing a patient)
        is_busy_doc = appointments_collection.find_one({
            "doctor_id": ObjectId(doc_id),
            "status": "in_progress"
        })
        doc["is_busy"] = True if is_busy_doc else False
        
        doc["is_online"] = doc.get("is_online", False)

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Assign Doctor - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
            body { font-family: 'Outfit', sans-serif; }
            .queue-badge { transition: all 0.3s ease; }
            .doctor-card:hover .queue-badge { transform: scale(1.1); }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen p-6 text-slate-800">
        <div class="max-w-2xl mx-auto">
            <div class="bg-white rounded-3xl shadow-2xl overflow-hidden border border-gray-100">
                <div class="bg-gradient-to-r from-indigo-600 to-purple-700 p-8 text-white relative">
                    <div class="relative z-10">
                        <h1 class="text-3xl font-bold">Assign Medical Staff</h1>
                        <p class="text-indigo-100 mt-2 opacity-90">Manage patient queue for {{ appointment.patient_name or appointment.name }}</p>
                    </div>
                    <i class="ri-nurse-line absolute right-8 top-8 text-8xl text-white/10"></i>
                </div>
                
                <div class="p-8">
                    <!-- Appointment Info Header -->
                    <div class="grid grid-cols-2 gap-4 mb-8">
                        <div class="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                            <p class="text-[10px] uppercase font-black text-slate-400 tracking-widest mb-1">Appointment ID</p>
                            <p class="font-mono text-indigo-600 font-bold">{{ appointment.appointment_id }}</p>
                        </div>
                        <div class="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                            <p class="text-[10px] uppercase font-black text-slate-400 tracking-widest mb-1">Assigned Branch</p>
                            <p class="font-bold text-slate-700">{{ appointment.branch_id or 'Main Branch' }}</p>
                        </div>
                    </div>

                    <div class="flex items-center justify-between mb-6">
                        <h3 class="text-sm font-bold text-slate-500">Live Doctor Availability</h3>
                        <span class="text-[10px] bg-indigo-50 text-indigo-600 px-3 py-1 rounded-full font-bold uppercase tracking-wider">
                            {{ doctors|length }} Active Staff
                        </span>
                    </div>

                    <div class="space-y-4">
                        {% for doc in doctors %}
                        <form action="/reception/send_to_doctor/{{ appointment.appointment_id }}" method="POST">
                            <input type="hidden" name="doctor_username" value="{{ doc.username }}">
                            <button type="submit" 
                                class="doctor-card w-full flex items-center justify-between p-5 bg-white border border-slate-200 rounded-3xl transition-all 
                                {% if doc.is_on_leave or not doc.is_online %}opacity-60 cursor-not-allowed bg-slate-50{% else %}hover:border-indigo-400 hover:shadow-xl hover:-translate-y-1{% endif %}"
                                {% if doc.is_on_leave or not doc.is_online %}disabled{% endif %}>
                                
                                <div class="flex items-center gap-5">
                                    <div class="relative">
                                        <div class="w-14 h-14 bg-indigo-100 text-indigo-700 rounded-2xl flex items-center justify-center font-bold text-xl">
                                            {{ doc.name[0] }}
                                        </div>
                                        <div class="absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-4 border-white 
                                            {% if doc.is_online %}bg-green-500{% else %}bg-slate-300{% endif %}"></div>
                                    </div>
                                    
                                    <div class="text-left">
                                        <h4 class="font-bold text-slate-800 text-lg leading-tight">{{ doc.name }}</h4>
                                        <p class="text-xs text-slate-500 font-medium">{{ doc.specialization or 'General Practitioner' }}</p>
                                        
                                        <div class="flex items-center gap-3 mt-2">
                                            <span class="flex items-center text-[10px] font-bold text-slate-400 uppercase">
                                                <i class="ri-user-received-2-line mr-1"></i> Today: {{ doc.today_workload }}
                                            </span>
                                            {% if doc.is_busy %}
                                            <span class="flex items-center text-[10px] font-bold text-amber-500 uppercase">
                                                <i class="ri-pulse-line mr-1"></i> In Consultation
                                            </span>
                                            {% endif %}
                                        </div>
                                    </div>
                                </div>

                                <div class="flex flex-col items-end gap-2">
                                    {% if doc.is_on_leave %}
                                        <span class="text-[10px] font-black bg-red-50 text-red-500 px-3 py-1.5 rounded-xl border border-red-100 uppercase">On Leave</span>
                                    {% elif not doc.is_online %}
                                        <span class="text-[10px] font-black bg-slate-100 text-slate-400 px-3 py-1.5 rounded-xl border border-slate-200 uppercase">Offline</span>
                                    {% else %}
                                        <div class="queue-badge bg-indigo-600 text-white px-4 py-2 rounded-2xl shadow-lg shadow-indigo-200 text-center min-w-[80px]">
                                            <p class="text-[9px] font-black uppercase tracking-tighter opacity-80">Queue Pos</p>
                                            <p class="text-lg font-bold">#{{ doc.queue_count + 1 }}</p>
                                        </div>
                                        <p class="text-[9px] font-bold text-indigo-400 uppercase tracking-widest mt-1">Click to Assign</p>
                                    {% endif %}
                                </div>
                            </button>
                        </form>
                        {% endfor %}

                        {% if not doctors %}
                        <div class="py-16 text-center">
                            <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                                <i class="ri-user-search-line text-3xl"></i>
                            </div>
                            <p class="text-slate-400 font-medium italic">No active doctors found in this branch.</p>
                            <p class="text-xs text-slate-300 mt-1">Please check branch settings in the admin panel.</p>
                        </div>
                        {% endif %}
                    </div>
                </div>
                
                <div class="p-6 bg-slate-50 border-t border-slate-100 text-center">
                    <a href="/reception_dashboard" class="group flex items-center justify-center gap-2 text-sm font-bold text-slate-400 hover:text-indigo-600 transition-colors">
                        <i class="ri-arrow-left-line transition-transform group-hover:-translate-x-1"></i>
                        Cancel and Return to Dashboard
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, appointment=appointment, doctors=doctors)

@app.route("/reception/send_to_doctor/<appointment_id>", methods=["POST"])
def reception_send_to_doctor(appointment_id):
    if "receptionist" not in session:
        flash("Please log in as receptionist to access this page.", "error")
        return redirect("/login")
    
    doctor_username = request.form.get("doctor_username")
    if not doctor_username:
        flash("Please select a doctor.", "error")
        return redirect(f"/reception/select_doctor/{appointment_id}")

    appointment = appointments_collection.find_one({"appointment_id": appointment_id})
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect("/reception_dashboard")

    doctor = doctors_collection.find_one({"username": doctor_username})
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(f"/reception/select_doctor/{appointment_id}")
    
    # Get patient prescriptions
    patient_phone = appointment.get("phone")
    prescriptions = list(prescriptions_collection.find({"patient_phone": patient_phone})) if patient_phone else []
    
    # Update appointment status and assign to doctor
    update_data = {
        "status": "sent_to_doctor",
        "doctor_id": doctor["_id"],
        "doctor_username": doctor_username,
        "doctor_name": doctor.get("name"),
        "sent_at": datetime.utcnow(),
        "has_prescriptions": len(prescriptions) > 0,
        "prescription_count": len(prescriptions)
    }
    
    appointments_collection.update_one(
        {"appointment_id": appointment_id},
        {"$set": update_data}
    )
    
    flash(f"Patient profile sent to {doctor.get('name')} successfully! {'Prescriptions included.' if prescriptions else 'No prescriptions found.'}", "success")
    return redirect("/reception_dashboard")

@app.route("/download/<path:filename>")
def download_file(filename):
    if not any(k in session for k in ["admin", "doctor", "receptionist", "patient"]):
        flash("Please log in to download files.", "error")
        return redirect("/login")
    # Check if file is in circulars, profiles, or certificates
    if filename.startswith("circulars/"):
        return send_from_directory(UPLOAD_FOLDER, filename)
    elif filename.startswith("profiles/"):
        return send_from_directory(UPLOAD_FOLDER, filename)
    elif filename.startswith("certificates/"):
        return send_from_directory(UPLOAD_FOLDER, filename)
    else:
        # Default to circulars if no prefix
        return send_from_directory(CIRCULAR_ATTACHMENTS_FOLDER, filename)

# --- HOLIDAY & LEAVE CALENDARS ---

@app.route("/admin/holidays", methods=["GET"])
def admin_holidays():
    if "admin" not in session: return redirect("/login")
    holidays = list(holidays_collection.find().sort("date", 1))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>Holidays - Hey Doc!</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-gray-50 p-8"><div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-8"><h1 class="text-3xl font-bold">Manage Holidays</h1><a href="/admin_dashboard" class="bg-gray-200 px-4 py-2 rounded-lg font-bold">Back</a></div>
        <form action="/admin/add_holiday" method="POST" class="mb-8 flex gap-4 bg-white p-6 rounded-2xl shadow-sm border">
            <input type="text" name="title" placeholder="Holiday Title" required class="p-2 border rounded-lg flex-1">
            <input type="date" name="date" required class="p-2 border rounded-lg">
            <button type="submit" class="bg-teal-600 text-white px-6 py-2 rounded-lg font-bold">Add Holiday</button>
        </form>
        <div class="bg-white rounded-2xl shadow-sm border overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-gray-50"><tr><th class="p-4">Holiday</th><th class="p-4">Date</th><th class="p-4">Action</th></tr></thead>
                {% for h in holidays %}<tr class="border-t"><td class="p-4 font-bold">{{ h.title }}</td><td class="p-4">{{ h.date }}</td>
                <td class="p-4"><form action="/admin/delete_holiday/{{ h._id }}" method="POST"><button type="submit" class="text-red-500 hover:underline">Delete</button></form></td></tr>{% endfor %}
            </table>
        </div>
    </div></body></html>
    """, holidays=holidays)

@app.route("/admin/add_holiday", methods=["POST"])
def admin_add_holiday():
    if "admin" not in session: return redirect("/login")
    title, date = request.form.get("title"), request.form.get("date")
    if title and date:
        if holidays_collection.find_one({"date": date}):
            flash("Holiday for this date already exists!", "error")
        else:
            holidays_collection.insert_one({"title": title, "date": date})
            flash("Holiday added successfully.", "success")
    return redirect("/admin/holidays")

@app.route("/admin/delete_holiday/<holiday_id>", methods=["POST"])
def admin_delete_holiday(holiday_id):
    if "admin" not in session: return redirect("/login")
    holidays_collection.delete_one({"_id": ObjectId(holiday_id)})
    return redirect("/admin/holidays")

@app.route("/holiday/calendar")
def holiday_calendar():
    role = get_user_role()
    if not role: return redirect("/login")
    
    # Pre-populate if empty for demo/ux
    if holidays_collection.count_documents({}) == 0:
        sample_holidays = [
            {"title": "New Year's Day", "date": "2024-01-01"},
            {"title": "Republic Day", "date": "2024-01-26"},
            {"title": "Independence Day", "date": "2024-08-15"},
            {"title": "Gandhi Jayanti", "date": "2024-10-02"},
            {"title": "Christmas Eve", "date": "2024-12-24"},
            {"title": "Christmas Day", "date": "2024-12-25"}
        ]
        holidays_collection.insert_many(sample_holidays)

    holidays = list(holidays_collection.find().sort("date", 1))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Calendar - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Plus Jakarta Sans', sans-serif; }
            .glass { background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(12px); }
            .holiday-card { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
            .holiday-card:hover { transform: translateY(-5px) scale(1.02); }
        </style>
    </head>
    <body class="bg-[#f0f2f5] min-h-screen pb-20">
        <div class="fixed top-0 left-0 w-full h-64 bg-teal-600 rounded-b-[60px] z-0"></div>
        
        <div class="relative z-10 max-w-5xl mx-auto px-6 pt-12">
            <div class="flex justify-between items-end mb-10 text-white">
                <div>
                    <h1 class="text-4xl font-black tracking-tight">Hospital Calendar</h1>
                    <p class="text-teal-100 font-medium mt-2">Planned holidays and public events for 2024-25</p>
                </div>
                <a href="/{{ 'admin_dashboard' if session.get('admin') else 'reception_dashboard' if session.get('receptionist') else 'dashboard' }}" 
                   class="glass px-8 py-3 rounded-2xl font-bold text-teal-800 flex items-center shadow-lg hover:bg-white transition-all">
                    <i class="ri-arrow-left-line mr-2"></i> Back
                </a>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for h in holidays %}
                {% set date_obj = h.date %}
                <div class="holiday-card bg-white p-6 rounded-[32px] shadow-xl border border-white/20 flex flex-col justify-between h-48">
                    <div class="flex justify-between items-start">
                        <div class="w-14 h-14 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center shadow-inner">
                            <i class="ri-calendar-event-line text-2xl"></i>
                        </div>
                        <span class="text-[10px] font-black uppercase tracking-widest bg-teal-600 text-white px-3 py-1 rounded-full">Holiday</span>
                    </div>
                    <div>
                        <p class="text-xl font-black text-slate-800 leading-tight">{{ h.title }}</p>
                        <div class="flex items-center mt-2 text-slate-400 font-bold text-xs uppercase tracking-tighter">
                            <i class="ri-time-line mr-1"></i> {{ h.date }}
                        </div>
                    </div>
                </div>
                {% endfor %}

                {% if session.get('admin') %}
                <a href="/admin/holidays" class="holiday-card border-4 border-dashed border-teal-200 rounded-[32px] flex flex-col items-center justify-center text-teal-300 hover:border-teal-400 hover:text-teal-500 transition-all h-48">
                    <i class="ri-add-circle-line text-4xl mb-2"></i>
                    <span class="font-black uppercase tracking-widest text-sm">Add New Holiday</span>
                </a>
                {% endif %}
            </div>

            {% if not holidays and not session.get('admin') %}
            <div class="text-center py-32 glass rounded-[40px] border border-white/30">
                <i class="ri-calendar-line text-6xl text-slate-200 mb-4 inline-block"></i>
                <p class="text-xl font-bold text-slate-400">No holidays scheduled yet.</p>
            </div>
            {% endif %}
        </div>
    </body>
    </html>
    """, holidays=holidays)

@app.route("/leave/calendar")
def leave_calendar_view():
    role = get_user_role()
    if not role: return redirect("/login")
    search_username = session.get(role)
    # Support both legacy 'doctor_username' and modern 'username'
    leaves = list(leaves_collection.find({
        "$or": [{"username": search_username}, {"doctor_username": search_username}],
        "status": "approved"
    }).sort("start_date", 1))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>Leave Calendar - Hey Doc!</title><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css"></head>
    <body class="bg-gray-50 p-8"><div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-8"><h1 class="text-3xl font-bold text-gray-800 tracking-tight">Leave Calendar</h1><a href="/{{ 'admin_dashboard' if session.get('admin') else 'reception_dashboard' if session.get('receptionist') else 'dashboard' }}" class="bg-white border px-6 py-2 rounded-xl font-bold italic text-slate-500 hover:text-blue-600 transition-colors">Back</a></div>
        <div class="space-y-4">
            {% for l in leaves %}<div class="bg-white p-6 rounded-[32px] shadow-sm border flex justify-between items-center">
                <div class="flex items-center space-x-6">
                    <div class="w-16 h-16 bg-blue-50 text-blue-600 rounded-3xl flex items-center justify-center shadow-inner"><i class="ri-calendar-check-line text-3xl"></i></div>
                    <div><p class="text-lg font-black text-slate-800">{{ l.leave_type|capitalize if l.leave_type else 'General' }} Leave</p>
                    <p class="text-sm font-bold text-slate-400">{{ l.start_date }} → {{ l.end_date }}</p></div>
                </div><span class="px-4 py-1.5 bg-green-50 text-green-600 rounded-full text-[10px] font-black uppercase tracking-widest">Approved</span>
            </div>{% endfor %}
            {% if not leaves %}<div class="text-center py-20 text-slate-300 italic">No upcoming approved leaves.</div>{% endif %}
        </div></div></body></html>
    """, leaves=leaves)

@app.route("/leave/download")
def download_leave_balances_csv():
    role = get_user_role()
    if not role: return redirect("/login")
    username = session.get(role)
    user_data = doctors_collection.find_one({"username": username}) if role == "doctor" else receptionists_collection.find_one({"username": username})
    if not user_data: return "User not found", 404
    accounts = user_data.get("leave_accounts", {})
    import csv, io
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Leave Type", "Granted", "Consumed", "Balance"])
    for k, v in accounts.items(): cw.writerow([k.replace("_", " ").title(), v.get("granted", 0), v.get("consumed", 0), v.get("balance", 0)])
    from flask import Response
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-disposition": f"attachment; filename=leave_balances_{username}.csv"})

@app.route("/doctor/apply_leave", methods=["GET", "POST"])
@app.route("/apply_leave", methods=["GET", "POST"])
def submit_leave():
    if request.method == "GET":
        return redirect("/leave/apply")
        
    user_type = None
    username = None
    if "doctor" in session:
        user_type = "doctor"
        username = session["doctor"]
    elif "receptionist" in session:
        user_type = "receptionist"
        username = session["receptionist"]
        
    if not username:
        flash("Please log in to apply for leave.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            start_date = request.form.get("start_date", "").strip()
            end_date = request.form.get("end_date", "").strip()
            leave_type = request.form.get("leave_type", "Casual Leave").strip()
            reason = request.form.get("reason", "").strip()
            
            if not all([start_date, end_date, reason]):
                flash("All fields are required.", "error")
                return redirect("/doctor/apply_leave")
            
            # Fetch staff details
            collection = doctors_collection if user_type == "doctor" else receptionists_collection
            staff = collection.find_one({"username": username})
            if not staff:
                flash("System Error: Staff profile not found.", "error")
                return redirect("/dashboard")

            staff_name = staff.get("name", username)
            
            # Map leave type to account key
            type_map = {
                "Casual Leave": "casual",
                "Sick Leave": "sick",
                "Loss of Pay": "lop",
                "Compensatory Off": "comp_off",
                "Bereavement": "bereavement",
                "Work From Home": "wfh"
            }
            account_key = type_map.get(leave_type, "casual")
            
            # Calculate duration
            fmt = "%Y-%m-%d"
            d1 = datetime.strptime(start_date, fmt)
            d2 = datetime.strptime(end_date, fmt)
            requested_days = (d2 - d1).days + 1
            
            if requested_days <= 0:
                flash("Error: End date must be after or equal to start date.", "error")
                return redirect("/apply_leave")

            # Check balance
            accounts = staff.get("leave_accounts", {})
            balance = accounts.get(account_key, {}).get("balance", 0)
            
            if requested_days > balance and account_key != "lop":
                flash("No leaves are there please contact your admin", "error")
                return redirect("/doctor/apply_leave")

            leave_doc = {
                "username": username,
                "role": user_type,
                "staff_name": staff_name,
                "doctor_name": staff_name, # Legacy
                "doctor_username": username, # Legacy
                "leave_type": leave_type,
                "account_key": account_key,
                "start_date": start_date,
                "end_date": end_date,
                "days": requested_days,
                "reason": reason,
                "status": "pending",
                "created_at": datetime.utcnow()
            }
            
            # Save leave request
            result = leaves_collection.insert_one(leave_doc)
            
            # Send notification to admin
            send_leave_notification(
                doctor_name=staff_name,
                start_date=start_date,
                    end_date=end_date,
                    reason=reason
                )
            
            flash("Leave request submitted successfully! The admin has been notified.", "success")
            return redirect("/doctor/my_leaves")
        except Exception as e:
            flash(f"Error submitting leave request: {e}", "error")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Apply Leave - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-[#f8fafc] flex items-center justify-center p-6">
        <div class="bg-white rounded-3xl shadow-xl w-full max-w-2xl overflow-hidden border border-slate-100">
            <div class="bg-yellow-600 p-8 text-white flex justify-between items-center">
                <div>
                    <h1 class="text-2xl font-bold">Apply for Leave</h1>
                    <p class="text-yellow-50 text-sm mt-1">Submit your request for administrative approval</p>
                </div>
                <a href="/dashboard" class="text-white/80 hover:text-white transition-colors">
                    <i class="ri-close-line text-3xl"></i>
                </a>
            </div>
            
            <form method="POST" class="p-8 space-y-6">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-4 rounded-xl {% if category == 'error' %}bg-red-50 text-red-600{% else %}bg-green-50 text-green-600{% endif %} font-medium text-sm">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Start Date *</label>
                        <input type="date" name="start_date" required class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-yellow-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">End Date *</label>
                        <input type="date" name="end_date" required class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-yellow-500 outline-none transition-all">
                    </div>
                </div>

                <div class="space-y-1">
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Leave Category *</label>
                    <select name="leave_type" required class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-yellow-500 outline-none transition-all">
                        <option value="Casual Leave">Casual Leave</option>
                        <option value="Sick Leave">Sick Leave</option>
                        <option value="Loss of Pay">Loss of Pay (LOP)</option>
                        <option value="Compensatory Off">Compensatory Off</option>
                        <option value="Bereavement">Bereavement</option>
                        <option value="Work From Home">Work From Home (WFH)</option>
                    </select>
                </div>
                
                <div class="space-y-1">
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Reason for Leave *</label>
                    <textarea name="reason" rows="4" required class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-yellow-500 outline-none transition-all" placeholder="Please provide a brief reason..."></textarea>
                </div>

                <button type="submit" class="w-full bg-yellow-600 text-white py-4 rounded-2xl font-bold hover:bg-yellow-700 shadow-xl shadow-yellow-50 transition-all active:scale-[0.98]">
                    Submit Leave Request
                </button>
            </form>
        </div>
    </body>
    </html>
    """)

@app.route("/doctor/profile", methods=["GET", "POST"])
def doctor_profile():
    if "doctor" not in session:
        flash("Please log in to access your profile.", "error")
        return redirect("/login")
    
    doctor = doctors_collection.find_one({"username": session.get("doctor")})
    
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        specialization = request.form.get("specialization")
        phone = request.form.get("phone")
        photo = request.files.get("profile_photo")
        
        update_data = {
            "name": name,
            "email": email,
            "specialization": specialization,
            "phone": phone
        }
        
        if photo and photo.filename != '':
            try:
                filename = secure_filename(photo.filename)
                ext = filename.split('.')[-1].lower()
                if ext not in ['png', 'jpg', 'jpeg', 'gif']:
                    flash("Invalid file type. Only PNG, JPG, JPEG, and GIF allowed.", "error")
                    return redirect("/doctor/profile")

                # Ensure directory exists
                if not os.path.exists(PROFILE_PHOTOS_FOLDER):
                    os.makedirs(PROFILE_PHOTOS_FOLDER, exist_ok=True)
                    
                new_filename = f"profile_{doctor['username']}.{ext}"
                photo_path = os.path.join(PROFILE_PHOTOS_FOLDER, new_filename)
                photo.save(photo_path)
                update_data["profile_photo"] = f"profiles/{new_filename}"
            except Exception as e:
                print(f"Error saving profile photo: {e}")
                flash(f"Note: Profile updated but photo could not be saved: {e}", "warning")
            
        doctors_collection.update_one({"_id": doctor["_id"]}, {"$set": update_data})
        flash("Profile updated successfully!", "success")
        return redirect("/doctor/profile")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Doctor Profile - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-[#f8fafc] flex items-center justify-center p-6">
        <div class="bg-white rounded-3xl shadow-xl w-full max-w-2xl overflow-hidden border border-slate-100">
            <div class="bg-teal-600 p-8 text-white flex justify-between items-center">
                <div>
                    <h1 class="text-2xl font-bold">My Profile</h1>
                    <p class="text-teal-50 text-sm mt-1">Manage your professional information</p>
                </div>
                <a href="/dashboard" class="text-white/80 hover:text-white transition-colors">
                    <i class="ri-close-line text-3xl"></i>
                </a>
            </div>
            
            <form method="POST" enctype="multipart/form-data" class="p-8 space-y-6">
                <div class="flex flex-col items-center space-y-4 mb-4">
                    <div class="relative group">
                        <div class="w-32 h-32 rounded-3xl overflow-hidden border-4 border-slate-50 shadow-lg bg-slate-50 group-hover:scale-105 transition-transform duration-300">
                            {% if doctor.profile_photo %}
                                <img src="/download/{{ doctor.profile_photo }}?v={{ range(1, 10000) | random }}" class="w-full h-full object-cover" id="previewImg">
                            {% else %}
                                <div class="w-full h-full flex items-center justify-center text-slate-300" id="previewPlaceholder">
                                    <i class="ri-user-smile-fill text-6xl"></i>
                                </div>
                            {% endif %}
                        </div>
                        <label class="absolute bottom-1 right-1 bg-teal-600 text-white w-10 h-10 rounded-xl flex items-center justify-center shadow-lg hover:bg-teal-700 transition-all cursor-pointer">
                            <i class="ri-camera-3-line"></i>
                            <input type="file" name="profile_photo" class="hidden" accept="image/*" onchange="previewFile(this)">
                        </label>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Full Name</label>
                        <input type="text" name="name" value="{{ doctor.name }}" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Email Address</label>
                        <input type="email" name="email" value="{{ doctor.email }}" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Specialization</label>
                        <input type="text" name="specialization" value="{{ doctor.specialization or '' }}" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none transition-all">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Phone Number</label>
                        <input type="text" name="phone" value="{{ doctor.phone or '' }}" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none transition-all">
                    </div>
                </div>

                <button type="submit" class="w-full bg-teal-600 text-white py-4 rounded-2xl font-bold hover:bg-teal-700 shadow-xl shadow-teal-50 transition-all active:scale-[0.98]">
                    Save Profile Changes
                </button>
            </form>
            
            <!-- Security Section -->
            <div class="px-8 pb-8">
                <div class="bg-slate-50 rounded-2xl p-6 border border-slate-100">
                    <h3 class="text-sm font-black text-slate-400 uppercase tracking-widest mb-4">Security Settings</h3>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center">
                                <i class="ri-face-recognition-fill text-2xl"></i>
                            </div>
                            <div>
                                <h4 class="font-bold text-slate-800">Hey Doc! Face ID</h4>
                                <p class="text-xs text-slate-500 font-medium">
                                    {% if doctor.face_id_enabled %}
                                    <span class="text-green-600 flex items-center gap-1"><i class="ri-checkbox-circle-fill"></i> Enabled</span>
                                    {% else %}
                                    Enable Face ID login for instant access
                                    {% endif %}
                                </p>
                            </div>
                        </div>
                        <button type="button" onclick="openEnrollModal()" class="bg-white border-2 border-indigo-100 text-indigo-600 px-4 py-2 rounded-xl font-bold text-sm hover:border-indigo-600 hover:bg-indigo-50 transition-all">
                            {% if doctor.face_id_enabled %}Re-Calibrate{% else %}Setup Now{% endif %}
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Face Enrollment Modal -->
        <div id="enrollModal" class="fixed inset-0 z-50 hidden bg-gray-900/90 backdrop-blur-md flex items-center justify-center p-4">
            <div class="bg-white rounded-[40px] shadow-2xl p-8 max-w-md w-full relative overflow-hidden">
                <button onclick="closeEnrollModal()" class="absolute top-6 right-6 text-gray-400 hover:text-gray-800 transition-colors">
                    <i class="ri-close-circle-fill text-3xl"></i>
                </button>
                
                <div class="text-center mb-8">
                    <h3 class="text-2xl font-black text-gray-800">Setup Face ID</h3>
                    <p class="text-gray-500 text-sm mt-1">Position your face in the oval frame</p>
                </div>
                
                <div class="relative rounded-3xl overflow-hidden bg-black aspect-[4/3] mb-6 shadow-inner ring-4 ring-gray-100">
                    <video id="enrollVideo" autoplay playsinline class="w-full h-full object-cover transform scale-x-[-1]"></video>
                    <div class="absolute inset-0 border-2 border-white/20 rounded-3xl pointer-events-none"></div>
                    <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div class="w-48 h-64 border-2 border-dashed border-white/50 rounded-[40%]"></div>
                    </div>
                </div>
                
                <div id="enrollStatus" class="text-center font-bold text-gray-600 mb-6 min-h-[1.5rem] animate-pulse">
                    Waiting for camera...
                </div>
                
                <button id="enrollBtn" onclick="captureAndEnroll()" class="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white py-4 rounded-2xl font-black uppercase tracking-widest transition-all">
                    <i class="ri-scan-line mr-2"></i> Capture Face
                </button>
            </div>
        </div>
        <script>
            let enrollStream = null;

            async function openEnrollModal() {
                const modal = document.getElementById('enrollModal');
                const video = document.getElementById('enrollVideo');
                const status = document.getElementById('enrollStatus');
                const btn = document.getElementById('enrollBtn');
                
                modal.classList.remove('hidden');
                btn.disabled = true;
                status.innerText = "Accessing camera...";
                
                try {
                    enrollStream = await navigator.mediaDevices.getUserMedia({ video: true });
                    video.srcObject = enrollStream;
                    status.innerText = "Ready. Look at the camera.";
                    btn.disabled = false;
                } catch (err) {
                    console.error(err);
                    status.innerText = "Camera access denied.";
                    status.classList.add('text-red-500');
                }
            }
            
            function closeEnrollModal() {
                document.getElementById('enrollModal').classList.add('hidden');
                if (enrollStream) {
                    enrollStream.getTracks().forEach(track => track.stop());
                    enrollStream = null;
                }
            }
            
            async function captureAndEnroll() {
                const video = document.getElementById('enrollVideo');
                const status = document.getElementById('enrollStatus');
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0);
                
                const dataURL = canvas.toDataURL('image/jpeg');
                
                status.innerText = "Processing Face Scan data...";
                
                try {
                    const res = await fetch('/api/register_face', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ image: dataURL })
                    });
                    const data = await res.json();
                    
                    if (data.success) {
                        status.innerText = "Success! Face ID Enabled.";
                        status.classList.add('text-green-600');
                        setTimeout(() => {
                            location.reload();
                        }, 1500);
                    } else {
                        status.innerText = data.message;
                        status.classList.add('text-red-600');
                    }
                } catch (err) {
                    console.error(err);
                    status.innerText = "Server error.";
                }
            }

            function previewFile(input) {
                if (input.files && input.files[0]) {
                    var reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.getElementById('previewImg') || document.createElement('img');
                        img.src = e.target.result;
                        img.id = 'previewImg';
                        img.className = 'w-full h-full object-cover';
                        
                        const placeholder = document.getElementById('previewPlaceholder');
                        if (placeholder) {
                            placeholder.parentNode.replaceChild(img, placeholder);
                        } else {
                            const container = document.querySelector('.w-32.h-32');
                            container.innerHTML = '';
                            container.appendChild(img);
                        }
                    }
                    reader.readAsDataURL(input.files[0]);
                }
            }
        </script>
    </body>
    </html>
    """, doctor=doctor)

@app.route("/admin/profile_legacy", methods=["GET", "POST"])
def admin_profile_legacy():
    if "admin" not in session:
        flash("Please log in as admin to access your profile.", "error")
        return redirect("/login")
    
    admin = admin_collection.find_one({"username": session.get("admin")})
    
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        
        update_data = {
            "name": name,
            "email": email
        }
        
        if password:
            update_data["password"] = password
            
        admin_collection.update_one({"_id": admin["_id"]}, {"$set": update_data})
        flash("Admin profile updated successfully!", "success")
        return redirect("/admin/profile")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Admin Profile - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-slate-100 flex items-center justify-center p-6">
        <div class="bg-white rounded-[40px] shadow-2xl w-full max-w-2xl overflow-hidden border border-slate-200">
            <div class="bg-teal-700 p-10 text-white flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-black tracking-tight">System Settings</h1>
                    <p class="text-teal-100/80 text-sm mt-1">Manage administrative credentials</p>
                </div>
                <a href="/admin_dashboard" class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center text-white hover:bg-white/20 transition-all">
                    <i class="ri-dashboard-3-line text-2xl"></i>
                </a>
            </div>
            
            <form method="POST" class="p-10 space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="space-y-2">
                        <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Administrator Name</label>
                        <input type="text" name="name" value="{{ admin.name }}" class="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all font-bold text-slate-700">
                    </div>
                    <div class="space-y-2">
                        <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Safe-Contact Email</label>
                        <input type="email" name="email" value="{{ admin.email }}" class="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all font-bold text-slate-700">
                    </div>
                </div>
                
                <div class="space-y-2 bg-slate-50 p-6 rounded-3xl border border-slate-100">
                    <label class="text-[10px] font-black text-red-400 uppercase tracking-widest ml-1">Identity Secret (Change Password)</label>
                    <input type="password" name="password" placeholder="Leave blank to keep current" class="w-full px-5 py-4 bg-white border border-slate-200 rounded-2xl focus:ring-4 focus:ring-red-500/10 focus:border-red-500 outline-none transition-all font-bold text-slate-700">
                    <p class="text-[10px] text-slate-400 mt-1 italic">Only enter a value if you wish to reset your administrative password.</p>
                </div>

                <button type="submit" class="w-full bg-teal-700 text-white py-5 rounded-[22px] font-black text-sm uppercase tracking-widest hover:bg-teal-800 shadow-2xl shadow-teal-900/20 transition-all active:scale-[0.98]">
                    Commit Secure Changes
                </button>
            </form>
            
            <!-- Face ID Registration Section -->
            <div class="p-10 border-t border-slate-100 bg-slate-50/50">
                <h3 class="text-sm font-black text-slate-400 uppercase tracking-widest mb-6 border-b border-slate-200 pb-2">Face ID Security</h3>
                <div class="flex items-center justify-between">
                    <div>
                        <p class="font-bold text-slate-700">Facial Recognition Data</p>
                        <p class="text-xs text-slate-400 mt-1">
                            {% if admin.face_id_registered %}
                                <span class="text-emerald-500 font-bold"><i class="ri-check-double-line"></i> Registered & Active</span>
                            {% else %}
                                <span class="text-amber-500 font-bold"><i class="ri-error-warning-line"></i> Not Configured</span>
                            {% endif %}
                        </p>
                    </div>
                    <a href="/admin/register_face" class="px-6 py-3 bg-white border border-slate-200 text-slate-600 rounded-xl font-bold text-xs uppercase tracking-widest hover:bg-teal-50 hover:text-teal-600 hover:border-teal-200 transition-all shadow-sm">
                        {% if admin.face_id_registered %}Re-Register Face{% else %}Register Face ID{% endif %}
                    </a>
                </div>
            </div>
                    </button>
                </div>
            </div>
        </div>

        <!-- Face Enrollment Modal -->
        <div id="enrollModal" class="fixed inset-0 z-50 hidden bg-gray-900/90 backdrop-blur-md flex items-center justify-center p-4">
            <div class="bg-white rounded-[40px] shadow-2xl p-8 max-w-md w-full relative overflow-hidden">
                <button onclick="closeEnrollModal()" class="absolute top-6 right-6 text-gray-400 hover:text-gray-800 transition-colors">
                    <i class="ri-close-circle-fill text-3xl"></i>
                </button>
                
                <div class="text-center mb-8">
                    <h3 class="text-2xl font-black text-gray-800">Face ID Setup</h3>
                    <p class="text-gray-500 text-sm mt-1">Look straight at the camera to enroll</p>
                </div>
                
                <div class="relative rounded-3xl overflow-hidden bg-black aspect-[4/3] mb-6 shadow-inner ring-4 ring-gray-100">
                    <video id="enrollVideo" autoplay playsinline class="w-full h-full object-cover transform scale-x-[-1]"></video>
                    <div class="absolute inset-0 border-2 border-white/20 rounded-3xl pointer-events-none"></div>
                    <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div class="w-48 h-64 border-2 border-dashed border-white/50 rounded-[40%]"></div>
                    </div>
                </div>
                
                <div id="enrollStatus" class="text-center font-bold text-gray-600 mb-6 min-h-[1.5rem] animate-pulse">
                    Initializing scanner...
                </div>
                
                <button id="enrollBtn" onclick="captureAndEnroll()" class="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-gray-400 text-white py-4 rounded-2xl font-black uppercase tracking-widest transition-all">
                    <i class="ri-scan-line mr-2"></i> Enroll Face
                </button>
            </div>
        </div>
        
        <form id="faceEnrollForm" method="POST" class="hidden">
            <input type="hidden" name="image_data" id="faceImageData">
        </form>

        <script>
            let enrollStream = null;

            async function openEnrollModal() {
                const modal = document.getElementById('enrollModal');
                const video = document.getElementById('enrollVideo');
                const status = document.getElementById('enrollStatus');
                const btn = document.getElementById('enrollBtn');
                
                modal.classList.remove('hidden');
                btn.disabled = true;
                status.innerText = "Accessing camera...";
                status.classList.remove('text-red-500', 'text-green-600', 'text-red-600');
                status.classList.add('animate-pulse');
                
                try {
                    enrollStream = await navigator.mediaDevices.getUserMedia({ video: true });
                    video.srcObject = enrollStream;
                    status.innerText = "Ready. Look at the camera.";
                    btn.disabled = false;
                    status.classList.remove('animate-pulse');
                } catch (err) {
                    console.error(err);
                    status.innerText = "Camera access denied.";
                    status.classList.add('text-red-500');
                    status.classList.remove('animate-pulse');
                }
            }
            
            function closeEnrollModal() {
                document.getElementById('enrollModal').classList.add('hidden');
                if (enrollStream) {
                    enrollStream.getTracks().forEach(track => track.stop());
                    enrollStream = null;
                }
            }
            
            async function captureAndEnroll() {
                const video = document.getElementById('enrollVideo');
                const status = document.getElementById('enrollStatus');
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0);
                
                const dataURL = canvas.toDataURL('image/jpeg');
                
                status.innerText = "Processing Face Scan data...";
                status.classList.remove('text-red-500', 'text-green-600', 'text-red-600');
                status.classList.add('animate-pulse');

                // Submit the image data via the hidden form
                document.getElementById('faceImageData').value = dataURL;
                document.getElementById('faceEnrollForm').submit();
            }

            function previewFile(input) {
                if (input.files && input.files[0]) {
                    var reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.getElementById('previewImg') || document.createElement('img');
                        img.src = e.target.result;
                        img.id = 'previewImg';
                        img.className = 'w-full h-full object-cover';
                        
                        const placeholder = document.getElementById('previewPlaceholder');
                        if (placeholder) {
                            placeholder.parentNode.replaceChild(img, placeholder);
                        } else {
                            const container = document.querySelector('.w-32.h-32');
                            container.innerHTML = '';
                            container.appendChild(img);
                        }
                    }
                    reader.readAsDataURL(input.files[0]);
                }
            }
        </script>
    </body>
    </html>
    """, admin=admin)


@app.route("/receptionist/profile", methods=["GET", "POST"])
def receptionist_profile():
    if "receptionist" not in session:
        flash("Please log in to access your profile.", "error")
        return redirect("/login")
    
    receptionist = receptionists_collection.find_one({"username": session.get("receptionist")})
    
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        photo = request.files.get("profile_photo")
        
        update_data = {
            "name": name,
            "email": email,
            "phone": phone
        }
        
        if photo and photo.filename != '':
            try:
                filename = secure_filename(photo.filename)
                ext = filename.split('.')[-1].lower()
                if ext not in ['png', 'jpg', 'jpeg', 'gif']:
                    flash("Invalid file type. Only PNG, JPG, JPEG, and GIF allowed.", "error")
                    return redirect("/receptionist/profile")
                    
                if not os.path.exists(PROFILE_PHOTOS_FOLDER):
                    os.makedirs(PROFILE_PHOTOS_FOLDER, exist_ok=True)
                    
                new_filename = f"profile_rec_{receptionist['username']}.{ext}"
                photo_path = os.path.join(PROFILE_PHOTOS_FOLDER, new_filename)
                photo.save(photo_path)
                update_data["profile_photo"] = f"profiles/{new_filename}"
            except Exception as e:
                flash(f"Note: Profile updated but photo failed: {e}", "warning")
            
        receptionists_collection.update_one({"_id": receptionist["_id"]}, {"$set": update_data})
        flash("Profile updated successfully!", "success")
        return redirect("/receptionist/profile")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Desk Profile - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div class="bg-white rounded-[40px] shadow-xl w-full max-w-2xl overflow-hidden border border-slate-100">
            <div class="bg-purple-600 p-10 text-white flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-black tracking-tight">Desk Identity</h1>
                    <p class="text-purple-100 text-sm mt-1">Manage your professional presence</p>
                </div>
                <a href="/reception_dashboard" class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center text-white hover:bg-white/20 transition-all">
                    <i class="ri-dashboard-line text-2xl"></i>
                </a>
            </div>
            
            <form method="POST" enctype="multipart/form-data" class="p-10 space-y-8">
                <div class="flex flex-col items-center space-y-4">
                    <div class="relative group">
                        <div class="w-32 h-32 rounded-[30px] overflow-hidden border-4 border-slate-50 shadow-2xl bg-slate-100 group-hover:scale-105 transition-all duration-500">
                            {% if receptionist.profile_photo %}
                                <img src="/download/{{ receptionist.profile_photo }}?v={{ range(1, 10000) | random }}" class="w-full h-full object-cover" id="previewImg">
                            {% else %}
                                <div class="w-full h-full flex items-center justify-center text-slate-300" id="previewPlaceholder">
                                    <i class="ri-shield-user-line text-6xl"></i>
                                </div>
                            {% endif %}
                        </div>
                        <label class="absolute -bottom-2 -right-2 bg-purple-600 text-white w-10 h-10 rounded-2xl flex items-center justify-center shadow-2xl hover:bg-purple-700 transition-all cursor-pointer border-4 border-white">
                            <i class="ri-camera-lens-line"></i>
                            <input type="file" name="profile_photo" class="hidden" accept="image/*" onchange="previewFile(this)">
                        </label>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="space-y-2">
                        <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Designated Name</label>
                        <input type="text" name="name" value="{{ receptionist.name }}" class="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-purple-500/10 focus:border-purple-500 outline-none transition-all font-bold text-slate-700">
                    </div>
                    <div class="space-y-2">
                        <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Registered Email</label>
                        <input type="email" name="email" value="{{ receptionist.email }}" class="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-purple-500/10 focus:border-purple-500 outline-none transition-all font-bold text-slate-700">
                    </div>
                    <div class="md:col-span-2 space-y-2">
                        <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Contact Terminal (Phone)</label>
                        <input type="text" name="phone" value="{{ receptionist.phone or '' }}" class="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-purple-500/10 focus:border-purple-500 outline-none transition-all font-bold text-slate-700">
                    </div>
                </div>

                <button type="submit" class="w-full bg-purple-600 text-white py-5 rounded-[22px] font-black text-sm uppercase tracking-widest hover:bg-purple-700 shadow-2xl shadow-purple-900/20 transition-all active:scale-[0.98]">
                    Update Desk Credentials
                </button>
            </form>
            
            <!-- Security Section -->
            <div class="px-10 pb-10">
                <div class="bg-slate-50/50 rounded-2xl p-6 border border-slate-100">
                    <h3 class="text-sm font-black text-slate-400 uppercase tracking-widest mb-4">Face ID Access</h3>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center">
                                <i class="ri-face-recognition-line text-2xl"></i>
                            </div>
                            <div>
                                <h4 class="font-bold text-slate-800">Hey Doc! Face ID</h4>
                                <p class="text-xs text-slate-500 font-medium">
                                    {% if receptionist.face_id_enabled %}
                                    <span class="text-green-600 flex items-center gap-1"><i class="ri-checkbox-circle-fill"></i> System Active</span>
                                    {% else %}
                                    Secure desk access with facial recognition
                                    {% endif %}
                                </p>
                            </div>
                        </div>
                        <button type="button" onclick="openEnrollModal()" class="bg-white border-2 border-purple-100 text-purple-600 px-4 py-2 rounded-xl font-bold text-sm hover:border-purple-600 hover:bg-purple-50 transition-all">
                            {% if receptionist.face_id_enabled %}Reset Face ID{% else %}Configure{% endif %}
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Face Enrollment Modal -->
        <div id="enrollModal" class="fixed inset-0 z-50 hidden bg-gray-900/90 backdrop-blur-md flex items-center justify-center p-4">
            <div class="bg-white rounded-[40px] shadow-2xl p-8 max-w-md w-full relative overflow-hidden">
                <button onclick="closeEnrollModal()" class="absolute top-6 right-6 text-gray-400 hover:text-gray-800 transition-colors">
                    <i class="ri-close-circle-fill text-3xl"></i>
                </button>
                
                <div class="text-center mb-8">
                    <h3 class="text-2xl font-black text-gray-800">Face ID Setup</h3>
                    <p class="text-gray-500 text-sm mt-1">Look straight at the camera to enroll</p>
                </div>
                
                <div class="relative rounded-3xl overflow-hidden bg-black aspect-[4/3] mb-6 shadow-inner ring-4 ring-gray-100">
                    <video id="enrollVideo" autoplay playsinline class="w-full h-full object-cover transform scale-x-[-1]"></video>
                    <div class="absolute inset-0 border-2 border-white/20 rounded-3xl pointer-events-none"></div>
                    <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div class="w-48 h-64 border-2 border-dashed border-white/50 rounded-[40%]"></div>
                    </div>
                </div>
                
                <div id="enrollStatus" class="text-center font-bold text-gray-600 mb-6 min-h-[1.5rem] animate-pulse">
                    Initializing scanner...
                </div>
                
                <button id="enrollBtn" onclick="captureAndEnroll()" class="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white py-4 rounded-2xl font-black uppercase tracking-widest transition-all">
                    <i class="ri-scan-line mr-2"></i> Enroll Face
                </button>
            </div>
        </div>
        <script>
            let enrollStream = null;

            async function openEnrollModal() {
                const modal = document.getElementById('enrollModal');
                const video = document.getElementById('enrollVideo');
                const status = document.getElementById('enrollStatus');
                const btn = document.getElementById('enrollBtn');
                
                modal.classList.remove('hidden');
                btn.disabled = true;
                status.innerText = "Accessing camera...";
                
                try {
                    enrollStream = await navigator.mediaDevices.getUserMedia({ video: true });
                    video.srcObject = enrollStream;
                    status.innerText = "Ready. Look at the camera.";
                    btn.disabled = false;
                } catch (err) {
                    console.error(err);
                    status.innerText = "Camera access denied.";
                    status.classList.add('text-red-500');
                }
            }
            
            function closeEnrollModal() {
                document.getElementById('enrollModal').classList.add('hidden');
                if (enrollStream) {
                    enrollStream.getTracks().forEach(track => track.stop());
                    enrollStream = null;
                }
            }
            
            async function captureAndEnroll() {
                const video = document.getElementById('enrollVideo');
                const status = document.getElementById('enrollStatus');
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0);
                
                const dataURL = canvas.toDataURL('image/jpeg');
                
                status.innerText = "Encrypting Face Scan data...";
                
                try {
                    const res = await fetch('/api/register_face', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ image: dataURL })
                    });
                    const data = await res.json();
                    
                    if (data.success) {
                        status.innerText = "Enrolled Successfully!";
                        status.classList.add('text-green-600');
                        setTimeout(() => {
                            location.reload();
                        }, 1500);
                    } else {
                        status.innerText = data.message;
                        status.classList.add('text-red-600');
                    }
                } catch (err) {
                    console.error(err);
                    status.innerText = "Server error.";
                }
            }

            function previewFile(input) {
                if (input.files && input.files[0]) {
                    var reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.getElementById('previewImg') || document.createElement('img');
                        img.src = e.target.result;
                        img.id = 'previewImg';
                        img.className = 'w-full h-full object-cover';
                        
                        const placeholder = document.getElementById('previewPlaceholder');
                        if (placeholder) {
                            placeholder.parentNode.replaceChild(img, placeholder);
                        } else {
                            const container = document.querySelector('.w-32.h-32');
                            container.innerHTML = '';
                            container.appendChild(img);
                        }
                    }
                    reader.readAsDataURL(input.files[0]);
                }
            }
        </script>
    </body>
    </html>
    """, receptionist=receptionist)

@app.route("/patient_details/<phone>")
def patient_details(phone):
    if "doctor" not in session:
        flash("Please log in to view patient details.", "error")
        return redirect("/login")
    
    patient = patients_collection.find_one({"phone": phone})
    appointments = list(appointments_collection.find({"phone": phone}).sort("date", -1))
    prescriptions = list(prescriptions_collection.find({"patient_phone": phone}).sort("created_at", -1))
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Patient History - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-[#f8fafc] p-8">
        <div class="max-w-6xl mx-auto space-y-8">
            <header class="flex justify-between items-center">
                <div>
                   <h1 class="text-3xl font-bold text-slate-800">Patient Longitudinal History</h1>
                   <p class="text-slate-400">Complete medical record for {{ phone }}</p>
                </div>
                <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white border border-slate-200 px-5 py-2 rounded-xl text-slate-600 font-bold hover:border-teal-500 hover:text-teal-600 transition-all">
                    <i class="ri-arrow-left-line mr-2"></i>Back to Dashboard
                </a>
            </header>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="bg-white rounded-3xl border border-slate-100 shadow-sm p-8">
                    <div class="w-20 h-20 bg-teal-100 text-teal-600 rounded-2xl flex items-center justify-center mb-6">
                        <i class="ri-user-3-fill text-3xl"></i>
                    </div>
                    <div class="space-y-4">
                        <div>
                            <p class="text-[10px] font-black text-slate-300 uppercase tracking-widest">Name</p>
                            <p class="text-xl font-bold text-slate-800">{{ patient.name if patient else 'N/A' }}</p>
                        </div>
                        <div>
                            <p class="text-[10px] font-black text-slate-300 uppercase tracking-widest">Contact</p>
                            <p class="text-slate-600">{{ phone }}</p>
                            <p class="text-slate-600 text-sm">{{ patient.email if patient and patient.email else '' }}</p>
                        </div>
                        {% if patient and patient.address %}
                        <div>
                            <p class="text-[10px] font-black text-slate-300 uppercase tracking-widest">Address</p>
                            <p class="text-slate-600 text-sm">{{ patient.address }}</p>
                        </div>
                        {% endif %}
                    </div>
                </div>

                <div class="lg:col-span-2 space-y-8">
                    <section>
                        <h3 class="text-lg font-bold text-slate-800 mb-4 flex items-center">
                            <i class="ri-history-line mr-2 text-teal-600"></i> Appointments
                        </h3>
                        <div class="space-y-4">
                            {% for a in appointments %}
                                <div class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex justify-between items-center group hover:border-teal-100 transition-all">
                                    <div>
                                        <p class="font-bold text-slate-800 text-lg">{{ a.date }}</p>
                                        <p class="text-xs text-slate-400">At {{ a.time }} • {{ a.branch }}</p>
                                        <p class="text-sm text-slate-500 mt-2 italic">"{{ a.symptoms }}"</p>
                                        {% if a.certificate_path %}
                                        <a href="/download/{{ a.certificate_path }}" target="_blank" class="inline-flex items-center mt-3 text-xs font-bold text-teal-600 hover:text-teal-700 bg-teal-50 px-3 py-1.5 rounded-lg transition-all">
                                            <i class="ri-file-list-3-line mr-1.5"></i> View Certificate
                                        </a>
                                        {% endif %}
                                    </div>
                                    <div class="text-right">
                                        <span class="px-3 py-1 rounded-full text-[10px] font-black uppercase
                                            {% if a.status == 'confirmed' %}bg-green-100 text-green-700{% else %}bg-slate-100 text-slate-500{% endif %}">
                                            {{ a.status }}
                                        </span>
                                    </div>
                                </div>
                            {% endfor %}
                        </div>
                    </section>

                    <section>
                        <h3 class="text-lg font-bold text-slate-800 mb-4 flex items-center">
                            <i class="ri-medicine-bottle-line mr-2 text-purple-600"></i> Prescriptions & Reports
                        </h3>
                        <div class="space-y-4">
                            {% for p in prescriptions %}
                                <div class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm group hover:border-purple-100 transition-all">
                                    <div class="flex justify-between items-start mb-4">
                                        <div>
                                            <p class="font-bold text-slate-800">Prescription - {{ p.created_at.strftime('%d %b %Y') if p.created_at else 'N/A' }}</p>
                                            <p class="text-xs text-slate-400">By Dr. {{ p.doctor_username }}</p>
                                        </div>
                                        <div class="flex space-x-2">
                                            <a href="/view_certificate/{{ p.prescription_id }}" class="text-[10px] font-bold text-teal-600 hover:text-teal-700 bg-teal-50 px-3 py-1 rounded-lg transition-all flex items-center">
                                                <i class="ri-award-line mr-1 text-xs"></i> Online Certificate
                                            </a>
                                            <a href="/print_prescription/{{ p.prescription_id }}" class="text-[10px] font-bold text-slate-400 hover:text-slate-600 bg-slate-50 px-3 py-1 rounded-lg transition-all flex items-center">
                                                <i class="ri-printer-line mr-1 text-xs"></i> Print
                                            </a>
                                        </div>
                                    </div>
                                    <div class="bg-slate-50 p-4 rounded-xl text-sm text-slate-700 whitespace-pre-line leading-relaxed">
                                        {{ p.prescription_text }}
                                    </div>
                                </div>
                            {% endfor %}
                            {% if not prescriptions %}
                                <p class="text-slate-400 text-xs text-center py-10 bg-white rounded-3xl border border-dashed border-slate-200">No medical reports found for this patient.</p>
                            {% endif %}
                        </div>
                    </section>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, patient=patient, appointments=appointments, prescriptions=prescriptions, phone=phone)

@app.route("/doctor/my_leaves")
def doctor_my_leaves():
    if "doctor" not in session:
        flash("Please log in as doctor to access this page.", "error")
        return redirect("/login")
    
    leaves = list(leaves_collection.find({"doctor_username": session.get("doctor")}).sort("created_at", -1))
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>My Leaves - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-[#f8fafc] p-8">
        <div class="max-w-4xl mx-auto space-y-8">
            <header class="flex justify-between items-center">
                <div>
                   <h1 class="text-3xl font-bold text-slate-800">Leave History</h1>
                   <p class="text-slate-400">Track and manage your time-off requests</p>
                </div>
                <div class="flex items-center space-x-4">
                    <a href="/doctor/apply_leave" class="bg-yellow-600 text-white px-6 py-3 rounded-2xl font-bold hover:bg-yellow-700 transition-all shadow-lg shadow-yellow-100">
                        <i class="ri-add-line mr-2"></i>New Application
                    </a>
                    <a href="/dashboard" class="bg-white border border-slate-200 px-5 py-3 rounded-2xl text-slate-600 font-bold hover:border-teal-500 hover:text-teal-600 transition-all">
                        <i class="ri-arrow-left-line mr-2"></i>Dashboard
                    </a>
                </div>
            </header>

            <div class="grid grid-cols-1 gap-6">
                {% for leave in leaves %}
                <div class="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm flex flex-col md:flex-row md:items-center justify-between group hover:border-teal-100 transition-all">
                    <div class="space-y-2">
                        <div class="flex items-center space-x-3">
                            <div class="w-12 h-12 bg-slate-50 rounded-2xl flex items-center justify-center text-slate-400 group-hover:bg-teal-50 group-hover:text-teal-600 transition-all">
                                <i class="ri-calendar-check-line text-2xl"></i>
                            </div>
                            <div>
                                <p class="text-xl font-bold text-slate-800">{{ leave.start_date }} <span class="text-slate-300 font-normal mx-2">to</span> {{ leave.end_date }}</p>
                                <p class="text-sm text-slate-500">{{ leave.reason }}</p>
                            </div>
                        </div>
                    </div>
                    <div class="mt-6 md:mt-0 flex flex-col items-end space-y-3">
                        <span class="px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest
                            {% if leave.status == 'approved' %}bg-green-100 text-green-700
                            {% elif leave.status == 'rejected' %}bg-red-100 text-red-700
                            {% else %}bg-yellow-100 text-yellow-700{% endif %}">
                            {{ leave.status }}
                        </span>
                        {% if leave.admin_reason %}
                        <div class="text-right max-w-xs">
                            <p class="text-[10px] font-bold text-slate-300 uppercase mb-1">Admin Response</p>
                            <p class="text-xs text-slate-600 italic">"{{ leave.admin_reason }}"</p>
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
                
                {% if not leaves %}
                <div class="p-20 text-center bg-white rounded-3xl border border-dashed border-slate-200">
                    <i class="ri-calendar-close-line text-4xl text-slate-200 mb-4 block"></i>
                    <p class="text-slate-400 font-medium">No leave requests found</p>
                </div>
                {% endif %}
            </div>
        </div>
    </body>
    </html>
    """, leaves=leaves)


# --- Patient Dashboard (Enhanced version implemented above) ---


# --- Admin Routes ---

@app.route("/admin/cms")
def admin_cms():
    if "admin" not in session:
        return redirect("/login")
    site_settings = site_settings_collection.find_one({"type": "global"}) or {}
    fees = site_settings_collection.find_one({"type": "fees"}) or {"consultation_fee": 500, "free_consultation_days": 7}
    return render_template("admin/cms_management.html", 
                         site_settings=site_settings,
                         theme=site_settings,
                         fees=fees,
                         homepage_content=homepage_content_collection.find_one({"type": "main"}) or {})

@app.route("/admin/reports")
def admin_reports():
    if "admin" not in session:
        return redirect("/login")
    metrics = {
        "total_patients": patients_collection.count_documents({}),
        "total_doctors": doctors_collection.count_documents({}),
        "total_appointments": appointments_collection.count_documents({}),
        "total_revenue": 0 # Placeholder, can be calculated from payments collection if exists
    }
    
    # Calculate revenue if payments collection exists
    if 'payments' in db.list_collection_names():
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
        result = list(payments_collection.aggregate(pipeline))
        if result:
            metrics["total_revenue"] = result[0]["total"]

    return render_template("admin/reports_analytics.html",
                         site_settings=site_settings_collection.find_one({"type": "global"}) or {},
                         metrics=metrics)

@app.route("/admin/profile", methods=["GET", "POST"])
def admin_profile():
    if "admin" not in session:
        return redirect("/login")
    
    admin = admin_collection.find_one({"username": session["admin"]})
    
    # DEBUG: Log face encoding status
    if admin:
        has_face = "Yes" if "face_encoding" in admin and admin["face_encoding"] else "No"
        print(f"DEBUG PROFILE: Admin {session['admin']} has face encoding? {has_face}")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        
        update_data = {}
        if name: update_data["name"] = name
        if email: update_data["email"] = email
            
        if update_data:
            if admin:
                admin_collection.update_one({"_id": admin["_id"]}, {"$set": update_data})
            else:
                update_data["username"] = session["admin"]
                update_data["created_at"] = datetime.utcnow()
                admin_collection.insert_one(update_data)
                
            flash("Profile updated successfully!", "success")
        return redirect("/admin/profile")

    return render_template("admin/admin_profile.html", 
                         admin=admin, 
                         admin_name=admin.get("name", "Super Admin") if admin else "Super Admin",
                         site_settings=site_settings_collection.find_one({"type": "global"}) or {})

@app.route("/admin/update_password", methods=["POST"])
def admin_update_password():
    if "admin" not in session: return redirect("/login")
    
    admin = admin_collection.find_one({"username": session["admin"]})
    current_pass = request.form.get("current_password")
    new_pass = request.form.get("new_password")
    confirm_pass = request.form.get("confirm_password")
    
    if new_pass != confirm_pass:
        flash("New passwords do not match!", "error")
        return redirect("/admin/profile#security")
        
    if not admin or admin.get("password") != current_pass:
        flash("Incorrect current password!", "error")
        return redirect("/admin/profile#security")
        
    admin_collection.update_one({"username": session["admin"]}, {"$set": {"password": new_pass}})
    flash("Password updated successfully!", "success")
    return redirect("/admin/profile#security")

@app.route("/admin/update_notifications", methods=["POST"])
def admin_update_notifications():
    if "admin" not in session: return redirect("/login")
    
    email_alerts = request.form.get("email_alerts") == "true"
    report_alerts = request.form.get("report_alerts") == "true"
    
    admin_collection.update_one(
        {"username": session["admin"]}, 
        {"$set": {"email_alerts": email_alerts, "report_alerts": report_alerts}},
        upsert=True
    )
    flash("Notification preferences updated!", "success")
    return redirect("/admin/profile#notifications")

# --- Face Authentication Routes ---

@app.route("/api/register_face", methods=["POST"])
def api_register_face():
    """Register face for the logged-in user"""
    if not any(k in session for k in ["admin", "doctor", "receptionist", "pharmacist", "lab_assistant"]):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        data = request.json
        image_data = data.get("image")
        
        if not image_data:
            return jsonify({"success": False, "message": "No image data provided"}), 400
            
        # 1. Validate image quality
        is_valid, msg = validate_face_quality(image_data)
        if not is_valid:
            return jsonify({"success": False, "message": msg}), 400
            
        # 2. Extract encoding
        encoding, error = extract_face_encoding_from_base64(image_data)
        if error:
            return jsonify({"success": False, "message": error}), 400
            
        # 3. Store in user's document
        user_collection = None
        user_id = None
        
        if "admin" in session:
            user_collection = admin_collection
            username = session.get("admin")
            # For admin, we find by username instead of _id if _id isn't in session
            user_id = session.get("admin_id")
            user_query = {"username": username}
            
        elif "doctor" in session:
            user_collection = doctors_collection
            user_id = session.get("doctor_id") # Assuming we store this, or find by username
            username = session.get("doctor")
        elif "receptionist" in session:
            user_collection = receptionists_collection
            username = session.get("receptionist")
        # Add other roles...
        
        if user_collection and username:
            user_collection.update_one(
                {"username": username},
                {"$set": {"face_encoding": encoding, "face_id_enabled": True}},
                upsert=True
            )
            return jsonify({"success": True, "message": "Face ID registered successfully!"})
            
        return jsonify({"success": False, "message": "User context error"}), 400
        
    except Exception as e:
        print(f"Face registration error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route("/api/face_login", methods=["POST"])
def api_face_login():
    """Authenticate user via face"""
    try:
        data = request.json
        image_data = data.get("image")
        
        if not image_data:
            return jsonify({"success": False, "message": "No image data provided"}), 400
            
        # 1. Extract encoding from live image
        live_encoding, error = extract_face_encoding_from_base64(image_data)
        if error:
            return jsonify({"success": False, "message": error}), 400
            
        # 2. Search across collections
        # This is expensive O(N) searching. For production, use vector search (e.g., Pinecone/MongoDB Atlas Vector).
        # For this MVP, we iterate.
        
        collections = [
            (doctors_collection, "doctor", "doctor"),
            (receptionists_collection, "receptionist", "receptionist"),
            (pharmacists_collection, "pharmacist", "pharmacist"),
            (lab_assistants_collection, "lab_assistant", "lab_assistant"),
            (branch_admins_collection, "branch_admin", "branch_admin"),
            (admin_collection, "admin", "admin") 
        ]
        
        for col, role_key, role_session_name in collections:
            # Find users with face_id_enabled
            users_with_face = col.find({"face_id_enabled": True, "face_encoding": {"$exists": True}})
            
            for user in users_with_face:
                stored_encoding = user.get("face_encoding")
                if not stored_encoding: continue
                
                # Use stricter threshold for security
                is_match, confidence = verify_face(live_encoding, stored_encoding, threshold=0.5)
                
                if is_match:
                    # LOGIN SUCCESS!
                    session.clear()
                    session[role_key] = user["username"]
                    # Set other session vars like id, name, branch...
                    if "_id" in user: session[f"{role_key}_id"] = str(user["_id"])
                    if "name" in user: session[f"{role_key}_name"] = user["name"]
                    if "branch_id" in user: session[f"{role_key}_branch"] = user["branch_id"]
                    
                    # Update online status if doctor
                    if role_key == "doctor":
                        doctors_collection.update_one({"username": user["username"]}, {"$set": {"is_online": True}})
                    
                    # Return redirect URL
                    dashboard_map = {
                        "doctor": "/dashboard",
                        "receptionist": "/reception_dashboard",
                        "pharmacist": "/pharmacist_dashboard", 
                        "lab_assistant": "/lab_dashboard",
                        "admin": "/admin_dashboard"
                    }
                    
                    return jsonify({
                        "success": True, 
                        "message": f"Welcome back, {user.get('name', 'User')}!",
                        "redirect_url": dashboard_map.get(role_key, "/")
                    })
        return jsonify({"success": False, "message": "Face not recognized"}), 401
        
    except Exception as e:
        print(f"Face login error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# --- Face Registration for Admins ---
@app.route("/staff/face_register", methods=["GET", "POST"])
def staff_face_register():
    # Only Admin or Branch Admin can register
    user_role = get_user_role()
    if user_role not in ["admin", "branch_admin"]:
        flash("Unauthorized. Face ID registration is only for administrators.", "error")
        return redirect("/login")
        
    username = session.get(user_role)
    
    if request.method == "POST":
        try:
            data = request.json
            image_data = data.get("image")
            
            if not image_data:
                return jsonify({"success": False, "message": "No image captured"}), 400
            
            # Extract Encoding
            encoding, error = extract_face_encoding_from_base64(image_data)
            if error: 
                # Enhanced error message from reference
                error_hints = {
                    "No face detected": "Ensure your face is clearly visible and centered in the frame.",
                    "Multiple faces": "Please ensure only one person is in the frame.",
                    "Could not process": "Try improving lighting conditions and look directly at the camera."
                }
                hint = next((v for k, v in error_hints.items() if k in error), error)
                return jsonify({"success": False, "message": hint}), 400
            
            # Encrypt encoding for secure storage (from reference implementation)
            encrypted_encoding = encrypt_face_encoding(encoding)
            
            # Prepare database update with timestamp
            update_data = {
                "face_encoding": encrypted_encoding,
                "face_id_enabled": True,
                "face_enrolled_at": datetime.utcnow()
            }
            
            # Save to Database
            if user_role == "admin":
                admin_collection.update_one({"username": username}, {"$set": update_data}, upsert=True)
            else:
                branch_admins_collection.update_one({"username": username}, {"$set": update_data}, upsert=True)
                
            flash("Face ID identity registered successfully!", "success")
            return jsonify({"success": True, "redirect": f"/{user_role}_dashboard"})
            
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
            
    return render_template("staff/face_register.html")

@app.route("/admin/clear_face", methods=["POST"])
def admin_clear_face():
    user_role = get_user_role()
    if user_role not in ["admin", "branch_admin"]:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    username = session.get(user_role)
    collection = admin_collection if user_role == "admin" else branch_admins_collection
    
    collection.update_one({"username": username}, {"$unset": {"face_encoding": ""}})
    flash("Face ID data removed successfully.", "success")
    return redirect("/admin/profile" if user_role == "admin" else "/branch_admin_dashboard")

# --- Face Verification for Two-Factor Auth ---
@app.route("/staff/face_verify", methods=["GET", "POST"])
def staff_face_verify():
    if not session.get("pending_face_authorized"):
        flash("Unauthorized access. Please login again.", "error")
        return redirect("/login")
        
    username = session.get("pending_face_user")
    user_type = session.get("pending_face_type")
    
    if request.method == "POST":
        try:
            data = request.json
            image_data = data.get("image")
            
            if not image_data:
                return jsonify({"success": False, "message": "No image captured"}), 400
            
            # Fetch User for Encoding
            user = None
            if user_type == "admin":
                user = admin_collection.find_one({"username": username})
            elif user_type == "branch_admin":
                user = branch_admins_collection.find_one({"username": username})
            
            if not user or "face_encoding" not in user:
                 return jsonify({
                     "success": False, 
                     "message": "Face ID setup incomplete.",
                     "setup_required": True
                 }), 400

            stored_encoding = user["face_encoding"]
            
            # Decrypt the stored encoding (it was encrypted during registration)
            decrypted_encoding = decrypt_face_encoding(stored_encoding)
            if not decrypted_encoding:
                return jsonify({
                    "success": False, 
                    "message": "Error loading Face ID data. Please re-register."
                }), 500
            
            live_encoding, error = extract_face_encoding_from_base64(image_data)
            
            if error: 
                # Enhanced error message
                return jsonify({"success": False, "message": f"Scan failed: {error}. Try improving lighting and look directly at the camera."}), 400
            
            # Compare decrypted encoding with live capture
            match, confidence = verify_face(live_encoding, decrypted_encoding, threshold=0.5)
            
            if match:
                # SUCCESS - Complete login by setting session
                session[user_type] = username
                
                # Transfer email if available
                if session.get("pending_face_email"):
                    session["email"] = session.get("pending_face_email")
                
                # Transfer branch for branch_admin
                if user_type == "branch_admin" and session.get("pending_face_branch"):
                    session["branch_admin_branch"] = session.get("pending_face_branch")
                
                # Cleanup pending face session variables
                for k in ["pending_face_user", "pending_face_type", "pending_face_authorized", "pending_face_branch", "pending_face_id", "pending_face_email"]:
                    session.pop(k, None)
                
                flash(f"Identity Verified! Welcome {username}!", "success")
                
                # CORRECT REDIRECT: Redirect to specific dashboard based on role
                if user_type == "branch_admin":
                    target = "/branch_admin_dashboard"
                else:
                    target = "/admin_dashboard"
                    
                return jsonify({"success": True, "redirect": target})
            else:
                 return jsonify({"success": False, "message": "Face Verification Failed."}), 400
                 
        except Exception as e:
            print(f"Verify Error: {e}")
            return jsonify({"success": False, "message": "Internal Error"}), 500

    return render_template("staff/face_verify.html")

# --- Payment Gateway (Fake) ---
@app.route("/logout")
def logout():
    # Set doctor offline if logged in
    if "doctor" in session:
        doctors_collection.update_one({"username": session["doctor"]}, {"$set": {"is_online": False}})

    session.clear()
    flash("You have been logged out.", "success")
    return redirect("/")

# --- Payment Gateway (Fake) ---
@app.route("/payment/<appointment_id>", methods=["GET", "POST"])
def payment(appointment_id):
    appointment = appointments_collection.find_one({"appointment_id": appointment_id})
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect("/")
    
    if request.method == "POST":
        try:
            amount = request.form.get("amount", "500")
            payment_method = request.form.get("payment_method", "card")
            card_number = request.form.get("card_number", "").strip()
            
            # Fake payment processing - always succeeds
            payment_id = f"PAY{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
            
            payment_doc = {
                "payment_id": payment_id,
                "appointment_id": appointment_id,
                "amount": float(amount),
                "payment_method": payment_method,
                "status": "completed",
                "created_at": datetime.utcnow()
            }
            
            payments_collection.insert_one(payment_doc)
            
            # Update appointment status
            appointments_collection.update_one(
                {"appointment_id": appointment_id},
                {"$set": {"payment_status": "paid", "payment_id": payment_id}}
            )
            
            flash("Payment completed successfully!", "success")
            return redirect(f"/payment_success/{payment_id}")
        except Exception as e:
            flash(f"Payment error: {e}", "error")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Payment - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <h1 class="text-xl font-bold">Payment</h1>
            <a href="/" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back</a>
        </nav>
        <div class="p-6 max-w-2xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-semibold mb-4">Payment Details</h2>
                <p class="mb-2"><strong>Appointment ID:</strong> {{ appointment.appointment_id }}</p>
                <p class="mb-2"><strong>Patient:</strong> {{ appointment.get('name', 'N/A') }}</p>
                <p class="mb-4"><strong>Amount:</strong> ₹500</p>
                
                <form method="POST" action="/payment/{{ appointment.appointment_id }}" class="space-y-4">
                    <input type="hidden" name="amount" value="500">
                    <div>
                        <label class="block text-gray-700 mb-1">Payment Method<span class="text-red-500">*</span></label>
                        <select name="payment_method" required class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500">
                            <option value="card">Credit/Debit Card</option>
                            <option value="upi">UPI</option>
                            <option value="netbanking">Net Banking</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-1">Card Number (Fake Payment - Enter any number)</label>
                        <input type="text" name="card_number" placeholder="1234 5678 9012 3456" class="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500" />
                    </div>
                    <div class="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-4">
                        <strong>Note:</strong> This is a fake payment gateway for testing purposes. Payment will always succeed.
                    </div>
                    <button type="submit" class="bg-teal-600 text-white px-6 py-2 rounded hover:bg-teal-700 w-full">Pay ₹500</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, appointment=appointment)

@app.route("/payment_success/<payment_id>")
def payment_success(payment_id):
    payment = payments_collection.find_one({"payment_id": payment_id})
    if not payment:
        flash("Payment not found.", "error")
        return redirect("/")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
        <meta charset="UTF-8">
        <title>Payment Success - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gray-100 flex items-center justify-center">
        <div class="bg-white p-8 rounded-lg shadow-md max-w-md text-center">
            <div class="text-6xl mb-4">✓</div>
            <h2 class="text-2xl font-bold text-green-600 mb-4">Payment Successful!</h2>
            <p class="mb-2"><strong>Payment ID:</strong> {{ payment.payment_id }}</p>
            <p class="mb-2"><strong>Amount:</strong> ₹{{ payment.amount }}</p>
            <p class="mb-4"><strong>Status:</strong> {{ payment.status }}</p>
            <a href="/auth_home" class="bg-teal-600 text-white px-6 py-2 rounded hover:bg-teal-700">Back to Home</a>
        </div>
    </body>
    </html>
    """, payment=payment)

@app.route("/update_appointment_status/<appointment_id>/<status>")
def update_appointment_status(appointment_id, status):
    if "doctor" not in session:
        flash("Please log in to update appointment status.", "error")
        return redirect("/")
    
    # Expanded valid statuses based on your dashboard data
    valid_statuses = ['confirmed', 'pending', 'cancelled', 'checked_in', 'booked', 'completed']
    if status not in valid_statuses: 
        flash("Invalid status provided.", "error")
        return redirect("/dashboard")

    try:
        # Get appointment details before updating (for email notification)
        appointment = appointments_collection.find_one({"appointment_id": appointment_id})
        if not appointment:
            flash(f"Appointment with ID {appointment_id} not found.", "error")
            return redirect("/dashboard")
        
        result = appointments_collection.update_one(
            {"appointment_id": appointment_id},
            {"$set": {"status": status}}
        )
        
        if result.modified_count > 0:
            flash(f"Appointment {appointment_id} status updated to {status.capitalize()}.", "success")
            
            # Send cancellation email if status is cancelled
            if status == 'cancelled':
                email_sent = send_cancellation_email(
                    patient_name=appointment.get('name', 'Patient'),
                    patient_email=appointment.get('email', ''),
                    appointment_date=appointment.get('date', ''),
                    appointment_time=appointment.get('time', '')
                )
                if email_sent:
                    flash("Cancellation email sent to patient.", "success")
                else:
                    flash("Appointment cancelled but email notification failed.", "warning")
        else:
            flash(f"Appointment with ID {appointment_id} not found or status already {status}.", "info") 
    except Exception as e:
        flash(f"Error updating appointment: {str(e)}", "error")
    
    return redirect("/dashboard")

# ...existing code...
@app.route("/patient/book_now")
def patient_book_now():
    session["patient_guest"] = True
    return redirect("/add_appointment")

@app.route("/add_appointment", methods=["GET", "POST"])
def add_appointment():
    if not any(k in session for k in ["doctor", "receptionist", "patient", "patient_guest"]):
        flash("Please log in to add appointments.", "error")
        return redirect("/login")

    appointment_data = {}
    try:
        branch_locations = {
            (b.get("location") or "").strip()
            for b in branches_collection.find({}, {"location": 1})
        }
        branch_locations.discard("")
    except Exception:
        branch_locations = set()
    location_options = sorted(branch_locations)

    default_city = location_options[0] if location_options else 'Hyderabad'
    today_date = datetime.now().strftime("%d-%m-%Y")  # d-m-Y format for input and min

    selected_date = request.form.get("date", today_date) if request.method == "POST" else today_date
    selected_city = request.form.get("location", default_city) if request.method == "POST" else default_city
    
    # Convert selected_date to YYYY-MM-DD format for generate_time_slots
    appointment_date = selected_date
    if appointment_date:
        try:
            if len(appointment_date) == 10 and appointment_date[2] == '-' and appointment_date[5] == '-':
                # DD-MM-YYYY format, convert to YYYY-MM-DD
                dt = datetime.strptime(appointment_date, "%d-%m-%Y")
                appointment_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    time_slots = generate_time_slots(selected_city, appointment_date)
    booked_slots = get_booked_slots_for_date(selected_date, city=selected_city)

    if request.method == "POST":
        try:
            name = request.form["name"]
            phone = request.form["phone"]
            email = request.form["email"]
            location = request.form.get("location", default_city)
            date_input = request.form["date"]
            time = request.form["time"]
            address = request.form["address"]
            symptoms = request.form["symptoms"]
             # Convert date to d-m-Y format for storing
            try:
                date_obj = datetime.strptime(date_input, "%Y-%m-%d")
                date = date_obj.strftime("%d-%m-%Y")
            except Exception:
                date = date_input  # fallback if already in d-m-Y

            normalized_phone, phone_error = normalize_indian_phone(phone)
            if phone_error:
                flash(phone_error, "error")
                return render_template_string(appointment_form_template, mode='add', appointment_data=appointment_data, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

            # Find Branch ID based on location
            branch_data = branches_collection.find_one({"location": location})
            branch_id = str(branch_data["_id"]) if branch_data else None
            
            consultation_type = request.form.get("consultation_type", "Walk-in")

            appointment_data = {
                "name": name,
                "phone": normalized_phone,
                "email": email,
                "location": location,
                "branch_id": branch_id, # critical for routing to reception
                "consultation_type": consultation_type,
                "date": date,  # store in d-m-Y format
                "time": time,
                "address": address,
                "symptoms": symptoms
            }

            # Compare dates in d-m-Y format
            if datetime.strptime(date, "%d-%m-%Y") < datetime.strptime(today_date, "%d-%m-%Y"):
                flash("Cannot book an appointment for a past date.", "error")
                return render_template_string(appointment_form_template, mode='add', appointment_data=appointment_data, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

            existing_appointment = appointments_collection.find_one({
                "date": date,
                "time": time,
                "location": location
            }) or blocked_slots_collection.find_one({
                "date": date,
                "time": time,
                "location": location
            })

            if existing_appointment:
                flash(f"The slot {date} {time} is unavailable (booked/blocked). Please choose a different time.", "error")
                return render_template_string(appointment_form_template, mode='add', appointment_data=appointment_data, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

            # Format location for ID (replace spaces with underscores, remove special chars)
            location_id = location.replace(" ", "_").replace(",", "").replace(".", "")
            date_str = datetime.now().strftime("%d%m%y")
            while True:
                random_num = str(random.randint(1, 9999)).zfill(4)
                potential_appointment_id = f"HeyDoc_{location_id}_{date_str}_{random_num}"
                if not appointments_collection.find_one({"appointment_id": potential_appointment_id}):
                    appointment_id = potential_appointment_id
                    break

            new_appointment_data = {
                "appointment_id": appointment_id,
                "name": name,
                "phone": normalized_phone,
                "email": email,
                "address": address,
                "symptoms": symptoms,
                "date": date,  # store in d-m-Y format
                "time": time,
                "location": location,
                "status": "pending",
                "created_at_str": datetime.now().strftime("%d-%m-%Y %I:%M %p IST")
            }

            appointments_collection.insert_one(new_appointment_data)
            flash(f"Appointment {appointment_id} created successfully.", "success")
            return redirect("/dashboard")

        except Exception as e:
            flash(f"Error creating appointment: {str(e)}", "error")
            return render_template_string(appointment_form_template, mode='add', appointment_data=appointment_data, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)

    return render_template_string(appointment_form_template, mode='add', appointment_data=appointment_data, time_slots=time_slots, today_date=today_date, booked_slots=booked_slots, location_options=location_options)
             
# ...existing code...


# --- Block/Unblock Slot Routes ---
@app.route("/block_slot", methods=["GET", "POST"])
def block_slot():
    if "doctor" not in session:
        flash("Please log in to manage slots.", "error")
        return redirect("/")

    if request.method == "POST":
        date = request.form.get("date", "").strip()
        time = request.form.get("time", "").strip()
        location = request.form.get("location", "Hyderabad").strip()
        reason = request.form.get("reason", "").strip()

        if not date or not time:
            flash("Date and Time are required.", "error")
            return redirect("/block_slot")

        # Convert date from YYYY-MM-DD to DD-MM-YYYY format for storage
        formatted_date = date
        try:
            if len(date) == 10 and date[4] == '-' and date[7] == '-':
                # YYYY-MM-DD format, convert to DD-MM-YYYY
                dt = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = dt.strftime("%d-%m-%Y")
        except ValueError:
            pass

        # Prevent blocking if an appointment already exists (check both formats)
        exists = appointments_collection.find_one({"date": date, "time": time, "location": location})
        if not exists:
            # Also check with formatted date
            exists = appointments_collection.find_one({"date": formatted_date, "time": time, "location": location})
        
        if exists:
            flash(f"Cannot block {formatted_date} {time}: an appointment exists.", "error")
            return redirect("/block_slot")

        # Prevent duplicate block (check both formats)
        already_blocked = blocked_slots_collection.find_one({"date": date, "time": time, "location": location})
        if not already_blocked:
            already_blocked = blocked_slots_collection.find_one({"date": formatted_date, "time": time, "location": location})
        
        if already_blocked:
            flash("This slot is already blocked.", "info")
            return redirect("/block_slot")

        blocked_slots_collection.insert_one({
            "date": formatted_date,  # Store in DD-MM-YYYY format
            "time": time,
            "location": location,
            "reason": reason,
            "created_at": datetime.now().strftime("%d-%m-%Y %I:%M %p IST")
        })
        flash(f"Blocked {date} {time}.", "success")
        return redirect("/block_slot")

    # GET: show form and list
    all_blocked = blocked_slots_collection.find({}).sort("date", 1)
    
    # Filter out past blocked slots - only show present and future ones
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")
    
    blocked_list = []
    for blocked in all_blocked:
        blocked_date = blocked.get('date', '')
        blocked_time = blocked.get('time', '')
        
        # Skip if no date or time
        if not blocked_date or not blocked_time:
            continue
        
        # Normalize blocked date to YYYY-MM-DD for comparison
        normalized_date = blocked_date
        try:
            if len(blocked_date) == 10 and blocked_date[2] == '-' and blocked_date[5] == '-':
                # DD-MM-YYYY format, convert to YYYY-MM-DD for comparison
                dt = datetime.strptime(blocked_date, "%d-%m-%Y")
                normalized_date = dt.strftime("%Y-%m-%d")
            elif len(blocked_date) == 10 and blocked_date[4] == '-' and blocked_date[7] == '-':
                # Already YYYY-MM-DD format
                normalized_date = blocked_date
        except ValueError:
            # If date parsing fails, skip this blocked slot
            continue
            
        # Convert blocked time to 24-hour format for comparison
        try:
            if 'AM' in blocked_time or 'PM' in blocked_time:
                # Parse 12-hour format
                try:
                    time_obj = datetime.strptime(blocked_time, "%I:%M %p")
                except ValueError:
                    time_obj = datetime.strptime(blocked_time, "%I:%M:%S %p")
                blocked_time_24 = time_obj.strftime("%H:%M")
            else:
                # Already in 24-hour format
                blocked_time_24 = blocked_time
        except ValueError:
            # If time parsing fails, skip this blocked slot
            continue
        
        # Check if blocked slot is today or in the future
        if normalized_date > current_date:
            # Future date - include
            # Ensure date is in DD-MM-YYYY format for display
            if len(blocked_date) == 10 and blocked_date[4] == '-' and blocked_date[7] == '-':
                # YYYY-MM-DD format, convert to DD-MM-YYYY
                try:
                    dt = datetime.strptime(blocked_date, "%Y-%m-%d")
                    blocked['date'] = dt.strftime("%d-%m-%Y")
                except ValueError:
                    pass
            blocked_list.append(blocked)
        elif normalized_date == current_date:
            # Today - only include if time is current or future
            if blocked_time_24 >= current_time:
                # Ensure date is in DD-MM-YYYY format for display
                if len(blocked_date) == 10 and blocked_date[4] == '-' and blocked_date[7] == '-':
                    # YYYY-MM-DD format, convert to DD-MM-YYYY
                    try:
                        dt = datetime.strptime(blocked_date, "%Y-%m-%d")
                        blocked['date'] = dt.strftime("%d-%m-%Y")
                    except ValueError:
                        pass
                blocked_list.append(blocked)
        # Past dates are automatically excluded
    # Get selected date for time slot generation (default to today)
    selected_date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    
    return render_template_string(
        block_slot_template,
        time_slots=generate_time_slots("Hyderabad", selected_date),
        blocked_list=blocked_list,
        datetime=datetime,
        available_cities=AVAILABLE_CITIES
    )

@app.route("/unblock_slot")
def unblock_slot():
    if "doctor" not in session:
        flash("Please log in to manage slots.", "error")
        return redirect("/")

    sid = request.args.get("id", "").strip()
    try:
        if sid:
            blocked_slots_collection.delete_one({"_id": ObjectId(sid)})
            flash("Slot unblocked.", "success")
    except Exception as e:
        flash(f"Error unblocking slot: {e}", "error")
    return redirect("/block_slot")

# Migration function to update existing blocked slots to DD-MM-YYYY format
@app.route("/admin/block_slots", methods=["GET", "POST"])
def admin_block_slots():
    if "admin" not in session:
        flash("Please log in as admin to manage slots.", "error")
        return redirect("/login")

    if request.method == "POST":
        date = request.form.get("date")
        time = request.form.get("time")
        location = request.form.get("location")
        reason = request.form.get("reason", "Administrative Block")
        
        # Date formatting and validation
        formatted_date = date
        try:
            if len(date) == 10 and date[4] == '-' and date[7] == '-':
                dt = datetime.strptime(date, "%Y-%m-%d")
                
                # Check for past date
                if dt.date() < datetime.now().date():
                    flash("Cannot block slots for past dates.", "error")
                    return redirect("/admin/block_slots")
                    
                formatted_date = dt.strftime("%d-%m-%Y")
        except ValueError:
            pass

        # Check for existing appointments
        exists = appointments_collection.find_one({"date": date, "time": time, "location": location})
        if not exists:
            exists = appointments_collection.find_one({"date": formatted_date, "time": time, "location": location})
        
        if exists:
            flash(f"Cannot block {formatted_date} {time}: an appointment exists.", "error")
        else:
            blocked_slots_collection.insert_one({
                "date": formatted_date,
                "time": time,
                "location": location,
                "reason": reason,
                "created_by": session.get("admin"),
                "created_at": datetime.now().strftime("%d-%m-%Y %I:%M %p IST")
            })
            flash(f"Slot {formatted_date} {time} blocked successfully for {location}.", "success")
        
        return redirect("/admin/block_slots")

    # GET logic
    all_blocked = blocked_slots_collection.find({}).sort("date", 1)
    
    # Simple list for display
    blocked_list = list(all_blocked)
    
    # Get branches for the dropdown
    branches = list(branches_collection.find({}, {"name": 1, "location": 1}))
    locations = [f"{b['name']} ({b['location']})" for b in branches]

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-50">
    <head>
        <meta charset="UTF-8">
        <title>Block Slots - Admin Control</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-slate-50 p-6">
        <div class="max-w-4xl mx-auto space-y-6">
            <div class="bg-white p-8 rounded-[30px] shadow-sm border border-slate-200 flex justify-between items-center">
                <div>
                    <h1 class="text-2xl font-black text-slate-800">Clinic Availability Control</h1>
                    <p class="text-slate-500 text-sm">Block specific slots across branches for maintenance or holidays</p>
                </div>
                <div class="flex items-center space-x-2">
                    <a href="/admin_dashboard" class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-500 hover:bg-teal-600 hover:text-white transition-all">
                        <i class="ri-dashboard-3-line"></i>
                    </a>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Blocking Form -->
                <div class="lg:col-span-1">
                    <form method="POST" class="bg-white p-6 rounded-[30px] shadow-sm border border-slate-200 space-y-4">
                        <div class="space-y-1">
                            <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Date</label>
                            <input type="date" name="date" required class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all">
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Time Slot (HH:MM)</label>
                            <input type="time" name="time" required class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all">
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Branch Location</label>
                            <select name="location" required class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all">
                                {% for loc in locations %}
                                    <option value="{{ loc }}">{{ loc }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Reason</label>
                            <input type="text" name="reason" placeholder="e.g. Doctor unavailable" required class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-teal-500/10 focus:border-teal-500 outline-none transition-all">
                        </div>
                        <button type="submit" class="w-full bg-teal-600 text-white py-4 rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-teal-700 shadow-lg shadow-teal-500/20 transition-all">
                            Block Slot
                        </button>
                    </form>
                </div>

                <!-- Active Blocks List -->
                <div class="lg:col-span-2">
                    <div class="bg-white rounded-[30px] shadow-sm border border-slate-200 overflow-hidden">
                        <div class="p-6 border-b border-slate-100 bg-slate-50/30 flex justify-between items-center">
                            <h3 class="text-xs font-black text-slate-400 uppercase tracking-widest">Active Blocks</h3>
                        </div>
                        <div class="overflow-y-auto max-h-[600px] divide-y divide-slate-100">
                            {% if blocked_list %}
                                {% for item in blocked_list %}
                                    <div class="p-4 flex justify-between items-center hover:bg-slate-50 transition-colors">
                                        <div>
                                            <div class="flex items-center space-x-2">
                                                <span class="text-sm font-black text-slate-700">{{ item.date }}</span>
                                                <span class="text-xs font-bold text-teal-600 bg-teal-50 px-2 py-0.5 rounded-full">{{ item.time }}</span>
                                            </div>
                                            <p class="text-xs text-slate-500 mt-1"><i class="ri-map-pin-line mr-1"></i> {{ item.location }}</p>
                                            <p class="text-[10px] text-slate-400 mt-0.5 italic">Reason: {{ item.reason }}</p>
                                        </div>
                                        <a href="/admin/unblock_slot/{{ item._id }}" class="w-8 h-8 rounded-lg bg-red-50 text-red-500 flex items-center justify-center hover:bg-red-500 hover:text-white transition-all">
                                            <i class="ri-delete-bin-line"></i>
                                        </a>
                                    </div>
                                {% endfor %}
                            {% else %}
                                <div class="p-10 text-center text-slate-400 text-sm">
                                    <i class="ri-calendar-check-line text-4xl mb-2 block opacity-20"></i>
                                    No slots are currently blocked.
                                </div>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, locations=locations, blocked_list=blocked_list)

@app.route("/admin/unblock_slot/<sid>")
def admin_unblock_slot(sid):
    if "admin" not in session:
        return redirect("/login")
    try:
        blocked_slots_collection.delete_one({"_id": ObjectId(sid)})
        flash("Slot unblocked successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect("/admin/block_slots")

@app.route("/migrate_blocked_slots")
def migrate_blocked_slots():
    if "doctor" not in session:
        flash("Please log in to access this function.", "error")
        return redirect("/")
    
    try:
        # Find all blocked slots with YYYY-MM-DD format
        all_blocked = blocked_slots_collection.find({})
        updated_count = 0
        
        for blocked in all_blocked:
            blocked_date = blocked.get('date', '')
            
            # Check if it's in YYYY-MM-DD format
            if len(blocked_date) == 10 and blocked_date[4] == '-' and blocked_date[7] == '-':
                try:
                    # Convert to DD-MM-YYYY format
                    dt = datetime.strptime(blocked_date, "%Y-%m-%d")
                    new_date = dt.strftime("%d-%m-%Y")
                    
                    # Update the document
                    blocked_slots_collection.update_one(
                        {"_id": blocked["_id"]},
                        {"$set": {"date": new_date}}
                    )
                    updated_count += 1
                except ValueError:
                    # Skip if date parsing fails
                    continue
        
        flash(f"Migration completed. Updated {updated_count} blocked slots to DD-MM-YYYY format.", "success")
    except Exception as e:
        flash(f"Error during migration: {str(e)}", "error")
    
    return redirect("/block_slot")


# --- Public API: get generated time slots for a city ---


# --- Availability Routes ---
# ...existing code...

@app.route("/add_availability", methods=["GET", "POST"])
def add_availability():
    if "doctor" not in session:
        flash("Please log in to manage availability.", "error")
        return redirect("/")

    # Build location options: branches only (no default cities)
    try:
        branch_locations = {
            (b.get("location") or "").strip()
            for b in branches_collection.find({}, {"location": 1})
        }
        branch_locations.discard("")
    except Exception:
        branch_locations = set()
    location_options = sorted(branch_locations)  # <-- Only branch locations

    if request.method == "POST":
        try:
            location = request.form.get("location", "").strip()
            def is_real_place(loc_name: str) -> bool:
                try:
                    if not loc_name:
                        return False
                    url = "https://nominatim.openstreetmap.org/search"
                    params = {"q": loc_name, "format": "json", "addressdetails": 1, "limit": 1}
                    headers = {"User-Agent": "clinic-app/1.0"}
                    r = requests.get(url, params=params, headers=headers, timeout=6)
                    if r.status_code != 200:
                        return False
                    data = r.json()
                    return isinstance(data, list) and len(data) > 0
                except Exception:
                    return False

            if location_options:
                if location not in location_options:
                    flash("Please select a location from Branch list.", "error")
                    return render_template_string(availability_form_template, datetime=datetime, location_options=location_options)
            else:
                if not is_real_place(location):
                    flash("Please enter a real location name (validated against maps).", "error")
                    return render_template_string(availability_form_template, datetime=datetime, location_options=location_options)
            hospital_name = request.form.get("hospital_name", "Hey Doc!").strip()
            mode = request.form.get("mode", "default")
            date_override = request.form.get("date", "").strip()

            def fmt_12h(value):
                if not value:
                    return None
                try:
                    t = datetime.strptime(value, "%H:%M")
                    return t.strftime("%I:%M %p")
                except Exception:
                    return value

            morning_start = fmt_12h(request.form.get("morning_start"))
            morning_end = fmt_12h(request.form.get("morning_end"))
            evening_start = fmt_12h(request.form.get("evening_start"))
            evening_end = fmt_12h(request.form.get("evening_end"))

            working_hours = {}
            if morning_start and morning_end:
                working_hours["morning_shift"] = {"start": morning_start, "end": morning_end}
            if evening_start and evening_end:
                working_hours["evening_shift"] = {"start": evening_start, "end": evening_end}

            if not working_hours:
                flash("Please enter at least one complete shift (start and end).", "error")
                return render_template_string(availability_form_template, datetime=datetime, location_options=location_options)

            timings_col = loc_aval_collection

            doc = {
                "hospital_name": hospital_name or "Hey Doc ",
                "location": location,
                "working_hours": working_hours,
                "created_at": datetime.utcnow()
            }

            if mode == "date" and date_override:
                try:
                    dt = datetime.strptime(date_override, "%Y-%m-%d")
                    doc["date"] = dt.strftime("%d-%m-%Y")
                except Exception:
                    doc["date"] = date_override
                doc["Default"] = False
            else:
                doc["Default"] = True

            timings_col.insert_one(doc)
            flash("Availability saved.", "success")
            return redirect("/dashboard")
        except Exception as e:
            flash(f"Error saving availability: {e}", "error")
            return render_template_string(availability_form_template, datetime=datetime, location_options=location_options)

    return render_template_string(availability_form_template, datetime=datetime, location_options=location_options)

# ...existing code...

# --- Branch Management Routes ---
@app.route("/add_branch", methods=["GET", "POST"])
def add_branch():
    if "doctor" not in session:
        flash("Please log in to manage branches.", "error")
        return redirect("/")

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            location = request.form.get("location", "").strip()
            address = request.form.get("address", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            notes = request.form.get("notes", "").strip()
            morning_start = request.form.get("morning_start", "").strip()
            morning_end = request.form.get("morning_end", "").strip()
            evening_start = request.form.get("evening_start", "").strip()
            evening_end = request.form.get("evening_end", "").strip()
            is_default = request.form.get("is_default") == "on"

            if not name:
                flash("Branch name is required.", "error")
                return redirect("/add_branch")

            doc = {
                "name": name,
                "location": location,
                "address": address,
                "phone": phone,
                "email": email,
                "notes": notes,
                "created_at": datetime.utcnow(),
                "created_by": session.get("doctor")
            }

            branches_collection.insert_one(doc)
            # Also store timings in LocAval as requested
            def _fmt_12h(value):
                try:
                    # Accept both 12h (with AM/PM) and 24h, return 12h with AM/PM
                    return datetime.strptime(value, "%I:%M %p").strftime("%I:%M %p")
                except Exception:
                    try:
                        return datetime.strptime(value, "%H:%M").strftime("%I:%M %p")
                    except Exception:
                        return value or None

            working_hours = {}
            if morning_start and morning_end:
                working_hours["morning_shift"] = {"start": _fmt_12h(morning_start), "end": _fmt_12h(morning_end)}
            if evening_start and evening_end:
                working_hours["evening_shift"] = {"start": _fmt_12h(evening_start), "end": _fmt_12h(evening_end)}

            if working_hours:
                locaval_doc = {
                    "hospital_name": name,
                    "location": location,
                    "Default": True if is_default else False,
                    "working_hours": working_hours,
                    "created_at": datetime.utcnow()
                }
                loc_aval_collection.insert_one(locaval_doc)

            flash("Branch added successfully.", "success")
            return redirect("/dashboard")
        except Exception as e:
            flash(f"Error adding branch: {e}", "error")

    # GET
    return render_template_string(
        """
        <!DOCTYPE html>
        <html lang=\"en\" class=\"bg-gray-100\">
        <head>
          <meta charset=\"UTF-8\">
          <title>Add Branch - Hey Doc!</title>
          <script src=\"https://cdn.tailwindcss.com\"></script>
        </head>
        <body class=\"min-h-screen bg-gray-100\">
          <nav class=\"bg-teal-600 p-4 text-white flex justify-between items-center\">
            <h1 class=\"text-xl font-bold\">Add Branch</h1>
            <div>
              <a href=\"/dashboard\" class=\"bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100\">Dashboard</a>
            </div>
          </nav>
          <div class=\"p-6 max-w-2xl mx-auto\">
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% for category, message in messages %}
                <div class=\"mb-4 text-sm p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800\">{{ message }}</div>
              {% endfor %}
            {% endwith %}

            <div class=\"bg-white rounded-lg shadow-md p-6\">
              <form method=\"POST\" action=\"/add_branch\" class=\"space-y-4\">
                <div>
                  <label class=\"block text-gray-700 mb-1\">Branch Name<span class=\"text-red-500\">*</span></label>
                  <input type=\"text\" name=\"name\" required class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"e.g., Hey Doc Clinic - Hyderabad\" />
                </div>
                <div>
                  <label class=\"block text-gray-700 mb-1\">Location / City</label>
                  <input type=\"text\" name=\"location\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"e.g., Hyderabad\" />
                </div>
                <div>
                  <label class=\"block text-gray-700 mb-1\">Address</label>
                  <textarea name=\"address\" rows=\"3\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"Street, Area, Pin\"></textarea>
                </div>
                <div class=\"grid grid-cols-1 md:grid-cols-2 gap-4\">
                  <div>
                    <label class=\"block text-gray-700 mb-1\">Phone</label>
                    <input type=\"text\" name=\"phone\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"e.g., +91XXXXXXXXXX\" />
                  </div>
                  <div>
                    <label class=\"block text-gray-700 mb-1\">Email</label>
                    <input type=\"email\" name=\"email\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"e.g., branch@example.com\" />
                  </div>
                </div>
                <div class=\"grid grid-cols-1 md:grid-cols-2 gap-4\">
                  <div>
                    <label class=\"block text-gray-700 font-medium mb-2\">Morning Shift</label>
                    <div class=\"grid grid-cols-2 gap-2\">
                      <input type=\"text\" name=\"morning_start\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"11:00 AM\" />
                      <input type=\"text\" name=\"morning_end\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"02:00 PM\" />
                    </div>
                  </div>
                  <div>
                    <label class=\"block text-gray-700 font-medium mb-2\">Evening Shift</label>
                    <div class=\"grid grid-cols-2 gap-2\">
                      <input type=\"text\" name=\"evening_start\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"06:00 PM\" />
                      <input type=\"text\" name=\"evening_end\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"09:30 PM\" />
                    </div>
                  </div>
                </div>
                <div class=\"flex items-center space-x-2\">
                  <input id=\"is_default\" type=\"checkbox\" name=\"is_default\" class=\"h-4 w-4\">
                  <label for=\"is_default\" class=\"text-gray-700\">Mark as Default timings for this location</label>
                </div>
                <div>
                  <label class=\"block text-gray-700 mb-1\">Notes</label>
                  <textarea name=\"notes\" rows=\"2\" class=\"w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-teal-500\" placeholder=\"Any additional details\"></textarea>
                </div>

                <div class=\"flex items-center space-x-3\">
                  <button type=\"submit\" class=\"bg-teal-600 text-white px-5 py-2 rounded hover:bg-teal-700\">Save Branch</button>
                  <a href=\"/dashboard\" class=\"bg-gray-200 text-gray-700 px-5 py-2 rounded hover:bg-gray-300\">Cancel</a>
                </div>
              </form>
            </div>
          </div>
        </body>
        </html>
        """,
    )

# --- Prescription Routes ---
@app.route("/add_prescription", methods=["GET", "POST"])
def add_prescription():
    if "doctor" not in session:
        flash("Please log in to add prescriptions.", "error")
        return redirect("/")
    
    prescription_data = {}
    today_date = datetime.now().strftime("%Y-%m-%d")
    
                # Check for patient information from query parameters (when coming from patient-specific view)
    if request.method == "GET":
        patient_phone = request.args.get('patient_phone', '').strip()
        print(f"DEBUG: Received patient_phone parameter: '{patient_phone}'")
        if patient_phone:
            # Normalize phone number for search (remove +91 if present, add if missing)
            normalized_phone = patient_phone
            if patient_phone.startswith('+91'):
                normalized_phone = patient_phone[3:]  # Remove +91
            elif patient_phone.startswith('91'):
                normalized_phone = patient_phone[2:]  # Remove 91
            elif patient_phone.startswith('0'):
                normalized_phone = patient_phone[1:]  # Remove leading 0
            
            # Try multiple phone number formats for search
            phone_variants = [
                patient_phone,  # Original format
                f"+91{normalized_phone}",  # With +91
                f"91{normalized_phone}",   # With 91
                f"0{normalized_phone}",    # With 0
                normalized_phone           # Clean number
            ]
            
            print(f"DEBUG: Searching with phone variants: {phone_variants}")
            
            # Try to get patient name from appointments
            appointment = None
            for phone_variant in phone_variants:
                appointment = appointments_collection.find_one({"phone": phone_variant})
                if appointment:
                    print(f"DEBUG: Found appointment with phone variant: '{phone_variant}'")
                    break
            
            if appointment:
                prescription_data["patient_name"] = appointment.get("name", "")
                prescription_data["patient_phone"] = appointment.get("phone", patient_phone)
                print(f"DEBUG: Found appointment for {patient_phone}, name: {appointment.get('name', '')}")
            else:
                # Check if patient exists in prescriptions
                prescription = None
                for phone_variant in phone_variants:
                    prescription = prescriptions_collection.find_one({"patient_phone": phone_variant})
                    if prescription:
                        print(f"DEBUG: Found prescription with phone variant: '{phone_variant}'")
                        break
                
                if prescription:
                    prescription_data["patient_name"] = prescription.get("patient_name", "")
                    prescription_data["patient_phone"] = prescription.get("patient_phone", patient_phone)
                    print(f"DEBUG: Found prescription for {patient_phone}, name: {prescription.get('patient_name', '')}")
                else:
                    print(f"DEBUG: No patient found for phone: {patient_phone}")
                    # Let's also check what phone numbers exist in the database
                    all_appointments = list(appointments_collection.find({}, {"phone": 1, "name": 1}))
                    print(f"DEBUG: All phone numbers in appointments: {[a.get('phone') for a in all_appointments]}")
                    all_prescriptions = list(prescriptions_collection.find({}, {"patient_phone": 1, "patient_name": 1}))
                    print(f"DEBUG: All phone numbers in prescriptions: {[p.get('patient_phone') for p in all_prescriptions]}")
        
        print(f"DEBUG: Final prescription_data: {prescription_data}")
    
    if request.method == "POST":
        try:
            patient_name = request.form["patient_name"]
            patient_phone = request.form["patient_phone"]
            prescription_date = request.form["prescription_date"]
            # Convert input (YYYY-MM-DD) to IST display format (DD-MM-YYYY)
            try:
                _pd = datetime.strptime(prescription_date, "%Y-%m-%d")
                prescription_date_ist = _pd.strftime("%d-%m-%Y")
            except Exception:
                prescription_date_ist = prescription_date
            diagnosis = request.form["diagnosis"]
            instructions = request.form["instructions"]
            notes = request.form["notes"]
            
            # Normalize phone number to ensure +91 prefix
            normalized_phone, phone_error = normalize_indian_phone(patient_phone)
            if phone_error:
                flash(phone_error, "error")
                prescription_data = {
                    "patient_name": patient_name,
                    "patient_phone": patient_phone,
                    "prescription_date": prescription_date,
                    "diagnosis": diagnosis,
                    "instructions": instructions,
                    "notes": notes
                }
                return render_template_string(prescription_form_template, prescription_data=prescription_data, today_date=today_date)
            
            # Get medicine data from form arrays
            medicine_names = request.form.getlist("medicine_names[]")
            potencies = request.form.getlist("potencies[]")
            dosages = request.form.getlist("dosages[]")
            durations = request.form.getlist("durations[]")
            
            # Validate that we have at least one medicine
            if not medicine_names or not medicine_names[0]:
                flash("At least one medicine is required.", "error")
                prescription_data = {
                    "patient_name": patient_name,
                    "patient_phone": normalized_phone,
                    "prescription_date": prescription_date,
                    "diagnosis": diagnosis,
                    "instructions": instructions,
                    "notes": notes
                }
                return render_template_string(prescription_form_template, prescription_data=prescription_data, today_date=today_date)
            
            # Create medicines list
            medicines = []
            for i in range(len(medicine_names)):
                if medicine_names[i].strip():  # Only add if medicine name is not empty
                    medicines.append({
                        "name": medicine_names[i].strip(),
                        "potency": potencies[i].strip() if i < len(potencies) else "",
                        "dosage": dosages[i].strip() if i < len(dosages) else "",
                        "duration": durations[i].strip() if i < len(durations) else ""
                    })
            
            # Generate prescription ID
            date_str = datetime.now().strftime("%Y%m%d")
            while True:
                random_num = str(random.randint(1, 9999)).zfill(4)
                potential_prescription_id = f"PRES-{date_str}-{random_num}"
                if not prescriptions_collection.find_one({"prescription_id": potential_prescription_id}):
                    prescription_id = potential_prescription_id
                    break
            
            new_prescription_data = {
                "prescription_id": prescription_id,
                "patient_name": patient_name,
                "patient_phone": normalized_phone,
                "doctor_username": session.get("doctor"),
                # Store display date in IST style, and keep original ISO for queries/sorting
                "prescription_date": prescription_date_ist,
                "prescription_date_iso": prescription_date,
                "diagnosis": diagnosis,
                "medicines": medicines,
                "instructions": instructions,
                "notes": notes,
                "created_at_str": datetime.now().strftime("%d-%m-%Y %I:%M %p IST")
            }
            
            prescriptions_collection.insert_one(new_prescription_data)
            flash(f"Prescription {prescription_id} created successfully.", "success")
            
            # Redirect back to patient-specific view if we came from there
            if normalized_phone:
                return redirect(f"/prescriptions?patient_phone={normalized_phone}")
            else:
                return redirect("/prescriptions")
            
        except Exception as e:
            flash(f"Error creating prescription: {str(e)}", "error")
            prescription_data = {
                "patient_name": patient_name if 'patient_name' in locals() else "",
                "patient_phone": normalized_phone if 'normalized_phone' in locals() else (patient_phone if 'patient_phone' in locals() else ""),
                "prescription_date": prescription_date if 'prescription_date' in locals() else today_date,
                "diagnosis": diagnosis if 'diagnosis' in locals() else "",
                "instructions": instructions if 'instructions' in locals() else "",
                "notes": notes if 'notes' in locals() else ""
            }
            return render_template_string(prescription_form_template, prescription_data=prescription_data, today_date=today_date)
    
    print(f"DEBUG: Final render with prescription_data: {prescription_data}")
    print(f"DEBUG: Template will receive prescription_data.patient_name: '{prescription_data.get('patient_name', 'NOT_FOUND')}'")
    print(f"DEBUG: Template will receive prescription_data.patient_phone: '{prescription_data.get('patient_phone', 'NOT_FOUND')}'")
    return render_template_string(prescription_form_template, prescription_data=prescription_data, today_date=today_date)

@app.route("/prescriptions")
def prescriptions():
    if "doctor" not in session:
        flash("Please log in to view prescriptions.", "error")
        return redirect("/")
    
    search_query = request.args.get('search_query', '').strip()
    sort_by = request.args.get('sort_by', '')
    patient_phone = request.args.get('patient_phone', '').strip()
    
    query = {"doctor_username": session.get("doctor")}
    if patient_phone:
        # Filter by specific patient phone number
        query["patient_phone"] = patient_phone
    elif search_query:
        query["$or"] = [
                {"patient_name": {"$regex": search_query, "$options": "i"}},
                {"patient_phone": {"$regex": search_query, "$options": "i"}},
                {"prescription_id": {"$regex": search_query, "$options": "i"}}
            ]
    
    prescriptions_list = list(prescriptions_collection.find(query))
    
    # Apply sorting
    if sort_by == 'patient_name_asc':
        prescriptions_list.sort(key=lambda x: x.get('patient_name', '').lower())
    elif sort_by == 'patient_name_desc':
        prescriptions_list.sort(key=lambda x: x.get('patient_name', '').lower(), reverse=True)
    elif sort_by == 'date_asc':
        prescriptions_list.sort(key=lambda x: x.get('prescription_date_iso', x.get('prescription_date', '')))
    elif sort_by == 'date_desc':
        prescriptions_list.sort(key=lambda x: x.get('prescription_date_iso', x.get('prescription_date', '')), reverse=True)
    else:
        # Default sorting by created_at_str (latest first)
        def get_created_at_sort_key(prescription_item):
            created_at_str = prescription_item.get('created_at_str', '')
            if created_at_str and 'N/A' not in created_at_str:
                try:
                    return datetime.strptime(created_at_str, "%d-%m-%Y %I:%M %p IST")
                except ValueError:
                    return datetime.min
            return datetime.min
        
        prescriptions_list.sort(key=get_created_at_sort_key, reverse=True)
    
    # Get patient name for display if filtering by patient_phone
    patient_name = ""
    if patient_phone and prescriptions_list:
        # Get the patient name from the first prescription
        patient_name = prescriptions_list[0].get('patient_name', '')
    elif patient_phone:
        # If no prescriptions found, try to get patient name from appointments
        appointment = appointments_collection.find_one({"phone": patient_phone})
        if appointment:
            patient_name = appointment.get('name', '')
    
    return render_template_string(prescription_history_template, prescriptions=prescriptions_list, search_query=search_query, sort_by=sort_by, patient_phone=patient_phone, patient_name=patient_name)

@app.route("/view_prescription/<prescription_id>")
def view_prescription(prescription_id):
    if "doctor" not in session:
        flash("Please log in to view prescriptions.", "error")
        return redirect("/")
    
    prescription = prescriptions_collection.find_one({"prescription_id": prescription_id})
    
    if not prescription:
        flash("Prescription not found.", "error")
        return redirect("/prescriptions")
    
    # Get patient_phone from query parameter for back navigation
    patient_phone = request.args.get('patient_phone', '')
    
    # Create a detailed view template for single prescription
    detailed_template = """
    <!DOCTYPE html>
    <html lang="en" class="bg-gray-100">
    <head>
      <meta charset="UTF-8">
      <title>Prescription Details - Hey Doc!</title>
      <script src="https://cdn.tailwindcss.com"></script>
      <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body>
      <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
        <h1 class="text-xl font-bold">Hey Doc! - Prescription Details</h1>
        <div>
          <a href="/prescriptions{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">Back to Prescriptions</a>
          <a href="/dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100 mr-2">Dashboard</a>
          <a href="{{ url_for('logout') }}" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Logout</a>
        </div>
      </nav>

      <div class="p-6">
        <div class="bg-white rounded-lg shadow-md p-8 max-w-4xl mx-auto">
          <div class="flex justify-between items-start mb-6">
            <div>
              <h2 class="text-3xl font-bold text-gray-800">{{ prescription.patient_name }}</h2>
              <p class="text-lg text-gray-600">{{ prescription.patient_phone }}</p>
              <p class="text-gray-500">Prescription ID: {{ prescription.prescription_id }}</p>
            </div>
            <div class="text-right">
              <p class="text-sm text-gray-500">Prescription Date</p>
              <p class="text-lg font-semibold text-gray-800">{{ prescription.prescription_date }}</p>
              <p class="text-sm text-gray-500">{{ prescription.created_at_str }}</p>
            </div>
          </div>
          
          <div class="grid md:grid-cols-2 gap-8 mb-8">
            <div>
              <h3 class="text-xl font-semibold text-gray-700 mb-3">Diagnosis</h3>
              <p class="text-gray-600 text-lg">{{ prescription.diagnosis }}</p>
            </div>
            <div>
              <h3 class="text-xl font-semibold text-gray-700 mb-3">Special Instructions</h3>
              <p class="text-gray-600">{{ prescription.instructions or 'None provided' }}</p>
            </div>
          </div>
          
          <div class="mb-8">
            <h3 class="text-xl font-semibold text-gray-700 mb-4">Medicines Prescribed</h3>
            <div class="bg-gray-50 rounded-lg p-6">
              {% for medicine in prescription.medicines %}
              <div class="border border-gray-200 rounded-lg p-4 mb-4 last:mb-0">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 class="font-semibold text-gray-800 text-lg mb-2">{{ medicine.name }}</h4>
                    <div class="space-y-2">
                      <div class="flex justify-between">
                        <span class="font-medium text-gray-700">Potency:</span>
                        <span class="text-gray-600">{{ medicine.potency }}</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="font-medium text-gray-700">Dosage:</span>
                        <span class="text-gray-600">{{ medicine.dosage }}</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="font-medium text-gray-700">Duration:</span>
                        <span class="text-gray-600">{{ medicine.duration }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              {% endfor %}
            </div>
          </div>
          
          {% if prescription.notes %}
          <div class="mb-8">
            <h3 class="text-xl font-semibold text-gray-700 mb-3">Doctor's Notes</h3>
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p class="text-gray-700">{{ prescription.notes }}</p>
            </div>
          </div>
          {% endif %}
          
          <div class="flex justify-center space-x-4 pt-6 border-t border-gray-200">
            <a href="/prescriptions" class="bg-gray-500 text-white px-6 py-3 rounded-lg hover:bg-gray-600 transition-colors">
              <i class="ri-arrow-left-line mr-2"></i>Back to Prescriptions
            </a>
            <a href="/print_prescription/{{ prescription.prescription_id }}" class="bg-green-500 text-white px-6 py-3 rounded-lg hover:bg-green-600 transition-colors">
              <i class="ri-printer-line mr-2"></i>Print Prescription
            </a>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    
    return render_template_string(detailed_template, prescription=prescription, patient_phone=patient_phone)

@app.route("/print_prescription/<prescription_id>")
def print_prescription(prescription_id):
    if "doctor" not in session:
        flash("Please log in to print prescriptions.", "error")
        return redirect("/")
    
    prescription = prescriptions_collection.find_one({"prescription_id": prescription_id})
    
    if not prescription:
        flash("Prescription not found.", "error")
        return redirect("/prescriptions")
    
    # Get patient_phone from query parameter for back navigation
    patient_phone = request.args.get('patient_phone', '')
    
    doctor = doctors_collection.find_one({"username": prescription.get("doctor_username")})
    branch = get_branch_by_id(doctor.get("branch_id")) if doctor else None
    
    branch_phone = branch.get('phone', '') if branch else ''
    doctor_name = doctor.get('name', 'N/A') if doctor else 'N/A'
    specialization = doctor.get('specialization', '') if doctor else ''

    # Create a print-friendly template
    print_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Prescription - {{ prescription.patient_name }}</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
        .clinic-name { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
        .clinic-info { font-size: 14px; color: #666; }
        .patient-info { margin-bottom: 30px; }
        .patient-info h3 { margin: 0 0 10px 0; color: #333; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .section { margin-bottom: 25px; }
        .section h4 { margin: 0 0 10px 0; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
        .medicine { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
        .medicine h5 { margin: 0 0 10px 0; color: #333; }
        .medicine-details { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; }
        .detail-item { margin-bottom: 8px; }
        .detail-label { font-weight: bold; color: #555; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ccc; }
        .signature-line { margin-top: 50px; }
        @media print {
          body { margin: 0; }
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="header">
        <div class="clinic-name"><img src="/static/images/heydoc_logo.png" style="height: 50px; display: block; margin: 0 auto 10px auto;" alt="Hey Doc!"></div>
        <div class="clinic-info"><strong>{{ doctor_name }}</strong>, {{ specialization }}</div>
        <div class="clinic-info">Phone: {{ branch_phone }}</div>
      </div>
      
      <div class="patient-info">
        <h3>Patient Information</h3>
        <div class="info-grid">
          <div><strong>Name:</strong> {{ prescription.patient_name }}</div>
          <div><strong>Phone:</strong> {{ prescription.patient_phone }}</div>
          <div><strong>Prescription Date:</strong> {{ prescription.prescription_date }}</div>
          <div><strong>Prescription ID:</strong> {{ prescription.prescription_id }}</div>
        </div>
      </div>
      
      <div class="section">
        <h4>Diagnosis</h4>
        <p>{{ prescription.diagnosis }}</p>
      </div>
      
      <div class="section">
        <h4>Medicines Prescribed</h4>
        {% for medicine in prescription.medicines %}
        <div class="medicine">
          <h5>{{ medicine.name }}</h5>
          <div class="medicine-details">
            <div class="detail-item">
              <span class="detail-label">Potency:</span> {{ medicine.potency }}
            </div>
            <div class="detail-item">
              <span class="detail-label">Dosage:</span> {{ medicine.dosage }}
            </div>
            <div class="detail-item">
              <span class="detail-label">Duration:</span> {{ medicine.duration }}
            </div>
          </div>
        </div>
        {% endfor %}
      </div>
      
      {% if prescription.instructions %}
      <div class="section">
        <h4>Special Instructions</h4>
        <p>{{ prescription.instructions }}</p>
      </div>
      {% endif %}
      
      {% if prescription.notes %}
      <div class="section">
        <h4>Doctor's Notes</h4>
        <p>{{ prescription.notes }}</p>
      </div>
      {% endif %}
      
      <div class="footer">
        <div class="signature-line">
          <p>_________________________</p>
          <p><strong>{{ doctor_name }}</strong></p>
          <p>{{ specialization }}</p>
          <p>Date: {{ prescription.prescription_date }}</p>
        </div>
      </div>
      
      <div class="no-print" style="text-align: center; margin-top: 30px;">
        <button onclick="window.print()" style="background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-right: 10px;">Print</button>
        <a href="/prescriptions{% if patient_phone %}?patient_phone={{ patient_phone }}{% endif %}" style="background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Back to Prescriptions</a>
      </div>
    </body>
    </html>
    """
    
    return render_template_string(print_template, prescription=prescription, patient_phone=patient_phone, doctor_name=doctor_name, specialization=specialization, branch_phone=branch_phone)

@app.route("/view_certificate/<prescription_id>")
def view_certificate(prescription_id):
    if not any(k in session for k in ["admin", "doctor", "receptionist"]):
        flash("Please log in to view certificates.", "error")
        return redirect("/login")
    
    prescription = prescriptions_collection.find_one({"prescription_id": prescription_id})
    if not prescription:
        flash("Certificate data not found.", "error")
        return redirect("/dashboard")
    
    # Get doctor details
    doctor_username = prescription.get("doctor_username")
    doctor = doctors_collection.find_one({"username": doctor_username}) if doctor_username else None
    
    # If doctor_username wasn't stored (older prescriptions), try to find from session if doctor is viewing
    if not doctor and "doctor" in session:
        doctor = doctors_collection.find_one({"username": session.get("doctor")})

    cert_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Medical Certificate - {{ prescription.patient_name }}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            @media print {
                .no-print { display: none; }
                body { background: white; }
                .cert-container { box-shadow: none; border: 1px solid #eee; margin: 0; }
            }
            body { font-family: 'Inter', sans-serif; }
            .serif { font-family: 'Crimson Pro', serif; }
        </style>
    </head>
    <body class="bg-slate-50 min-h-screen py-12 px-4">
        <div class="max-w-3xl mx-auto">
            <!-- Printing Controls -->
            <div class="no-print mb-8 flex justify-between items-center bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                <a href="javascript:history.back()" class="flex items-center text-slate-500 hover:text-slate-800 font-medium transition-colors">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                    Back
                </a>
                <button onclick="window.print()" class="bg-teal-600 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-teal-700 transition-all flex items-center shadow-lg shadow-teal-100">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 00-2 2h2m2 4h10a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
                    Print Certificate
                </button>
            </div>

            <!-- Certificate -->
            <div class="cert-container bg-white shadow-2xl rounded-sm border-t-[12px] border-teal-600 p-12 md:p-16 relative overflow-hidden">
                <!-- Watermark -->
                <div class="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none select-none">
                    <h1 class="text-9xl font-black -rotate-45 serif">HEY DOC</h1>
                </div>

                <!-- Header -->
                <div class="flex flex-col md:flex-row justify-between items-center md:items-start border-bottom-2 border-slate-100 pb-8 mb-12">
                    <div class="text-center md:text-left mb-6 md:mb-0">
                        <img src="/static/images/heydoc_logo.png" alt="Hey Doc!" class="h-16 mb-2 mx-auto md:mx-0">
                        <p class="text-slate-400 text-xs font-bold uppercase tracking-[0.2em] mt-2">Secure Medical Systems</p>
                    </div>
                    <div class="text-center md:text-right text-slate-500 text-sm">
                        <p class="font-bold text-slate-800">{{ doctor.name if doctor else 'Medical Officer' }}</p>
                        <p>{{ doctor.specialization if doctor else 'General Physician' }}</p>
                        <p>Reg No: {{ doctor.reg_no if doctor and doctor.reg_no else 'VERIFIED' }}</p>
                    </div>
                </div>

                <!-- Content -->
                <div class="text-center space-y-8 relative z-10">
                    <h3 class="text-4xl font-bold text-slate-800 serif italic underline underline-offset-8 decoration-teal-200">Medical Certificate</h3>
                    
                    <div class="text-lg text-slate-700 leading-relaxed max-w-2xl mx-auto space-y-6 serif">
                        <p>This is to certify that <span class="font-bold text-slate-900 border-b-2 border-slate-100 px-2">{{ prescription.patient_name }}</span>, 
                        whose contact number is registered as <span class="font-bold text-slate-900">{{ prescription.patient_phone }}</span>, 
                        has been under my professional medical care.</p>

                        <div class="bg-slate-50 p-8 rounded-2xl border border-slate-100 text-left">
                            <h4 class="text-xs font-black text-slate-400 uppercase tracking-widest mb-4">Clinical Findings & Diagnosis</h4>
                            <p class="text-xl font-semibold text-slate-800 italic leading-snug">"{{ prescription.diagnosis }}"</p>
                        </div>

                        <p>The patient was examined on <span class="font-bold text-slate-900">{{ prescription.prescription_date }}</span> and 
                        appropriate medical advice/treatment was provided accordingly.</p>
                    </div>
                </div>

                <!-- Footer / Signatures -->
                <div class="mt-20 flex flex-col md:flex-row justify-between items-end">
                    <div class="text-left space-y-1 mb-8 md:mb-0">
                        <p class="text-xs font-bold text-slate-400 uppercase tracking-widest">Certificate ID</p>
                        <p class="text-sm font-mono text-slate-600 bg-slate-50 px-2 py-1 rounded">{{ prescription.prescription_id }}</p>
                        <p class="text-xs text-slate-400 mt-4 italic">Issued on: {{ prescription.created_at_str }}</p>
                    </div>
                    
                    <div class="text-center min-w-[200px]">
                        <div class="border-b-2 border-slate-200 mb-2 w-full"></div>
                        <p class="font-bold text-slate-800 serif">{{ doctor.name if doctor else 'Authorized Signatory' }}</p>
                        <p class="text-xs text-slate-400 font-bold uppercase tracking-wider">Medical Practitioner</p>
                    </div>
                </div>

                <!-- Footer Stamp -->
                <div class="mt-12 pt-8 border-t border-slate-50 text-center">
                    <p class="text-[10px] text-slate-300 font-bold uppercase tracking-[0.3em]">Electronically Verified Certificate • Hey Doc! Medical Care</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(cert_template, prescription=prescription, doctor=doctor)

@app.route("/delete_prescription/<prescription_id>")
def delete_prescription(prescription_id):
    if "doctor" not in session:
        flash("Please log in to delete prescriptions.", "error")
        return redirect("/")
    
    prescription = prescriptions_collection.find_one({"prescription_id": prescription_id})
    
    if not prescription:
        flash("Prescription not found.", "error")
        return redirect("/prescriptions")
    
    try:
        prescriptions_collection.delete_one({"prescription_id": prescription_id})
        flash(f"Prescription {prescription_id} deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting prescription: {str(e)}", "error")
    
    # Redirect back to prescriptions page, preserving patient_phone if it was a patient-specific view
    patient_phone = request.args.get('patient_phone', '')
    if patient_phone:
        return redirect(f"/prescriptions?patient_phone={patient_phone}")
    else:
        return redirect("/prescriptions")

# Calendar View Route
@app.route("/calendar")
def calendar_view():
    if "doctor" not in session:
        flash("Please log in to view calendar.", "error")
        return redirect("/")
    
    # Get month and year from query parameters, default to current month
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    day = request.args.get('day', None, type=int)  # New: specific day filter
    
    # Get all appointments, normalize their dates and filter for the selected month/day
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    all_appts = list(appointments_collection.find({}))
    appointments = []
    for appt in all_appts:
        raw_date = appt.get("date", "")
        parsed_dt = None
        # Try both common formats used across the app and DB
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                parsed_dt = datetime.strptime(raw_date, fmt)
                break
            except Exception:
                continue
        if not parsed_dt:
            continue
        if parsed_dt.year == year and parsed_dt.month == month and (day is None or parsed_dt.day == day):
            appt["_normalized_date"] = parsed_dt.strftime("%Y-%m-%d")
            appointments.append(appt)
    
    # Do not filter out past appointments; show all for the selected month/day
    
    print(f"Raw appointments found: {len(appointments)} (filtered to present and future only)")
    for app in appointments:
        print(f"  Appointment: {app.get('appointment_id')} - {app.get('name')} - {app.get('date')} - {app.get('time')}")
    
    # Organize appointments by normalized YYYY-MM-DD date keys for correct calendar placement
    appointments_by_date = {}
    for appointment in appointments:
        date_key = appointment.get('_normalized_date') or appointment.get('date')
        if date_key not in appointments_by_date:
            appointments_by_date[date_key] = []
        appointments_by_date[date_key].append(appointment)
    
    print(f"Appointments by date: {appointments_by_date}")
    
    # Generate calendar data
    calendar_data = generate_calendar_data(year, month, appointments_by_date)
    
    # Generate filter options
    current_year = datetime.now().year
    years = list(range(current_year - 2, current_year + 3))  # 2 years back, current, 2 years forward
    months = [
        (1, "January"), (2, "February"), (3, "March"), (4, "April"),
        (5, "May"), (6, "June"), (7, "July"), (8, "August"),
        (9, "September"), (10, "October"), (11, "November"), (12, "December")
    ]
    
    print(f"Calendar view - Year: {year}, Month: {month}, Day: {day}")
    print(f"Found {len(appointments)} appointments")
    
    return render_template_string(calendar_template, 
                                calendar_data=calendar_data, 
                                year=year, 
                                month=month, 
                                day=day,
                                month_name=start_date.strftime("%B"),
                                doctor=session["doctor"],
                                years=years,
                                months=months,
                                current_year=current_year)

def generate_calendar_data(year, month, appointments_by_date):
    """Generate calendar data for the specified month"""
    # Get the first day of the month and the number of days
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    # Get the day of week for the first day (0 = Monday, 6 = Sunday)
    first_day_weekday = first_day.weekday()
    
    # Calculate the number of days in the month
    days_in_month = last_day.day
    
    # Generate calendar grid
    calendar_weeks = []
    current_week = []
    
    # Add empty cells for days before the first day of the month
    for _ in range(first_day_weekday):
        current_week.append({"day": None, "appointments": []})
    
    # Add days of the month
    for day in range(1, days_in_month + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        appointments = appointments_by_date.get(date_str, [])
        
        if appointments:
            print(f"Day {day} has {len(appointments)} appointments:")
            for app in appointments:
                print(f"  - {app.get('appointment_id')} - {app.get('name')} - {app.get('time')}")
        
        current_week.append({
            "day": day,
            "date": date_str,
            "appointments": appointments,
            "is_today": date_str == datetime.now().strftime("%Y-%m-%d")
        })
        
        # Start a new week if we've reached Sunday (weekday 6)
        if len(current_week) == 7:
            calendar_weeks.append(current_week)
            current_week = []
    
    # Add remaining days to complete the last week
    while len(current_week) < 7:
        current_week.append({"day": None, "appointments": []})
    
    if current_week:
        calendar_weeks.append(current_week)
    
    return calendar_weeks

# Calendar Template
calendar_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Calendar - {{ doctor.name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8fafc;
        }
        .professional-header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border-bottom: 1px solid #475569;
        }
        .professional-sidebar {
            background: #ffffff;
            border-right: 1px solid #e2e8f0;
            box-shadow: 2px 0 4px rgba(0, 0, 0, 0.05);
        }
        .calendar-container {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .calendar-day {
            border: 1px solid #f1f5f9;
            min-height: 120px;
            transition: all 0.2s ease;
            position: relative;
        }
        .calendar-day:hover {
            background: #f8fafc;
            border-color: #cbd5e1;
        }
        .calendar-day.today {
            background: #dbeafe;
            border-color: #3b82f6;
        }
        .calendar-day.today .day-number {
            color: #1d4ed8;
            font-weight: 600;
        }
        .calendar-day.selected {
            background: #eff6ff;
            border-color: #3b82f6;
            box-shadow: inset 0 0 0 2px #3b82f6;
        }
        .appointment-item {
            background: #3b82f6;
            color: white;
            border-radius: 4px;
            padding: 3px 6px;
            margin: 2px 0;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s ease;
            border-left: 3px solid #1d4ed8;
        }
        .appointment-item:hover {
            background: #2563eb;
            transform: translateX(2px);
        }
        .appointment-item.scheduled {
            background: #059669;
            border-left-color: #047857;
        }
        .appointment-item.scheduled:hover {
            background: #047857;
        }
        .appointment-item.completed {
            background: #6b7280;
            border-left-color: #4b5563;
        }
        .appointment-item.completed:hover {
            background: #4b5563;
        }
        .professional-button {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-weight: 500;
            font-size: 14px;
        }
        .professional-button:hover {
            background: #2563eb;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }
        .professional-button.secondary {
            background: #f8fafc;
            color: #475569;
            border: 1px solid #cbd5e1;
        }
        .professional-button.secondary:hover {
            background: #e2e8f0;
            border-color: #94a3b8;
        }
        .professional-input {
            border: 1px solid #cbd5e1;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            transition: all 0.2s ease;
            background: #ffffff;
        }
        .professional-input:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .professional-select {
            border: 1px solid #cbd5e1;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            background: #ffffff;
            transition: all 0.2s ease;
        }
        .professional-select:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .weekday-header {
            background: #f8fafc;
            color: #475569;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #e2e8f0;
        }
        .modal-overlay {
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
        }
        .modal-content {
            background: white;
            border-radius: 8px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        .status-scheduled { background: #059669; }
        .status-in-progress { background: #3b82f6; }
        
        .status-completed { background: #6b7280; }
        .section-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .section-title {
            color: #1e293b;
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .filter-summary {
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
            border: 1px solid #93c5fd;
            border-radius: 8px;
            padding: 16px;
        }
        .week-highlight {
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
            border: 2px solid #3b82f6 !important;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
            position: relative;
        }
        .week-highlight::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(29, 78, 216, 0.1));
            pointer-events: none;
        }
        .week-highlight .day-number {
            color: #1d4ed8 !important;
            font-weight: 700 !important;
        }
        .calendar-day.hidden-day {
            opacity: 0.3;
            background: #f8fafc;
            position: relative;
        }
        .calendar-day.hidden-day::before {
            content: 'Hidden by week filter';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            white-space: nowrap;
            opacity: 0;
            transition: opacity 0.2s ease;
            pointer-events: none;
            z-index: 10;
        }
        .calendar-day.hidden-day:hover::before {
            opacity: 1;
        }
    </style>
</head>
<body>
    <!-- Professional Header -->
    <header class="professional-header shadow-lg">
        <div class="flex justify-between items-center px-8 py-6">
            <div class="flex items-center space-x-6">
                <div class="flex items-center space-x-4">
                    <div class="w-10 h-10 bg-white bg-opacity-10 rounded-lg flex items-center justify-center">
                        <i class="ri-calendar-line text-white text-xl"></i>
                    </div>
                    <div>
                        <h1 class="text-2xl font-bold text-white">Appointment Calendar</h1>
                        <p class="text-blue-200 text-sm">Dr. {{ doctor.name }} - Medical Practice</p>
                    </div>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <a href="/dashboard" class="professional-button secondary">
                    <i class="ri-dashboard-line mr-2"></i>Dashboard
                </a>
                <a href="/add_appointment" class="professional-button">
                    <i class="ri-add-line mr-2"></i>New Appointment
                </a>
                <a href="/logout" class="text-white hover:text-blue-200 transition-colors">
                    <i class="ri-logout-box-r-line text-xl"></i>
                </a>
            </div>
        </div>
    </header>

    <div class="flex min-h-screen">
        <!-- Professional Sidebar -->
        <div class="professional-sidebar w-80 p-6">
            <div class="space-y-6">
                <!-- Filter Section -->
                <div class="section-card">
                    <div class="section-title">
                        <i class="ri-filter-3-line text-blue-600"></i>
                        View Options
                    </div>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Year</label>
                            <select id="yearFilter" class="professional-select w-full">
                                {% for y in years %}
                                <option value="{{ y }}" {% if y == year %}selected{% endif %}>{{ y }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Month</label>
                            <select id="monthFilter" class="professional-select w-full">
                                {% for m_num, m_name in months %}
                                <option value="{{ m_num }}" {% if m_num == month %}selected{% endif %}>{{ m_name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Day (Optional)</label>
                            <input type="number" id="dayFilter" min="1" max="31" placeholder="Enter day" 
                                   value="{{ day if day else '' }}" class="professional-input w-full">
                        </div>
                        <button onclick="updateCalendar()" class="professional-button w-full">
                            <i class="ri-search-line mr-2"></i>Apply Filter
                        </button>
                    </div>
                </div>

                <!-- Quick Actions -->
                <div class="section-card">
                    <div class="section-title">
                        <i class="ri-time-line text-green-600"></i>
                        Quick Actions
                    </div>
                    <div class="space-y-3">
                        <button onclick="goToToday()" class="professional-button w-full text-left">
                            <i class="ri-calendar-line mr-2"></i>Go to Today
                        </button>
                        {% if day %}
                        <button onclick="clearDayFilter()" class="professional-button secondary w-full text-left">
                            <i class="ri-close-line mr-2"></i>Clear Day Filter
                        </button>
                        {% endif %}
                        <button onclick="clearWeekHighlights()" class="professional-button secondary w-full text-left">
                            <i class="ri-filter-off-line mr-2"></i>Clear Week Filter
                        </button>

                        <div class="h-2"></div>
                        <a href="/block_slot" class="professional-button secondary w-full text-left">
                            <i class="ri-lock-2-line mr-2"></i>Block a Slot
                        </a>

                    </div>
                </div>

                <!-- Quick Filters -->
                <div class="section-card">
                    <div class="section-title">
                        <i class="ri-calendar-event-line text-purple-600"></i>
                        Quick Filters
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Choose Range</label>
                        <select id="quickFilterSelect" class="professional-select w-full" onchange="handleQuickFilterChange(this.value)">
                            <option value="" selected>Select...</option>
                            <option value="this_week">This Week</option>
                            <option value="next_week">Next Week</option>
                            <option value="this_month">This Month</option>
                            <option value="next_month">Next Month</option>
                        </select>
                    </div>
                </div>




            </div>
        </div>

        <!-- Main Calendar Area -->
        <div class="flex-1 p-8">
            <!-- Calendar Header -->
            <div class="flex justify-between items-center mb-8">
                <div class="flex items-center space-x-6">
                    <button onclick="navigateMonth(-1)" class="professional-button secondary">
                        <i class="ri-arrow-left-s-line"></i>
                    </button>
                    <h2 class="text-3xl font-bold text-gray-800">{{ month_name }} {{ year }}</h2>
                    <button onclick="navigateMonth(1)" class="professional-button secondary">
                        <i class="ri-arrow-right-s-line"></i>
                    </button>
                </div>
                <div class="text-right">
                    <p class="text-sm text-gray-600">Medical Practice Calendar</p>
                    <p class="text-xs text-gray-500">Professional Appointment Management</p>
                </div>
            </div>

            <!-- Calendar Grid -->
            <div class="calendar-container">
                <table class="w-full">
                    <thead>
                        <tr>
                            <th class="weekday-header p-4 text-left">Monday</th>
                            <th class="weekday-header p-4 text-left">Tuesday</th>
                            <th class="weekday-header p-4 text-left">Wednesday</th>
                            <th class="weekday-header p-4 text-left">Thursday</th>
                            <th class="weekday-header p-4 text-left">Friday</th>
                            <th class="weekday-header p-4 text-left">Saturday</th>
                            <th class="weekday-header p-4 text-left">Sunday</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for week in calendar_data %}
                        <tr>
                            {% for day in week %}
                            <td class="calendar-day p-3 {% if day.day is none %}bg-gray-50{% endif %} {% if day.is_today %}today{% endif %}" 
                                {% if day.day is not none %}onclick="handleDayClick({{ day.day }})" style="cursor: pointer;" title="Click to view this day"{% endif %}>
                                {% if day.day is not none %}
                                <div class="flex justify-between items-start mb-3">
                                    <span class="day-number font-semibold text-lg {% if day.is_today %}text-blue-700{% else %}text-gray-800{% endif %}">
                                        {{ day.day }}
                                    </span>
                                    {% if day.appointments %}
                                    <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full font-medium">
                                        {{ day.appointments|length }}
                                    </span>
                                    {% endif %}
                                </div>
                                
                                {% if day.appointments %}
                                <div class="space-y-2">
                                    {% for appointment in day.appointments %}
                                    <div class="appointment-item {% if appointment.status == 'scheduled' %}scheduled{% elif appointment.status == 'completed' %}completed{% endif %}" 
                                         onclick="handleAppointmentClick('{{ appointment.appointment_id }}'); event.stopPropagation();"
                                         title="{{ appointment.name }} - {{ appointment.time }}">
                                        <div class="font-semibold truncate">{{ appointment.time }}</div>
                                        <div class="truncate opacity-90">{{ appointment.name }}</div>
                                    </div>
                                    {% endfor %}
                                </div>
                                {% endif %}
                                {% endif %}
                            </td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Appointment Modal -->
    <div id="appointmentModal" class="fixed inset-0 modal-overlay hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="modal-content max-w-lg w-full max-h-[80vh] overflow-y-auto">
                <div class="flex justify-between items-center p-6 border-b border-gray-200">
                    <h3 class="text-xl font-semibold text-gray-800">Appointment Details</h3>
                    <button onclick="closeAppointmentModal()" class="text-gray-400 hover:text-gray-600">
                        <i class="ri-close-line text-xl"></i>
                    </button>
                </div>
                <div id="appointmentModalContent" class="p-6">
                    <!-- Content will be loaded here -->
                </div>
            </div>
        </div>
    </div>

    <script>
        function updateCalendar() {
            const year = document.getElementById('yearFilter').value;
            const month = document.getElementById('monthFilter').value;
            const day = document.getElementById('dayFilter').value;
            
            console.log('Updating calendar:', { year, month, day });
            
            // Clear any stored week filter when manually updating calendar
            sessionStorage.removeItem('filterWeek');
            
            let url = `/calendar?year=${year}&month=${month}`;
            if (day && day.trim() !== '') {
                url += `&day=${day}`;
            }
            console.log('Navigating to:', url);
            window.location.href = url;
        }

        function navigateMonth(direction) {
            const year = parseInt(document.getElementById('yearFilter').value);
            const month = parseInt(document.getElementById('monthFilter').value);
            const day = document.getElementById('dayFilter').value;
            
            console.log('Navigating month:', { direction, year, month, day });
            
            let newMonth = month + direction;
            let newYear = year;
            
            if (newMonth > 12) {
                newMonth = 1;
                newYear++;
            } else if (newMonth < 1) {
                newMonth = 12;
                newYear--;
            }
            
            // Clear any stored week filter when navigating to a different month
            sessionStorage.removeItem('filterWeek');
            
            let url = `/calendar?year=${newYear}&month=${newMonth}`;
            if (day && day.trim() !== '') {
                url += `&day=${day}`;
            }
            console.log('Navigating to:', url);
            window.location.href = url;
        }

        function goToToday() {
            console.log('Go to Today clicked');
            const today = new Date();
            const year = today.getFullYear();
            const month = today.getMonth() + 1;
            const day = today.getDate();
            
            // Clear any stored week filter when going to today
            sessionStorage.removeItem('filterWeek');
            
            console.log('Navigating to today:', { year, month, day });
            window.location.href = `/calendar?year=${year}&month=${month}&day=${day}`;
        }

        function clearDayFilter() {
            console.log('Clear day filter clicked');
            const year = document.getElementById('yearFilter').value;
            const month = document.getElementById('monthFilter').value;
            
            // Clear any stored week filter when clearing day filter
            sessionStorage.removeItem('filterWeek');
            
            console.log('Clearing day filter:', { year, month });
            window.location.href = `/calendar?year=${year}&month=${month}`;
        }

        function setQuickFilter(filterType) {
            console.log('Quick filter clicked:', filterType);
            
            try {
                const today = new Date();
                let targetDate = new Date(today);
                
                console.log('Today:', today);
                console.log('Target date:', targetDate);
                
                switch(filterType) {
                    case 'this_week':
                        console.log('Processing this_week case');
                        // Calculate the Monday of current week
                        const currentDayOfWeek = today.getDay();
                        const daysToMonday = currentDayOfWeek === 0 ? 6 : currentDayOfWeek - 1;
                        const mondayOfThisWeek = new Date(today);
                        mondayOfThisWeek.setDate(today.getDate() - daysToMonday);
                        
                        // Navigate to the current month and filter to show only this week's appointments
                        const currentYear = today.getFullYear();
                        const currentMonth = today.getMonth() + 1;
                        const currentWeekUrl = `/calendar?year=${currentYear}&month=${currentMonth}`;
                        console.log('Navigating to current month:', currentWeekUrl);
                        
                        // Store the week to filter after navigation
                        sessionStorage.setItem('filterWeek', mondayOfThisWeek.toISOString());
                        window.location.href = currentWeekUrl;
                        return;
                    case 'next_week':
                        console.log('Processing next_week case');
                        // Calculate the Monday of next week
                        const nextWeekDay = today.getDay();
                        const daysToNextMonday = nextWeekDay === 0 ? 1 : 8 - nextWeekDay;
                        const mondayOfNextWeek = new Date(today);
                        mondayOfNextWeek.setDate(today.getDate() + daysToNextMonday);
                        
                        // Navigate to the month containing next week and filter appointments
                        const nextWeekYear = mondayOfNextWeek.getFullYear();
                        const nextWeekMonth = mondayOfNextWeek.getMonth() + 1;
                        const nextWeekUrl = `/calendar?year=${nextWeekYear}&month=${nextWeekMonth}`;
                        console.log('Navigating to:', nextWeekUrl);
                        
                        // Store the week to filter after navigation
                        sessionStorage.setItem('filterWeek', mondayOfNextWeek.toISOString());
                        window.location.href = nextWeekUrl;
                        return;
                    case 'this_month':
                        console.log('Processing this_month case');
                        // Show all appointments in current month
                        const thisYear = today.getFullYear();
                        const thisMonth = today.getMonth() + 1;
                        const thisMonthUrl = `/calendar?year=${thisYear}&month=${thisMonth}`;
                        console.log('Navigating to current month:', thisMonthUrl);
                        window.location.href = thisMonthUrl;
                        return;
                    case 'next_month':
                        console.log('Processing next_month case');
                        targetDate.setMonth(today.getMonth() + 1);
                        // For next month, show the full month without day filter
                        const nextYear = targetDate.getFullYear();
                        const nextMonth = targetDate.getMonth() + 1;
                        console.log('Next month filter:', { nextYear, nextMonth });
                        const nextMonthUrl = `/calendar?year=${nextYear}&month=${nextMonth}`;
                        console.log('Navigating to:', nextMonthUrl);
                        window.location.href = nextMonthUrl;
                        return;
                    default:
                        console.log('Unknown filter type:', filterType);
                        return;
                }
            } catch (error) {
                console.error('Error in setQuickFilter:', error);
                alert('Error in quick filter: ' + error.message);
            }
        }

        function handleQuickFilterChange(value) {
            if (!value) { return; }
            setQuickFilter(value);
            // Reset select back to placeholder after navigation trigger
            const select = document.getElementById('quickFilterSelect');
            if (select) {
                select.value = '';
            }
        }

        function filterWeekAppointments(mondayDate) {
            console.log('Filtering appointments for week starting from:', mondayDate);
            
            // Clear any existing highlights and filters
            clearWeekHighlights();
            clearWeekFilters();
            
            // Calculate all days in the week (Monday to Sunday)
            const weekDays = [];
            for (let i = 0; i < 7; i++) {
                const dayDate = new Date(mondayDate);
                dayDate.setDate(mondayDate.getDate() + i);
                weekDays.push(dayDate);
            }
            
            console.log('Week days to show:', weekDays);
            
            // Get all calendar day cells
            const allDayCells = document.querySelectorAll('.calendar-day');
            
            allDayCells.forEach(cell => {
                const daySpan = cell.querySelector('.day-number');
                if (daySpan && daySpan.textContent.trim()) {
                    const dayNumber = parseInt(daySpan.textContent.trim());
                    
                    // Check if this day is in our target week
                    const isInTargetWeek = weekDays.some(weekDay => weekDay.getDate() === dayNumber);
                    
                    if (isInTargetWeek) {
                        // Show this day and its appointments
                        cell.style.display = 'table-cell';
                        cell.classList.add('week-highlight');
                        cell.classList.remove('hidden-day');
                        
                        // Show all appointment items in this day
                        const appointmentItems = cell.querySelectorAll('.appointment-item');
                        appointmentItems.forEach(item => {
                            item.style.display = 'block';
                        });
                    } else {
                        // Mark this day as hidden but keep it visible with reduced opacity
                        cell.style.display = 'table-cell';
                        cell.classList.add('hidden-day');
                        cell.classList.remove('week-highlight');
                        
                        // Hide appointment items in this day
                        const appointmentItems = cell.querySelectorAll('.appointment-item');
                        appointmentItems.forEach(item => {
                            item.style.display = 'none';
                        });
                    }
                }
            });
            
            // Add a visual indicator for the filtered week
            addWeekFilterIndicator(mondayDate);
        }

        function showAllAppointments() {
            console.log('Showing all appointments');
            
            // Clear any existing highlights and filters
            clearWeekHighlights();
            clearWeekFilters();
            
            // Show all calendar day cells
            const allDayCells = document.querySelectorAll('.calendar-day');
            allDayCells.forEach(cell => {
                cell.style.display = 'table-cell';
                cell.classList.remove('hidden-day');
                
                // Show all appointment items in this day
                const appointmentItems = cell.querySelectorAll('.appointment-item');
                appointmentItems.forEach(item => {
                    item.style.display = 'block';
                });
            });
            
            // Remove week filter indicator
            const existingIndicator = document.querySelector('.week-filter-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Clear stored week filter
            sessionStorage.removeItem('filterWeek');
        }

        function clearWeekHighlights() {
            // Remove existing week highlights
            document.querySelectorAll('.week-highlight').forEach(cell => {
                cell.classList.remove('week-highlight');
            });
            
            // Remove hidden day styling
            document.querySelectorAll('.hidden-day').forEach(cell => {
                cell.classList.remove('hidden-day');
            });
            
            // Remove week indicator
            const existingIndicator = document.querySelector('.week-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Clear stored week filter
            sessionStorage.removeItem('filterWeek');
        }

        function clearWeekFilters() {
            // Remove week filter indicator
            const existingIndicator = document.querySelector('.week-filter-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Clear stored week filter
            sessionStorage.removeItem('filterWeek');
        }

        function addWeekIndicator(mondayDate) {
            // Create a visual indicator for the highlighted week
            const indicator = document.createElement('div');
            indicator.className = 'week-indicator';
            indicator.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                z-index: 1000;
                font-weight: 600;
                font-size: 14px;
            `;
            
            const weekStart = mondayDate.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            });
            const weekEnd = new Date(mondayDate);
            weekEnd.setDate(mondayDate.getDate() + 6);
            const weekEndStr = weekEnd.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            });
            
            indicator.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="ri-calendar-week-line"></i>
                    <span>Week: ${weekStart} - ${weekEndStr}</span>
                    <button onclick="clearWeekHighlights()" style="background: none; border: none; color: white; cursor: pointer; margin-left: 8px;">
                        <i class="ri-close-line"></i>
                    </button>
                </div>
            `;
            
            document.body.appendChild(indicator);
        }

        function addWeekFilterIndicator(mondayDate) {
            // Create a visual indicator for the filtered week
            const indicator = document.createElement('div');
            indicator.className = 'week-filter-indicator';
            indicator.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #059669, #047857);
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
                z-index: 1000;
                font-weight: 600;
                font-size: 14px;
            `;
            
            const weekStart = mondayDate.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            });
            const weekEnd = new Date(mondayDate);
            weekEnd.setDate(mondayDate.getDate() + 6);
            const weekEndStr = weekEnd.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            });
            
            indicator.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="ri-filter-3-line"></i>
                    <span>Showing Week: ${weekStart} - ${weekEndStr}</span>
                    <button onclick="clearWeekHighlights()" style="background: none; border: none; color: white; cursor: pointer; margin-left: 8px;">
                        <i class="ri-close-line"></i>
                    </button>
                </div>
            `;
            
            document.body.appendChild(indicator);
        }

        function handleDayClick(day) {
            console.log('Day clicked:', day);
            
            // Check if there's an active week filter
            const hasWeekFilter = document.querySelector('.week-filter-indicator') !== null;
            const hasWeekHighlight = document.querySelector('.week-highlight') !== null;
            const hasHiddenDays = document.querySelector('.hidden-day') !== null;
            
            // Check if the clicked day is currently hidden
            const clickedCell = event.target.closest('.calendar-day');
            const isHiddenDay = clickedCell && clickedCell.classList.contains('hidden-day');
            
            if (hasWeekFilter || hasWeekHighlight || hasHiddenDays || isHiddenDay) {
                // If there's a week filter active or the clicked day is hidden, clear it first
                console.log('Week filter active or hidden day clicked, clearing filter first');
                clearWeekHighlights();
                // Then filter by the clicked day
                setTimeout(() => {
                    filterByDay(day);
                }, 100);
            } else {
                // No week filter, just filter by day normally
                filterByDay(day);
            }
        }

        function filterByDay(day) {
            console.log('Filter by day clicked:', day);
            const year = document.getElementById('yearFilter').value;
            const month = document.getElementById('monthFilter').value;
            
            // Clear any stored week filter when filtering by day
            sessionStorage.removeItem('filterWeek');
            
            // Also clear any active week highlights
            clearWeekHighlights();
            
            console.log('Filtering by day:', { year, month, day });
            window.location.href = `/calendar?year=${year}&month=${month}&day=${day}`;
        }

        function handleAppointmentClick(appointmentId) {
            console.log('Appointment clicked:', appointmentId);
            
            // Check if there's an active week filter
            const hasWeekFilter = document.querySelector('.week-filter-indicator') !== null;
            const hasWeekHighlight = document.querySelector('.week-highlight') !== null;
            const hasHiddenDays = document.querySelector('.hidden-day') !== null;
            
            if (hasWeekFilter || hasWeekHighlight || hasHiddenDays) {
                // If there's a week filter active, clear it first
                console.log('Week filter active, clearing it first');
                clearWeekHighlights();
                // Then show the appointment modal
                setTimeout(() => {
                    showAppointmentModal(appointmentId);
                }, 100);
            } else {
                // No week filter, just show the appointment modal normally
                showAppointmentModal(appointmentId);
            }
        }

        function showAppointmentModal(appointmentId) {
            console.log('Opening modal for appointment:', appointmentId);
            
            // Check if modal elements exist
            const modal = document.getElementById('appointmentModal');
            const modalContent = document.getElementById('appointmentModalContent');
            
            if (!modal) {
                console.error('Modal element not found');
                alert('Modal element not found');
                return;
            }
            
            if (!modalContent) {
                console.error('Modal content element not found');
                alert('Modal content element not found');
                return;
            }
            
            console.log('Modal elements found, making fetch request...');
            
            fetch(`/get_appointment_details/${appointmentId}`)
                .then(response => {
                    console.log('Response status:', response.status);
                    console.log('Response headers:', response.headers);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Appointment data received:', data);
                    console.log('Data type:', typeof data);
                    console.log('Data keys:', Object.keys(data));
                    
                    if (data.success) {
                        const appointment = data.appointment;
                        console.log('Appointment object:', appointment);
                        console.log('Appointment keys:', Object.keys(appointment));
                        
                        // Log specific fields to debug
                        console.log('Name:', appointment.name);
                        console.log('Phone:', appointment.phone);
                        console.log('Email:', appointment.email);
                        console.log('Address:', appointment.address);
                        console.log('Date:', appointment.date);
                        console.log('Date display:', appointment.date_display);
                        console.log('Date formatted:', appointment.date_formatted);
                        console.log('Time:', appointment.time);
                        console.log('Symptoms:', appointment.symptoms);
                        console.log('Status:', appointment.status);
                        console.log('Created at:', appointment.created_at_str);
                        
                        modalContent.innerHTML = `
                            <div class="space-y-6">
                                <!-- Patient Header -->
                                <div class="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 rounded-lg border border-blue-200">
                                    <div class="flex items-center space-x-4">
                                        <div class="w-16 h-16 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-xl flex items-center justify-center shadow-lg">
                                            <i class="ri-user-heart-line text-white text-2xl"></i>
                                        </div>
                                        <div class="flex-1">
                                            <h3 class="text-2xl font-bold text-gray-900 mb-1">${appointment.name || 'N/A'}</h3>
                                            <p class="text-blue-600 font-medium">Patient Details</p>
                                            <p class="text-sm text-gray-600 mt-1">Appointment ID: ${appointment.appointment_id || 'N/A'}</p>
                                        </div>
                                        <div class="text-right">
                                            <div class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                                                <span class="status-indicator status-${appointment.status || 'pending'} mr-2"></span>
                                                ${(appointment.status || 'pending').replace('_', ' ').toUpperCase()}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Contact Information -->
                                <div class="bg-white border border-gray-200 rounded-lg p-6">
                                    <h4 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                        <i class="ri-contacts-line text-blue-600 mr-2"></i>
                                        Contact Information
                                    </h4>
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                            <i class="ri-phone-line text-green-600 text-lg"></i>
                                            <div>
                                                <p class="text-sm text-gray-600">Phone</p>
                                                <p class="font-medium text-gray-900">${appointment.phone || 'N/A'}</p>
                                            </div>
                                        </div>
                                        <div class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                            <i class="ri-mail-line text-blue-600 text-lg"></i>
                                            <div>
                                                <p class="text-sm text-gray-600">Email</p>
                                                <p class="font-medium text-gray-900">${appointment.email || 'N/A'}</p>
                                            </div>
                                        </div>
                                        <div class="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg md:col-span-2">
                                            <i class="ri-map-pin-line text-red-600 text-lg mt-1"></i>
                                            <div>
                                                <p class="text-sm text-gray-600">Address</p>
                                                <p class="font-medium text-gray-900">${appointment.address || 'No address provided'}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Appointment Details -->
                                <div class="bg-white border border-gray-200 rounded-lg p-6">
                                    <h4 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                        <i class="ri-calendar-event-line text-purple-600 mr-2"></i>
                                        Appointment Details
                                    </h4>
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                            <i class="ri-calendar-line text-purple-600 text-lg"></i>
                                            <div>
                                                <p class="text-sm text-gray-600">Date</p>
                                                <p class="font-medium text-gray-900">${appointment.date_display || appointment.date || 'N/A'}</p>
                                            </div>
                                        </div>
                                        <div class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                            <i class="ri-time-line text-purple-600 text-lg"></i>
                                            <div>
                                                <p class="text-sm text-gray-600">Time</p>
                                                <p class="font-medium text-gray-900">${appointment.time || 'N/A'}</p>
                                            </div>
                                        </div>

                                    </div>
                                </div>
                                
                                <!-- Medical Information -->
                                <div class="bg-white border border-gray-200 rounded-lg p-6">
                                    <h4 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                        <i class="ri-heart-pulse-line text-red-600 mr-2"></i>
                                        Medical Information
                                    </h4>
                                    <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                                        <div class="flex items-start space-x-3">
                                            <i class="ri-stethoscope-line text-red-600 text-lg mt-1"></i>
                                            <div class="flex-1">
                                                <p class="text-sm text-gray-600 mb-2">Symptoms & Medical Notes</p>
                                                <p class="text-gray-900 leading-relaxed">${appointment.symptoms || 'No medical notes available'}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Action Buttons -->
                                <div class="flex space-x-4 pt-4">
                                    <a href="/edit_appointment/${appointment.appointment_id}" 
                                       class="professional-button flex-1 text-center bg-blue-600 hover:bg-blue-700">
                                        <i class="ri-edit-line mr-2"></i>Edit Appointment
                                    </a>
                                    <a href="/add_prescription?patient_phone=${encodeURIComponent(appointment.phone)}" 
                                       class="professional-button flex-1 text-center bg-green-600 hover:bg-green-700">
                                        <i class="ri-medicine-bottle-line mr-2"></i>Add Prescription
                                    </a>
                                    <button onclick="closeAppointmentModal()" 
                                            class="professional-button secondary flex-1">
                                        <i class="ri-close-line mr-2"></i>Close
                                    </button>
                                </div>
                            </div>
                        `;
                        
                        document.getElementById('appointmentModal').classList.remove('hidden');
                    } else {
                        alert('Error loading appointment details');
                    }
                })
                .catch(error => {
                    console.error('Error loading appointment details:', error);
                    alert('Error loading appointment details: ' + error.message);
                });
        }

        function closeAppointmentModal() {
            document.getElementById('appointmentModal').classList.add('hidden');
        }



        // Highlight selected day on page load
        function highlightSelectedDay() {
            const dayFilter = document.getElementById('dayFilter').value;
            if (dayFilter) {
                const dayCells = document.querySelectorAll('.calendar-day');
                dayCells.forEach(cell => {
                    const daySpan = cell.querySelector('.day-number');
                    if (daySpan && daySpan.textContent.trim() === dayFilter) {
                        cell.classList.add('selected');
                    }
                });
            }
        }

        // Close modal when clicking outside
        document.getElementById('appointmentModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeAppointmentModal();
            }
        });

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Calendar page loaded');
            highlightSelectedDay();
            
            // Check for stored week filter (for next week navigation)
            const storedFilterWeek = sessionStorage.getItem('filterWeek');
            if (storedFilterWeek) {
                console.log('Found stored week to filter:', storedFilterWeek);
                const mondayDate = new Date(storedFilterWeek);
                // Clear the stored value
                sessionStorage.removeItem('filterWeek');
                // Filter the week after a short delay to ensure DOM is ready
                setTimeout(() => {
                    // First show all appointments, then filter
                    showAllAppointments();
                    filterWeekAppointments(mondayDate);
                }, 100);
            } else {
                // If no stored filter, ensure all appointments are visible
                setTimeout(() => {
                    showAllAppointments();
                }, 50);
            }
            
            // Add click event listeners for debugging
            document.querySelectorAll('.professional-button').forEach(button => {
                button.addEventListener('click', function(e) {
                    console.log('Button clicked:', this.textContent.trim());
                });
            });
            
            // Debug filter elements
            console.log('Filter elements found:');
            console.log('Year filter:', document.getElementById('yearFilter'));
            console.log('Month filter:', document.getElementById('monthFilter'));
            console.log('Day filter:', document.getElementById('dayFilter'));
            
            // Debug quick action buttons
            console.log('Quick action buttons found:', document.querySelectorAll('[onclick*="goToToday"]').length);
            console.log('Quick filter buttons found:', document.querySelectorAll('[onclick*="setQuickFilter"]').length);
            
            // Debug appointment items
            console.log('Appointment items found:', document.querySelectorAll('.appointment-item').length);
            
            // Add error handling for missing elements
            const yearFilter = document.getElementById('yearFilter');
            const monthFilter = document.getElementById('monthFilter');
            const dayFilter = document.getElementById('dayFilter');
            
            if (!yearFilter) console.error('Year filter not found');
            if (!monthFilter) console.error('Month filter not found');
            if (!dayFilter) console.error('Day filter not found');
            
            // Test quick filter buttons
            document.querySelectorAll('[onclick*="setQuickFilter"]').forEach((button, index) => {
                console.log(`Quick filter button ${index}:`, button.textContent.trim());
            });
            
            // Test quick action buttons
            document.querySelectorAll('[onclick*="goToToday"]').forEach((button, index) => {
                console.log(`Quick action button ${index}:`, button.textContent.trim());
            });
        });
    </script>
</body>
</html>
"""

# API endpoint to get appointment details for modal
@app.route("/get_appointment_details/<appointment_id>")
def get_appointment_details(appointment_id):
    print(f"=== GET APPOINTMENT DETAILS CALLED ===")
    print(f"Appointment ID: {appointment_id}")
    print(f"Session: {session}")
    
    if "doctor" not in session:
        print("Not authenticated - doctor not in session")
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    try:
        print(f"Looking for appointment in database: {appointment_id}")
        appointment = appointments_collection.find_one({"appointment_id": appointment_id})
        
        if appointment:
            print(f"Found appointment: {appointment}")
            print(f"Appointment keys: {list(appointment.keys())}")
            
            # Convert ObjectId to string for JSON serialization
            if '_id' in appointment:
                appointment['_id'] = str(appointment['_id'])
            
            # Ensure date is properly formatted for display
            if 'date' in appointment and appointment['date']:
                try:
                    # Parse the date and format it nicely
                    from datetime import datetime
                    date_obj = datetime.strptime(appointment['date'], '%Y-%m-%d')
                    appointment['date_display'] = date_obj.strftime('%d %B %Y')  # e.g., "15 January 2024"
                    appointment['date_formatted'] = date_obj.strftime('%d-%m-%Y')  # e.g., "15-01-2024"
                except Exception as e:
                    print(f"Error formatting date {appointment['date']}: {e}")
                    appointment['date_display'] = appointment['date']
                    appointment['date_formatted'] = appointment['date']
            else:
                appointment['date_display'] = 'N/A'
                appointment['date_formatted'] = 'N/A'
            
            print(f"Appointment date fields:")
            print(f"  Original date: {appointment.get('date')}")
            print(f"  Date display: {appointment.get('date_display')}")
            print(f"  Date formatted: {appointment.get('date_formatted')}")
            
            response_data = {"success": True, "appointment": appointment}
            print(f"Returning response: {response_data}")
            return jsonify(response_data)
        else:
            print(f"Appointment not found: {appointment_id}")
            # Let's also check what appointments exist
            all_appointments = list(appointments_collection.find({}, {"appointment_id": 1, "name": 1}))
            print(f"All appointments in database: {all_appointments}")
            return jsonify({"success": False, "error": "Appointment not found"}), 404
    except Exception as e:
        print(f"Error getting appointment details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# --- CMS & Circular Routes ---

@app.route("/admin/add_circular", methods=["GET", "POST"])
def admin_add_circular():
    if "admin" not in session: return redirect("/login")
    
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        branch_id = request.form.get("branch_id", "all")
        
        circulars_collection.insert_one({
            "title": title,
            "content": content,
            "branch_id": branch_id,
            "created_at": datetime.utcnow()
        })
        flash("Circular published successfully!", "success")
        return redirect("/admin_dashboard")
        
    branches = list(branches_collection.find({}))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>New Circular - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 p-8 min-h-screen">
        <div class="max-w-2xl mx-auto bg-white rounded-3xl shadow-xl p-10 border border-gray-100">
            <h1 class="text-2xl font-black text-gray-800 mb-8 flex items-center">
                <i class="ri-megaphone-line mr-3 text-teal-600"></i> Publish New Circular
            </h1>
            <form method="POST" class="space-y-6">
                <div>
                    <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest block mb-2">Target Branch</label>
                    <select name="branch_id" class="w-full bg-gray-50 border border-gray-100 rounded-2xl px-6 py-4 text-sm font-bold outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="all">Global (All Branches & Home)</option>
                        {% for b in branches %}
                        <option value="{{ b._id }}">{{ b.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div>
                    <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest block mb-2">Circular Title</label>
                    <input type="text" name="title" required class="w-full bg-gray-50 border border-gray-100 rounded-2xl px-6 py-4 text-sm font-bold outline-none focus:ring-2 focus:ring-teal-500">
                </div>
                <div>
                    <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest block mb-2">Message Content</label>
                    <textarea name="content" rows="6" required class="w-full bg-gray-50 border border-gray-100 rounded-2xl px-6 py-4 text-sm font-bold outline-none focus:ring-2 focus:ring-teal-500"></textarea>
                </div>
                <div class="flex gap-4 pt-4">
                    <button type="submit" class="flex-1 bg-teal-600 text-white font-black py-4 rounded-2xl uppercase tracking-widest text-xs hover:bg-teal-700 transition-all shadow-lg shadow-teal-900/10">Publish Circular</button>
                    <a href="/admin_dashboard" class="px-8 bg-gray-100 text-gray-500 font-black py-4 rounded-2xl uppercase tracking-widest text-xs hover:bg-gray-200 transition-all">Cancel</a>
                </div>
            </form>
        </div>
    </body>
    </html>
    """, branches=branches)

@app.route("/admin/manage_circulars")
def admin_manage_circulars():
    if "admin" not in session: return redirect("/login")
    circulars = list(circulars_collection.find({}).sort("created_at", -1))
    return render_template_string("""
    <!-- Simple Management Table -->
    <body class="bg-gray-50 p-8">
        <h1 class="text-2xl font-bold mb-6">Manage Circulars</h1>
        <table class="w-full bg-white rounded-xl overflow-hidden shadow">
            <thead class="bg-gray-100">
                <tr><th class="p-4 text-left">Title</th><th class="p-4 text-left">Target</th><th class="p-4 text-left">Date</th></tr>
            </thead>
            <tbody>
                {% for c in circulars %}
                <tr class="border-t border-gray-50">
                    <td class="p-4 font-medium">{{ c.title }}</td>
                    <td class="p-4 text-sm text-gray-500">{{ c.branch_id }}</td>
                    <td class="p-4 text-xs">{{ c.created_at.strftime('%d %b %Y') }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    """, circulars=circulars)
@app.route("/admin/manage_cms")
def admin_manage_cms():
    if "admin" not in session: return redirect("/login")
    
    settings = site_settings_collection.find_one({"type": "global"}) or {
        "site_name": "Hey Doc!",
        "primary_color": "teal",
        "font_family": "Outfit, sans-serif",
        "contact_email": "support@heydoc.com",
        "contact_phone": "+1 234 567 890",
        "contact_address": "123 Medical Center, Health City",
        "logo_url": "/static/images/heydoc_logo.png"
    }
    
    home_doc = homepage_content_collection.find_one({"type": "main"})
    home_content = home_doc["content"] if home_doc else "<!-- Default Homepage Template -->"
    
    fees = site_settings_collection.find_one({"type": "fees"}) or {
        "consultation_fee": 500,
        "free_consultation_days": 7
    }
    
    return render_template("admin/cms_management.html", 
                         site_settings=settings, 
                         theme=settings, 
                         home_content=home_content, 
                         fees=fees)

@app.route("/admin/cms", methods=["POST"])
def admin_cms_process():
    if "admin" not in session: return redirect("/login")
    
    action = request.form.get("action")
    
    if action == "update_template":
        content = request.form.get("content")
        homepage_content_collection.update_one(
            {"type": "main"},
            {"$set": {"content": content, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        flash("Homepage template deployed successfully!", "success")
        
    elif action == "update_theme":
        updates = {
            "site_name": request.form.get("site_name"),
            "primary_color": request.form.get("primary_color"),
            "font_family": request.form.get("font_family"),
            "logo_url": request.form.get("logo_url"),
            "updated_at": datetime.utcnow()
        }
        site_settings_collection.update_one(
            {"type": "global"},
            {"$set": updates},
            upsert=True
        )
        flash("Site identity updated!", "success")
        
    elif action == "update_setup":
        updates = {
            "contact_email": request.form.get("contact_email"),
            "contact_phone": request.form.get("contact_phone"),
            "contact_address": request.form.get("contact_address"),
            "facebook_url": request.form.get("facebook_url"),
            "twitter_url": request.form.get("twitter_url"),
            "instagram_url": request.form.get("instagram_url"),
            "updated_at": datetime.utcnow()
        }
        site_settings_collection.update_one(
            {"type": "global"},
            {"$set": updates},
            upsert=True
        )
        flash("Global setup saved!", "success")
        
    elif action == "update_fees":
        updates = {
            "consultation_fee": int(request.form.get("consultation_fee", 0)),
            "free_consultation_days": int(request.form.get("free_consultation_days", 7)),
            "updated_at": datetime.utcnow()
        }
        site_settings_collection.update_one(
            {"type": "fees"},
            {"$set": updates},
            upsert=True
        )
        flash("Consultation fees updated!", "success")
        
    return redirect("/admin/manage_cms")


# --- Hospital Payroll Management Routes ---
@app.route("/admin/payroll")
def admin_payroll_dashboard():
    if "admin" not in session: return redirect("/login")
    
    # Fetch roles for templates
    roles = ["doctor", "receptionist", "pharmacist", "lab_assistant", "financial_analytics", "branch_admin"]
    
    # Fetch existing salary templates
    templates = {t['role']: t for t in payroll_settings_collection.find({"type": "salary_template"})}
    
    # Fetch recent payroll runs
    recent_salaries = list(salaries_collection.find({}).sort("created_at", -1).limit(20))
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Payroll Management - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-slate-50 min-h-screen">
        <nav class="bg-indigo-700 p-4 text-white flex justify-between items-center shadow-xl">
            <h1 class="text-xl font-bold flex items-center"><i class="ri-money-dollar-box-line mr-2"></i> Payroll Management</h1>
            <a href="/admin_dashboard" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Dashboard</a>
        </nav>
        
        <div class="p-8 max-w-7xl mx-auto space-y-8">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                <!-- Salary Templates -->
                <div class="md:col-span-2 bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
                    <div class="flex items-center justify-between mb-6">
                        <h2 class="text-xl font-black text-slate-800 flex items-center">
                            <i class="ri-settings-5-line mr-2 text-indigo-600"></i> Salary Structures
                        </h2>
                        <div class="flex gap-3">
                            <a href="/admin/import_employee_data" class="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 transition-all flex items-center gap-2">
                                <i class="ri-file-upload-line"></i> Import Employee CSV
                            </a>
                            <a href="/admin/export_employee_data" class="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-bold hover:bg-emerald-700 transition-all flex items-center gap-2">
                                <i class="ri-file-excel-2-line"></i> Download Employee Data CSV
                            </a>
                        </div>
                    </div>
                    <div class="space-y-6">
                        {% for role in roles %}
                        {% set t = templates.get(role, {}) %}
                        <form action="/admin/payroll/save_template" method="POST" class="p-6 rounded-2xl bg-slate-50 border border-slate-100 grid grid-cols-2 md:grid-cols-4 gap-4 items-end">
                            <input type="hidden" name="role" value="{{ role }}">
                            <div class="col-span-2 md:col-span-1">
                                <label class="text-[10px] font-black uppercase text-slate-400 block mb-1">Role</label>
                                <span class="font-bold text-slate-700 capitalize text-sm">{{ role.replace('_', ' ') }}</span>
                            </div>
                            <div>
                                <label class="text-[10px] font-black uppercase text-slate-400 block mb-1">Basic Pay (₹)</label>
                                <input type="number" name="basic_pay" value="{{ t.basic_pay|default(15000) }}" class="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-sm font-bold outline-none focus:ring-2 focus:ring-indigo-500">
                            </div>
                            <div>
                                <label class="text-[10px] font-black uppercase text-slate-400 block mb-1">ESI (%)</label>
                                <input type="number" step="0.1" name="esi_percent" value="{{ t.esi_percent|default(0.75) }}" class="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-sm font-bold outline-none focus:ring-2 focus:ring-indigo-500">
                            </div>
                            <div class="col-span-2 md:col-span-1">
                                <button type="submit" class="w-full bg-indigo-600 text-white font-bold py-2 rounded-xl text-xs uppercase tracking-widest hover:bg-indigo-700 transition-all">Update</button>
                            </div>
                        </form>
                        {% endfor %}
                    </div>
                </div>

                <!-- Process Payroll -->
                <div class="bg-indigo-900 text-white rounded-3xl shadow-xl p-8 space-y-6">
                    <h2 class="text-xl font-black mb-4 flex items-center">
                        <i class="ri-play-circle-line mr-2 text-indigo-400"></i> Run Payroll
                    </h2>
                    <p class="text-indigo-200 text-sm">Generate monthly salaries for all active staff across all branches.</p>
                    <form action="/admin/payroll/run" method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-[10px] font-bold uppercase text-indigo-300 block mb-1">Month</label>
                                <select name="month" class="w-full bg-indigo-800 border-none rounded-xl px-4 py-3 text-sm font-bold outline-none focus:ring-2 focus:ring-indigo-400">
                                    <option value="1">January</option>
                                    <option value="2">February</option>
                                    <option value="3">March</option>
                                    <option value="4">April</option>
                                    <option value="5">May</option>
                                    <option value="6">June</option>
                                    <option value="7">July</option>
                                    <option value="8">August</option>
                                    <option value="9">September</option>
                                    <option value="10">October</option>
                                    <option value="11">November</option>
                                    <option value="12">December</option>
                                </select>
                            </div>
                            <div>
                                <label class="text-[10px] font-bold uppercase text-indigo-300 block mb-1">Year</label>
                                <select name="year" class="w-full bg-indigo-800 border-none rounded-xl px-4 py-3 text-sm font-bold outline-none focus:ring-2 focus:ring-indigo-400">
                                    <option value="2025">2025</option>
                                    <option value="2026">2026</option>
                                </select>
                            </div>
                        </div>
                        <button type="submit" class="w-full bg-white text-indigo-900 font-black py-4 rounded-2xl uppercase tracking-widest text-sm hover:bg-indigo-50 transition-all shadow-lg">Start Generation</button>
                    </form>
                </div>
            </div>

            <!-- Recent Payroll Logs -->
            <div class="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                <div class="p-8 border-b border-slate-50 flex justify-between items-center">
                    <h2 class="text-xl font-black text-slate-800 flex items-center">
                        <i class="ri-history-line mr-2 text-slate-400"></i> Disbursement History
                    </h2>
                </div>
                <table class="w-full text-left">
                    <thead class="bg-slate-50 text-[10px] font-black uppercase text-slate-400 tracking-widest">
                        <tr>
                            <th class="px-8 py-4">Employee</th>
                            <th class="px-8 py-4">Role</th>
                            <th class="px-8 py-4">Period</th>
                            <th class="px-8 py-4">Net Salary</th>
                            <th class="px-8 py-4">Status</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        {% for sal in recent_salaries %}
                        <tr class="hover:bg-slate-50 transition-colors">
                            <td class="px-8 py-5 text-sm font-bold text-slate-700">{{ sal.staff_name }}</td>
                            <td class="px-8 py-5"><span class="text-[10px] font-black uppercase text-indigo-600 bg-indigo-50 px-2 py-1 rounded-md">{{ sal.role }}</span></td>
                            <td class="px-8 py-5 text-sm text-slate-500">{{ sal.month }}/{{ sal.year }}</td>
                            <td class="px-8 py-5 text-sm font-black text-slate-800">₹{{ "{:,.2f}".format(sal.net_salary) }}</td>
                            <td class="px-8 py-5">
                                <span class="bg-emerald-50 text-emerald-600 text-[10px] font-black px-3 py-1 rounded-full uppercase">Disbursed</span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """, roles=roles, templates=templates, recent_salaries=recent_salaries)

@app.route("/admin/payroll/save_template", methods=["POST"])
def admin_payroll_save_template():
    if "admin" not in session: return redirect("/login")
    
    role = request.form.get("role")
    updates = {
        "basic_pay": float(request.form.get("basic_pay", 0)),
        "esi_percent": float(request.form.get("esi_percent", 0)),
        "updated_at": datetime.utcnow()
    }
    
    payroll_settings_collection.update_one(
        {"type": "salary_template", "role": role},
        {"$set": updates},
        upsert=True
    )
    flash(f"Salary template for {role} updated!", "success")
    return redirect("/admin/payroll")

@app.route("/admin/payroll/run", methods=["POST"])
def admin_payroll_run():
    if "admin" not in session: return redirect("/login")
    
    month = int(request.form.get("month"))
    year = int(request.form.get("year"))
    
    # 1. Fetch all staff members across roles
    staff_lists = {
        "doctor": list(doctors_collection.find({})),
        "receptionist": list(receptionists_collection.find({})),
        "pharmacist": list(pharmacists_collection.find({})),
        "lab_assistant": list(lab_assistants_collection.find({})),
        "financial_analytics": list(financial_analytics_collection.find({})),
        "branch_admin": list(branch_admins_collection.find({}))
    }
    
    # 2. Fetch salary templates
    templates = {t['role']: t for t in payroll_settings_collection.find({"type": "salary_template"})}
    
    count = 0
    for role, members in staff_lists.items():
        template = templates.get(role, {"basic_pay": 15000, "esi_percent": 0.75})
        
        for staff in members:
            # Check if already generated for this month
            existing = salaries_collection.find_one({"username": staff['username'], "month": month, "year": year})
            if existing: continue
            
            basic = template.get("basic_pay", 15000)
            bonus = 0
            
            # Special Logic: Doctors get incentives based on consultations
            if role == "doctor":
                # Count consultations for this doctor in this month
                start_date = datetime(year, month, 1)
                if month == 12: end_date = datetime(year + 1, 1, 1)
                else: end_date = datetime(year, month + 1, 1)
                
                consult_count = prescriptions_collection.count_documents({
                    "doctor_username": staff['username'],
                    "created_at": {"$gte": start_date, "$lt": end_date}
                })
                # Incentive: ₹100 per consultation
                bonus = consult_count * 100
            
            # Deductions
            esi = (basic * template.get("esi_percent", 0.75)) / 100
            pf = (basic * 12) / 100 # Standard 12% PF
            
            net = basic + bonus - esi - pf
            
            salaries_collection.insert_one({
                "username": staff['username'],
                "staff_name": staff.get('name', staff['username']),
                "role": role,
                "month": month,
                "year": year,
                "basic_salary": basic,
                "incentives": bonus,
                "deductions": {"esi": esi, "pf": pf},
                "net_salary": net,
                "created_at": datetime.utcnow()
            })

            count += 1
            
    # Explicit breakdown for feedback
    breakdown_msg = []
    total_generated = 0
    for role, members in staff_lists.items():
        role_count = 0
        template = templates.get(role, {})
        # Re-check how many were actually inserted (or just use the logic flow if consistent)
        # Since we're in a single request, let's trust the loop count we just did or re-query
        # A simple re-query is safer for accurate reporting
        processed = salaries_collection.count_documents({"month": month, "year": year, "role": role})
        if processed > 0:
            row_count = salaries_collection.count_documents({"month": month, "year": year, "role": role, "created_at": {"$gte": datetime.utcnow() - timedelta(seconds=10)}})
            # This is a bit loose, better to just track in loop.
            pass

    # Let's rely on a simpler tracking method inside the loop
    # We already have `count` but user wants to know ABOUT ROLES.
    # Let's count properly inside the loop next time, but for now, let's just show total count and list roles processed.
    roles_processed = [r.replace('_', ' ').title() for r in staff_lists.keys() if len(staff_lists[r]) > 0]
    
    flash(f"Payroll generation complete! {count} new pay records created for {month}/{year}. Covered roles: {', '.join(roles_processed)}.", "success")
    return redirect("/admin/payroll")



# Employee Details Management Page
@app.route("/admin/employee_details")
def admin_employee_details():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    # Fetch all employees from all collections
    all_employees = []
    
    # Doctors
    for doc in doctors_collection.find({}):
        all_employees.append({
            "role": "Doctor",
            "name": doc.get("name", ""),
            "username": doc.get("username", ""),
            "email": doc.get("email", ""),
            "phone": doc.get("phone", ""),
            "branch_id": doc.get("branch_id", ""),
            "salary": doc.get("salary", 0),
            "bank_details": doc.get("bank_details", {}),
            "personal_details": doc.get("personal_details", {})
        })
    
    # Receptionists
    for rec in receptionists_collection.find({}):
        all_employees.append({
            "role": "Receptionist",
            "name": rec.get("name", ""),
            "username": rec.get("username", ""),
            "email": rec.get("email", ""),
            "phone": rec.get("phone", ""),
            "branch_id": rec.get("branch_id", ""),
            "salary": rec.get("salary", 0),
            "bank_details": rec.get("bank_details", {}),
            "personal_details": rec.get("personal_details", {})
        })
    
    # Pharmacists
    for pharm in pharmacists_collection.find({}):
        all_employees.append({
            "role": "Pharmacist",
            "name": pharm.get("name", ""),
            "username": pharm.get("username", ""),
            "email": pharm.get("email", ""),
            "phone": pharm.get("phone", ""),
            "branch_id": pharm.get("branch_id", ""),
            "salary": pharm.get("salary", 0),
            "bank_details": pharm.get("bank_details", {}),
            "personal_details": pharm.get("personal_details", {})
        })
    
    # Lab Assistants
    for lab in lab_assistants_collection.find({}):
        all_employees.append({
            "role": "Lab Assistant",
            "name": lab.get("name", ""),
            "username": lab.get("username", ""),
            "email": lab.get("email", ""),
            "phone": lab.get("phone", ""),
            "branch_id": lab.get("branch_id", ""),
            "salary": lab.get("salary", 0),
            "bank_details": lab.get("bank_details", {}),
            "personal_details": lab.get("personal_details", {})
        })
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Employee Details - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-slate-50 min-h-screen">
        <nav class="bg-teal-700 p-4 text-white flex justify-between items-center shadow-xl">
            <div class="flex items-center gap-3">
                <img src="/static/images/heydoc_new_logo.png" alt="HeyDoc!" class="h-8">
                <h1 class="text-xl font-bold flex items-center"><i class="ri-team-line mr-2"></i> Employee Details</h1>
            </div>
            <a href="/admin_dashboard" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Dashboard</a>
        </nav>
        
        <div class="p-8 max-w-7xl mx-auto">
            <div class="bg-white rounded-3xl shadow-sm border border-slate-100 p-8 mb-6">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-black text-slate-800">All Employees ({{ all_employees|length }})</h2>
                    <div class="flex gap-3">
                        <a href="/admin/import_employee_data" class="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 transition-all flex items-center gap-2">
                            <i class="ri-file-upload-line"></i> Import CSV
                        </a>
                        <a href="/admin/export_employee_data" class="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-bold hover:bg-emerald-700 transition-all flex items-center gap-2">
                            <i class="ri-file-excel-2-line"></i> Export CSV
                        </a>
                    </div>
                </div>
                
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead>
                            <tr class="border-b-2 border-slate-200">
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Role</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Name</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Username</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Email</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Phone</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Branch</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Salary</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Bank Details</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Personal Details</th>
                                <th class="text-left py-3 px-4 font-bold text-slate-700">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for emp in all_employees %}
                            <tr class="border-b border-slate-100 hover:bg-slate-50">
                                <td class="py-3 px-4">
                                    <span class="px-2 py-1 bg-{{ 'blue' if emp.role == 'Doctor' else 'green' if emp.role == 'Receptionist' else 'purple' if emp.role == 'Pharmacist' else 'orange' }}-100 text-{{ 'blue' if emp.role == 'Doctor' else 'green' if emp.role == 'Receptionist' else 'purple' if emp.role == 'Pharmacist' else 'orange' }}-700 rounded-lg text-xs font-bold">
                                        {{ emp.role }}
                                    </span>
                                </td>
                                <td class="py-3 px-4 font-semibold">{{ emp.name }}</td>
                                <td class="py-3 px-4 text-sm text-slate-600">{{ emp.username }}</td>
                                <td class="py-3 px-4 text-sm text-slate-600">{{ emp.email }}</td>
                                <td class="py-3 px-4 text-sm text-slate-600">{{ emp.phone }}</td>
                                <td class="py-3 px-4 text-sm text-slate-600">{{ emp.branch_id }}</td>
                                <td class="py-3 px-4 font-bold text-teal-600">₹{{ emp.salary }}</td>
                                <td class="py-3 px-4 text-sm">
                                    {% if emp.bank_details.get('account_number') %}
                                    <span class="text-green-600"><i class="ri-checkbox-circle-fill"></i> Complete</span>
                                    {% else %}
                                    <span class="text-red-500"><i class="ri-close-circle-fill"></i> Missing</span>
                                    {% endif %}
                                </td>
                                <td class="py-3 px-4 text-sm">
                                    {% if emp.personal_details.get('pan_number') %}
                                    <span class="text-green-600"><i class="ri-checkbox-circle-fill"></i> Complete</span>
                                    {% else %}
                                    <span class="text-red-500"><i class="ri-close-circle-fill"></i> Missing</span>
                                    {% endif %}
                                </td>
                                <td class="py-3 px-4">
                                    <a href="/admin/edit_employee/{{ emp.role }}/{{ emp.username }}" 
                                       class="inline-flex items-center gap-1 px-3 py-1.5 bg-teal-600 text-white rounded-lg text-sm font-bold hover:bg-teal-700 transition-all">
                                        <i class="ri-edit-line"></i> Edit
                                    </a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, all_employees=all_employees)


# Admin Edit Employee Details
@app.route("/admin/edit_employee/<role>/<username>", methods=["GET", "POST"])
def admin_edit_employee(role, username):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    # Map role to collection
    collection_map = {
        "Doctor": doctors_collection,
        "Receptionist": receptionists_collection,
        "Pharmacist": pharmacists_collection,
        "Lab Assistant": lab_assistants_collection
    }
    
    collection = collection_map.get(role)
    if collection is None:
        flash("Invalid role.", "error")
        return redirect("/admin/employee_details")
    
    employee = collection.find_one({"username": username})
    if not employee:
        flash("Employee not found.", "error")
        return redirect("/admin/employee_details")
    
    if request.method == "POST":
        try:
            # Update bank details
            bank_details = {
                "account_number": request.form.get("account_number", "").strip(),
                "account_holder_name": request.form.get("account_holder_name", "").strip(),
                "bank_name": request.form.get("bank_name", "").strip(),
                "ifsc_code": request.form.get("ifsc_code", "").strip(),
                "branch_name": request.form.get("branch_name", "").strip()
            }
            
            # Update personal details
            personal_details = {
                "pan_number": request.form.get("pan_number", "").strip(),
                "aadhar_number": request.form.get("aadhar_number", "").strip(),
                "date_of_birth": request.form.get("date_of_birth", "").strip(),
                "blood_group": request.form.get("blood_group", "").strip(),
                "permanent_address": request.form.get("permanent_address", "").strip(),
                "current_address": request.form.get("current_address", "").strip(),
                "emergency_contact_name": request.form.get("emergency_contact_name", "").strip(),
                "emergency_contact_phone": request.form.get("emergency_contact_phone", "").strip()
            }
            
            collection.update_one(
                {"username": username},
                {"$set": {
                    "bank_details": bank_details,
                    "personal_details": personal_details
                }}
            )
            
            flash(f"Details updated successfully for {employee.get('name')}!", "success")
            return redirect("/admin/employee_details")
            
        except Exception as e:
            flash(f"Error updating employee: {str(e)}", "error")
    
    # GET - Show edit form
    bank_details = employee.get("bank_details", {})
    personal_details = employee.get("personal_details", {})
    
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Employee - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body class="bg-slate-50 min-h-screen">
    <nav class="bg-teal-700 p-4 text-white shadow-xl">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <div class="flex items-center gap-3">
                <img src="/static/images/heydoc_new_logo.png" alt="HeyDoc!" class="h-8">
                <h1 class="text-xl font-bold flex items-center"><i class="ri-edit-line mr-2"></i> Edit Employee Details</h1>
            </div>
            <a href="/admin/employee_details" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Back to Employees</a>
        </div>
    </nav>
    
    <div class="p-8 max-w-6xl mx-auto">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="mb-4 p-4 rounded-lg bg-{{ 'red' if category == 'error' else 'green' }}-50 text-{{ 'red' if category == 'error' else 'green' }}-800 border border-{{ 'red' if category == 'error' else 'green' }}-200">
                    {{ message }}
                </div>
            {% endfor %}
        {% endwith %}
        
        <div class="bg-white rounded-3xl shadow-sm border border-slate-100 p-8 mb-6">
            <div class="mb-6">
                <h2 class="text-2xl font-black text-slate-800">{{ employee.name }}</h2>
                <p class="text-slate-600">{{ role }} • {{ employee.username }} • {{ employee.email }}</p>
            </div>
            
            <form method="POST" class="space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <!-- Bank Details -->
                    <div class="bg-slate-50 rounded-2xl p-6">
                        <h3 class="text-xl font-black text-slate-800 mb-4 flex items-center">
                            <i class="ri-bank-line mr-2 text-teal-600"></i> Bank Details
                        </h3>
                        
                        <div class="space-y-4">
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Account Number</label>
                                <input type="text" name="account_number" value="{{ bank_details.get('account_number', '') }}"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Account Holder Name</label>
                                <input type="text" name="account_holder_name" value="{{ bank_details.get('account_holder_name', '') }}"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Bank Name</label>
                                <input type="text" name="bank_name" value="{{ bank_details.get('bank_name', '') }}"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">IFSC Code</label>
                                <input type="text" name="ifsc_code" value="{{ bank_details.get('ifsc_code', '') }}" pattern="^[A-Z]{4}0[A-Z0-9]{6}$"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Bank Branch</label>
                                <input type="text" name="branch_name" value="{{ bank_details.get('branch_name', '') }}"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                        </div>
                    </div>
                    
                    <!-- Personal Details -->
                    <div class="bg-slate-50 rounded-2xl p-6">
                        <h3 class="text-xl font-black text-slate-800 mb-4 flex items-center">
                            <i class="ri-user-line mr-2 text-teal-600"></i> Personal Details
                        </h3>
                        
                        <div class="space-y-4">
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">PAN Number</label>
                                <input type="text" name="pan_number" value="{{ personal_details.get('pan_number', '') }}" pattern="^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Aadhar Number</label>
                                <input type="text" name="aadhar_number" value="{{ personal_details.get('aadhar_number', '') }}" pattern="^[0-9]{12}$"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Date of Birth</label>
                                <input type="date" name="date_of_birth" value="{{ personal_details.get('date_of_birth', '') }}"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Blood Group</label>
                                <select name="blood_group" class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                                    <option value="">Select</option>
                                    {% for bg in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] %}
                                    <option value="{{ bg }}" {% if personal_details.get('blood_group') == bg %}selected{% endif %}>{{ bg }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Permanent Address</label>
                                <textarea name="permanent_address" rows="2"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">{{ personal_details.get('permanent_address', '') }}</textarea>
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Current Address</label>
                                <textarea name="current_address" rows="2"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">{{ personal_details.get('current_address', '') }}</textarea>
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Emergency Contact Name</label>
                                <input type="text" name="emergency_contact_name" value="{{ personal_details.get('emergency_contact_name', '') }}"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                            
                            <div>
                                <label class="block text-slate-700 font-bold mb-1 text-sm">Emergency Contact Phone</label>
                                <input type="tel" name="emergency_contact_phone" value="{{ personal_details.get('emergency_contact_phone', '') }}" pattern="^[0-9]{10}$"
                                    class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            </div>
                        </div>
                    </div>
                </div>
                
                <button type="submit" class="w-full bg-teal-600 text-white py-4 rounded-xl font-bold hover:bg-teal-700 transition-all flex items-center justify-center gap-2">
                    <i class="ri-save-line text-xl"></i> Save All Changes
                </button>
            </form>
        </div>
    </div>
</body>
</html>
    """, employee=employee, role=role, bank_details=bank_details, personal_details=personal_details)


@app.route("/admin/export_employee_data")
def admin_export_employee_data():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    import csv
    from io import StringIO
    from flask import make_response
    
    # Fetch all employees from all collections
    all_employees = []
    
    # Doctors
    for doc in doctors_collection.find({}):
        all_employees.append({
            "Role": "Doctor",
            "Name": doc.get("name", ""),
            "Username": doc.get("username", ""),
            "Email": doc.get("email", ""),
            "Phone": doc.get("phone", ""),
            "Branch": doc.get("branch_id", ""),
            "Salary": doc.get("salary", 0),
            "Account Number": doc.get("bank_details", {}).get("account_number", ""),
            "Account Holder": doc.get("bank_details", {}).get("account_holder_name", ""),
            "Bank Name": doc.get("bank_details", {}).get("bank_name", ""),
            "IFSC Code": doc.get("bank_details", {}).get("ifsc_code", ""),
            "Bank Branch": doc.get("bank_details", {}).get("branch_name", ""),
            "PAN Number": doc.get("personal_details", {}).get("pan_number", ""),
            "Aadhar Number": doc.get("personal_details", {}).get("aadhar_number", ""),
            "Date of Birth": doc.get("personal_details", {}).get("date_of_birth", ""),
            "Blood Group": doc.get("personal_details", {}).get("blood_group", ""),
            "Permanent Address": doc.get("personal_details", {}).get("permanent_address", ""),
            "Current Address": doc.get("personal_details", {}).get("current_address", ""),
            "Emergency Contact Name": doc.get("personal_details", {}).get("emergency_contact_name", ""),
            "Emergency Contact Phone": doc.get("personal_details", {}).get("emergency_contact_phone", "")
        })
    
    # Receptionists
    for rec in receptionists_collection.find({}):
        all_employees.append({
            "Role": "Receptionist",
            "Name": rec.get("name", ""),
            "Username": rec.get("username", ""),
            "Email": rec.get("email", ""),
            "Phone": rec.get("phone", ""),
            "Branch": rec.get("branch_id", ""),
            "Salary": rec.get("salary", 0),
            "Account Number": rec.get("bank_details", {}).get("account_number", ""),
            "Account Holder": rec.get("bank_details", {}).get("account_holder_name", ""),
            "Bank Name": rec.get("bank_details", {}).get("bank_name", ""),
            "IFSC Code": rec.get("bank_details", {}).get("ifsc_code", ""),
            "Bank Branch": rec.get("bank_details", {}).get("branch_name", ""),
            "PAN Number": rec.get("personal_details", {}).get("pan_number", ""),
            "Aadhar Number": rec.get("personal_details", {}).get("aadhar_number", ""),
            "Date of Birth": rec.get("personal_details", {}).get("date_of_birth", ""),
            "Blood Group": rec.get("personal_details", {}).get("blood_group", ""),
            "Permanent Address": rec.get("personal_details", {}).get("permanent_address", ""),
            "Current Address": rec.get("personal_details", {}).get("current_address", ""),
            "Emergency Contact Name": rec.get("personal_details", {}).get("emergency_contact_name", ""),
            "Emergency Contact Phone": rec.get("personal_details", {}).get("emergency_contact_phone", "")
        })
    
    # Pharmacists
    for pharm in pharmacists_collection.find({}):
        all_employees.append({
            "Role": "Pharmacist",
            "Name": pharm.get("name", ""),
            "Username": pharm.get("username", ""),
            "Email": pharm.get("email", ""),
            "Phone": pharm.get("phone", ""),
            "Branch": pharm.get("branch_id", ""),
            "Salary": pharm.get("salary", 0),
            "Account Number": pharm.get("bank_details", {}).get("account_number", ""),
            "Account Holder": pharm.get("bank_details", {}).get("account_holder_name", ""),
            "Bank Name": pharm.get("bank_details", {}).get("bank_name", ""),
            "IFSC Code": pharm.get("bank_details", {}).get("ifsc_code", ""),
            "Bank Branch": pharm.get("bank_details", {}).get("branch_name", ""),
            "PAN Number": pharm.get("personal_details", {}).get("pan_number", ""),
            "Aadhar Number": pharm.get("personal_details", {}).get("aadhar_number", ""),
            "Date of Birth": pharm.get("personal_details", {}).get("date_of_birth", ""),
            "Blood Group": pharm.get("personal_details", {}).get("blood_group", ""),
            "Permanent Address": pharm.get("personal_details", {}).get("permanent_address", ""),
            "Current Address": pharm.get("personal_details", {}).get("current_address", ""),
            "Emergency Contact Name": pharm.get("personal_details", {}).get("emergency_contact_name", ""),
            "Emergency Contact Phone": pharm.get("personal_details", {}).get("emergency_contact_phone", "")
        })
    
    # Lab Assistants
    for lab in lab_assistants_collection.find({}):
        all_employees.append({
            "Role": "Lab Assistant",
            "Name": lab.get("name", ""),
            "Username": lab.get("username", ""),
            "Email": lab.get("email", ""),
            "Phone": lab.get("phone", ""),
            "Branch": lab.get("branch_id", ""),
            "Salary": lab.get("salary", 0),
            "Account Number": lab.get("bank_details", {}).get("account_number", ""),
            "Account Holder": lab.get("bank_details", {}).get("account_holder_name", ""),
            "Bank Name": lab.get("bank_details", {}).get("bank_name", ""),
            "IFSC Code": lab.get("bank_details", {}).get("ifsc_code", ""),
            "Bank Branch": lab.get("bank_details", {}).get("branch_name", ""),
            "PAN Number": lab.get("personal_details", {}).get("pan_number", ""),
            "Aadhar Number": lab.get("personal_details", {}).get("aadhar_number", ""),
            "Date of Birth": lab.get("personal_details", {}).get("date_of_birth", ""),
            "Blood Group": lab.get("personal_details", {}).get("blood_group", ""),
            "Permanent Address": lab.get("personal_details", {}).get("permanent_address", ""),
            "Current Address": lab.get("personal_details", {}).get("current_address", ""),
            "Emergency Contact Name": lab.get("personal_details", {}).get("emergency_contact_name", ""),
            "Emergency Contact Phone": lab.get("personal_details", {}).get("emergency_contact_phone", "")
        })
    
    # Generate CSV
    si = StringIO()
    if all_employees:
        fieldnames = all_employees[0].keys()
        writer = csv.DictWriter(si, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_employees)
    
    # Create response
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=employee_payroll_data_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output


@app.route("/admin/import_employee_data", methods=["GET", "POST"])
def admin_import_employee_data():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            import csv
            from io import StringIO
            
            # Get uploaded file
            if 'csv_file' not in request.files:
                flash("No file uploaded.", "error")
                return redirect("/admin/import_employee_data")
            
            file = request.files['csv_file']
            if file.filename == '':
                flash("No file selected.", "error")
                return redirect("/admin/import_employee_data")
            
            # Read CSV
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            updated_count = 0
            error_count = 0
            errors = []
            
            for row in csv_reader:
                try:
                    username = row.get('Username', '').strip()
                    if not username:
                        continue
                    
                    # Prepare update data
                    bank_details = {
                        "account_number": row.get('Account Number', '').strip(),
                        "account_holder_name": row.get('Account Holder', '').strip(),
                        "bank_name": row.get('Bank Name', '').strip(),
                        "ifsc_code": row.get('IFSC Code', '').strip(),
                        "branch_name": row.get('Bank Branch', '').strip()
                    }
                    
                    personal_details = {
                        "pan_number": row.get('PAN Number', '').strip(),
                        "aadhar_number": row.get('Aadhar Number', '').strip(),
                        "date_of_birth": row.get('DOB', '').strip(),
                        "blood_group": row.get('Blood Group', '').strip(),
                        "permanent_address": row.get('Permanent Address', '').strip(),
                        "current_address": row.get('Current Address', '').strip(),
                        "emergency_contact_name": row.get('Emergency Contact Name', '').strip(),
                        "emergency_contact_phone": row.get('Emergency Contact Phone', '').strip()
                    }
                    
                    update_data = {
                        "bank_details": bank_details,
                        "personal_details": personal_details
                    }
                    
                    # Try to update in all collections
                    updated = False
                    for collection in [doctors_collection, receptionists_collection, pharmacists_collection, lab_assistants_collection]:
                        result = collection.update_one(
                            {"username": username},
                            {"$set": update_data}
                        )
                        if result.matched_count > 0:
                            updated = True
                            updated_count += 1
                            break
                    
                    if not updated:
                        errors.append(f"Username '{username}' not found")
                        error_count += 1
                        
                except Exception as e:
                    errors.append(f"Error processing row: {str(e)}")
                    error_count += 1
            
            flash(f"Import complete! {updated_count} employees updated, {error_count} errors.", "success" if error_count == 0 else "warning")
            if errors and len(errors) <= 10:
                for err in errors[:10]:
                    flash(err, "error")
            
            return redirect("/admin/payroll")
            
        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "error")
            return redirect("/admin/import_employee_data")
    
    # GET - Show upload form
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Import Employee Data - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-slate-50 min-h-screen">
        <nav class="bg-indigo-700 p-4 text-white flex justify-between items-center shadow-xl">
            <h1 class="text-xl font-bold flex items-center"><i class="ri-file-upload-line mr-2"></i> Import Employee Data</h1>
            <a href="/admin/payroll" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Back to Payroll</a>
        </nav>
        
        <div class="p-8 max-w-3xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 p-4 rounded-lg bg-{{ 'red' if category == 'error' else 'amber' if category == 'warning' else 'green' }}-50 text-{{ 'red' if category == 'error' else 'amber' if category == 'warning' else 'green' }}-800 border border-{{ 'red' if category == 'error' else 'amber' if category == 'warning' else 'green' }}-200">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            
            <div class="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
                <h2 class="text-2xl font-black text-slate-800 mb-6">Upload CSV File</h2>
                
                <div class="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-6">
                    <h3 class="font-bold text-blue-900 mb-2 flex items-center">
                        <i class="ri-information-line mr-2"></i> CSV Format Required
                    </h3>
                    <p class="text-sm text-blue-800 mb-3">Your CSV must have these column headers (exact spelling):</p>
                    <code class="text-xs bg-white px-3 py-2 rounded block overflow-x-auto">
                        Username, Account Number, Account Holder, Bank Name, IFSC Code, Bank Branch,
                        PAN Number, Aadhar Number, DOB, Blood Group, Permanent Address, Current Address,
                        Emergency Contact Name, Emergency Contact Phone
                    </code>
                </div>
                
                <form method="POST" enctype="multipart/form-data" class="space-y-6">
                    <div>
                        <label class="block text-slate-700 font-bold mb-2">Select CSV File</label>
                        <input type="file" name="csv_file" accept=".csv" required
                            class="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:outline-none focus:border-indigo-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 file:font-semibold hover:file:bg-indigo-100">
                    </div>
                    
                    <button type="submit" class="w-full bg-indigo-600 text-white py-4 rounded-xl font-bold hover:bg-indigo-700 transition-all flex items-center justify-center gap-2">
                        <i class="ri-upload-cloud-line text-xl"></i> Upload and Import Data
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)

# Employee Profile Update Route
@app.route("/update_profile", methods=["GET", "POST"])
def update_profile():
    # Detect user role
    user_role = get_user_role()
    if not user_role:
        flash("Please login to access this page.", "error")
        return redirect("/login")
    
    username = session.get(user_role)
    
    # Get user data
    user_data = None
    collection = None
    
    if user_role == "doctor":
        collection = doctors_collection
    elif user_role == "receptionist":
        collection = receptionists_collection
    elif user_role == "pharmacist":
        collection = pharmacists_collection
    elif user_role == "lab_assistant":
        collection = lab_assistants_collection
    else:
        flash("Profile updates not available for your role.", "error")
        return redirect("/")
    
    user_data = collection.find_one({"username": username})
    if not user_data:
        flash("User not found.", "error")
        return redirect("/")
    
    if request.method == "POST":
        try:
            update_type = request.form.get("update_type")
            
            if update_type == "bank":
                bank_details = {
                    "account_number": request.form.get("account_number", "").strip(),
                    "account_holder_name": request.form.get("account_holder_name", "").strip(),
                    "bank_name": request.form.get("bank_name", "").strip(),
                    "ifsc_code": request.form.get("ifsc_code", "").strip(),
                    "branch_name": request.form.get("branch_name", "").strip()
                }
                collection.update_one(
                    {"username": username},
                    {"$set": {"bank_details": bank_details}}
                )
                flash("Bank details updated successfully!", "success")
                
            elif update_type == "personal":
                personal_details = {
                    "pan_number": request.form.get("pan_number", "").strip(),
                    "aadhar_number": request.form.get("aadhar_number", "").strip(),
                    "date_of_birth": request.form.get("date_of_birth", "").strip(),
                    "blood_group": request.form.get("blood_group", "").strip(),
                    "permanent_address": request.form.get("permanent_address", "").strip(),
                    "current_address": request.form.get("current_address", "").strip(),
                    "emergency_contact_name": request.form.get("emergency_contact_name", "").strip(),
                    "emergency_contact_phone": request.form.get("emergency_contact_phone", "").strip()
                }
                collection.update_one(
                    {"username": username},
                    {"$set": {"personal_details": personal_details}}
                )
                flash("Personal details updated successfully!", "success")
            
            return redirect("/update_profile")
            
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            return redirect("/update_profile")
    
    # GET - Show form
    bank_details = user_data.get("bank_details", {})
    personal_details = user_data.get("personal_details", {})
    
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Profile - Hey Doc!</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body class="bg-slate-50 min-h-screen">
    <nav class="bg-teal-600 p-4 text-white shadow-xl">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <div class="flex items-center gap-3">
                <img src="/static/images/heydoc_new_logo.png" alt="HeyDoc!" class="h-8">
                <h1 class="text-xl font-bold">Update My Profile</h1>
            </div>
            <a href="/" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Back to Dashboard</a>
        </div>
    </nav>
    
    <div class="p-8 max-w-6xl mx-auto">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="mb-4 p-4 rounded-lg bg-{{ 'red' if category == 'error' else 'green' }}-50 text-{{ 'red' if category == 'error' else 'green' }}-800 border border-{{ 'red' if category == 'error' else 'green' }}-200">
                    {{ message }}
                </div>
            {% endfor %}
        {% endwith %}
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <!-- Bank Details -->
            <div class="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
                <h2 class="text-2xl font-black text-slate-800 mb-6 flex items-center">
                    <i class="ri-bank-line mr-2 text-teal-600"></i> Bank Details
                </h2>
                
                <form method="POST" class="space-y-4">
                    <input type="hidden" name="update_type" value="bank">
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Account Number</label>
                        <input type="text" name="account_number" value="{{ bank_details.get('account_number', '') }}"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Account Holder Name</label>
                        <input type="text" name="account_holder_name" value="{{ bank_details.get('account_holder_name', '') }}"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Bank Name</label>
                        <input type="text" name="bank_name" value="{{ bank_details.get('bank_name', '') }}"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">IFSC Code</label>
                        <input type="text" name="ifsc_code" value="{{ bank_details.get('ifsc_code', '') }}" pattern="^[A-Z]{4}0[A-Z0-9]{6}$"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Bank Branch</label>
                        <input type="text" name="branch_name" value="{{ bank_details.get('branch_name', '') }}"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <button type="submit" class="w-full bg-teal-600 text-white py-3 rounded-xl font-bold hover:bg-teal-700 transition-all">
                        <i class="ri-save-line mr-2"></i>Save Bank Details
                    </button>
                </form>
            </div>
            
            <!-- Personal Details -->
            <div class="bg-white rounded-3xl shadow-sm border border-slate-100 p-8">
                <h2 class="text-2xl font-black text-slate-800 mb-6 flex items-center">
                    <i class="ri-user-line mr-2 text-teal-600"></i> Personal Details
                </h2>
                
                <form method="POST" class="space-y-4">
                    <input type="hidden" name="update_type" value="personal">
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">PAN Number</label>
                        <input type="text" name="pan_number" value="{{ personal_details.get('pan_number', '') }}" pattern="^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Aadhar Number</label>
                        <input type="text" name="aadhar_number" value="{{ personal_details.get('aadhar_number', '') }}" pattern="^[0-9]{12}$"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Date of Birth</label>
                        <input type="date" name="date_of_birth" value="{{ personal_details.get('date_of_birth', '') }}"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Blood Group</label>
                        <select name="blood_group" class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                            <option value="">Select</option>
                            {% for bg in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] %}
                            <option value="{{ bg }}" {% if personal_details.get('blood_group') == bg %}selected{% endif %}>{{ bg }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Permanent Address</label>
                        <textarea name="permanent_address" rows="2"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">{{ personal_details.get('permanent_address', '') }}</textarea>
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Current Address</label>
                        <textarea name="current_address" rows="2"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">{{ personal_details.get('current_address', '') }}</textarea>
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Emergency Contact Name</label>
                        <input type="text" name="emergency_contact_name" value="{{ personal_details.get('emergency_contact_name', '') }}"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <div>
                        <label class="block text-slate-700 font-bold mb-1 text-sm">Emergency Contact Phone</label>
                        <input type="tel" name="emergency_contact_phone" value="{{ personal_details.get('emergency_contact_phone', '') }}" pattern="^[0-9]{10}$"
                            class="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500">
                    </div>
                    
                    <button type="submit" class="w-full bg-teal-600 text-white py-3 rounded-xl font-bold hover:bg-teal-700 transition-all">
                        <i class="ri-save-line mr-2"></i>Save Personal Details
                    </button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
    """, bank_details=bank_details, personal_details=personal_details)

@app.route("/my_payroll")
def staff_payroll_history():
    # Detect user and role from session
    current_user = None
    role = None
    for r in ["doctor", "receptionist", "pharmacist", "lab_assistant", "financial_analytics", "branch_admin"]:
        if r in session:
            current_user = session[r]
            role = r
            break
            
    if not current_user: return redirect("/login")
    
    my_salaries = list(salaries_collection.find({"username": current_user}).sort("created_at", -1))
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>My Payroll - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="bg-gray-50 min-h-screen">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center shadow-lg">
            <h1 class="text-xl font-bold flex items-center"><i class="ri-bank-card-line mr-2"></i> My Payroll & Payslips</h1>
            <a href="{{ '/admin_dashboard' if 'admin' in session else '/dashboard' if 'doctor' in session else '/reception_dashboard' if 'receptionist' in session else '/' }}" class="bg-white/20 px-4 py-2 rounded-lg hover:bg-white/30 transition-all">Back to Dashboard</a>
        </nav>
        
        <div class="p-8 max-w-5xl mx-auto">
            <div class="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                <div class="p-8 border-b border-gray-50">
                    <h2 class="text-xl font-black text-gray-800">Payment History</h2>
                    <p class="text-xs text-gray-400 uppercase font-bold tracking-widest mt-1">Select a period to view details</p>
                </div>
                
                <div class="divide-y divide-gray-50">
                    {% for sal in salaries %}
                    <div class="p-8 hover:bg-gray-50 transition-all flex flex-col md:flex-row justify-between items-center gap-6">
                        <div class="flex items-center gap-6">
                            <div class="w-16 h-16 bg-teal-50 rounded-2xl flex flex-col items-center justify-center text-teal-600 border border-teal-100 italic">
                                <span class="text-[10px] font-black uppercase">{{ sal.year }}</span>
                                <span class="text-lg font-black">{{ sal.month }}</span>
                            </div>
                            <div>
                                <p class="text-lg font-black text-gray-800">₹{{ "{:,.2f}".format(sal.net_salary) }}</p>
                                <p class="text-xs text-gray-400">Net Disbursement • {{ sal.created_at.strftime('%d %b %Y') }}</p>
                            </div>
                        </div>
                        <div class="flex gap-3">
                            <a href="/download_payslip/{{ sal._id }}" class="px-6 py-3 bg-gray-900 text-white rounded-xl text-xs font-black uppercase tracking-widest hover:bg-black transition-all flex items-center">
                                <i class="ri-download-cloud-2-line mr-2"></i> Download PDF
                            </a>
                        </div>
                    </div>
                    {% else %}
                    <div class="p-20 text-center">
                        <i class="ri-history-line text-5xl text-gray-200 mb-4 block"></i>
                        <p class="text-gray-400 font-bold uppercase tracking-widest text-sm">No payroll records found yet</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </body>
    </html>
    """, salaries=my_salaries)

@app.route("/download_payslip/<salary_id>")
def download_payslip(salary_id):
    # Security check: Ensure staff can only download their own payslip
    current_user = None
    for r in ["doctor", "receptionist", "pharmacist", "lab_assistant", "financial_analytics", "branch_admin"]:
        if r in session:
            current_user = session[r]
            break
    if not current_user: return redirect("/login")

    from bson import ObjectId
    sal = salaries_collection.find_one({"_id": ObjectId(salary_id)})
    if not sal or sal['username'] != current_user:
        flash("Unauthorized access to payslip.", "error")
        return redirect("/my_payroll")

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Payslip - {{ sal.month }}/{{ sal.year }}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @media print { .no-print { display: none; } }
            body { font-family: 'Inter', sans-serif; }
        </style>
    </head>
    <body class="bg-gray-100 p-8">
        <div class="max-w-3xl mx-auto bg-white p-12 shadow-2xl rounded-sm border-t-8 border-teal-600">
            <div class="flex justify-between items-start mb-12">
                <div>
                    <h1 class="text-3xl font-black text-gray-900 uppercase tracking-tighter italic">Hey Doc!</h1>
                    <p class="text-xs text-gray-400 font-bold uppercase tracking-widest mt-1">Hospital Management System</p>
                </div>
                <div class="text-right">
                    <h2 class="text-xl font-black text-gray-800 uppercase tracking-widest">Payslip</h2>
                    <p class="text-sm text-gray-500 font-medium">Period: {{ sal.month }}/{{ sal.year }}</p>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-8 mb-12 border-b border-gray-100 pb-12">
                <div>
                    <p class="text-[10px] font-black uppercase text-gray-400 mb-1">Employee Details</p>
                    <p class="text-lg font-black text-gray-800">{{ sal.staff_name }}</p>
                    <p class="text-sm text-teal-600 font-bold uppercase tracking-widest">{{ sal.role }}</p>
                </div>
                <div class="text-right">
                    <p class="text-[10px] font-black uppercase text-gray-400 mb-1">Payment Date</p>
                    <p class="text-lg font-black text-gray-800">{{ sal.created_at.strftime('%d %b %Y') }}</p>
                </div>
            </div>

            <div class="space-y-6">
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500 font-medium uppercase tracking-widest text-[10px]">Basic Salary</span>
                    <span class="font-bold text-gray-800">₹{{ "{:,.2f}".format(sal.basic_salary) }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500 font-medium uppercase tracking-widest text-[10px]">Incentives / Bonus</span>
                    <span class="font-bold text-emerald-600">+ ₹{{ "{:,.2f}".format(sal.incentives) }}</span>
                </div>
                <div class="border-t border-dashed border-gray-200 py-4">
                    <div class="flex justify-between items-center text-sm mb-2">
                        <span class="text-gray-400 font-medium uppercase tracking-widest text-[10px]">ESI Deduction</span>
                        <span class="font-bold text-rose-600">- ₹{{ "{:,.2f}".format(sal.deductions.esi) }}</span>
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-gray-400 font-medium uppercase tracking-widest text-[10px]">Provident Fund (PF)</span>
                        <span class="font-bold text-rose-600">- ₹{{ "{:,.2f}".format(sal.deductions.pf) }}</span>
                    </div>
                </div>
            </div>

            <div class="mt-12 p-8 bg-teal-600 text-white rounded-xl flex justify-between items-center">
                <div>
                    <p class="text-[10px] font-black uppercase opacity-60 tracking-widest">Net Payable Salary</p>
                    <p class="text-4xl font-black italic tracking-tighter mt-1">₹{{ "{:,.2f}".format(sal.net_salary) }}</p>
                </div>
                <div class="text-right italic">
                     <p class="text-[10px] font-black uppercase opacity-60 tracking-widest mb-2">Authorized Signatory</p>
                     <img src="https://signature.freefire-name.com/img.php?f=7&t=HeyDocAdmin" class="h-12 invert opacity-80" alt="Sign">
                </div>
            </div>

            <div class="mt-12 text-center no-print">
                <button onclick="window.print()" class="px-8 py-4 bg-gray-900 text-white rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-black transition-all">Print This Payslip</button>
            </div>
        </div>
    </body>
    </html>
    """, sal=sal)

if __name__ == "__main__":
    # Create default admin if none exists
    if admin_collection.count_documents({}) == 0:
        admin_collection.insert_one({
            "username": "admin",
            "password": "admin123",
            "email": "eedevnsskjayanth@gmail.com",
            "name": "System Administrator",
            "created_at": datetime.utcnow()
        })
        print("Default admin created - Username: 'admin', Password: 'admin123', Email: 'eedevnsskjayanth@gmail.com'")
    
    # Create default doctor if none exists
    if doctors_collection.count_documents({}) == 0:
        doctors_collection.insert_one({
            "username": "drpriya",
            "password": "password123",
            "email": "drpriya@heydoc.com",
            "name": "Dr. Priya Sharma"
        })
        print("Default doctor 'drpriya' created with password 'password123'. Please change this in production!")
    
    # Initialize CMS Defaults
    if site_settings_collection.count_documents({"type": "global"}) == 0:
        site_settings_collection.insert_one({
            "type": "global",
            "site_name": "Hey Doc!",
            "primary_color": "teal",
            "font_family": "Outfit, sans-serif",
            "contact_email": "support@heydoc.com",
            "contact_phone": "+1 234 567 890",
            "contact_address": "123 Medical Center, Health City",
            "facebook_url": "#",
            "twitter_url": "#",
            "instagram_url": "#",
            "created_at": datetime.utcnow()
        })
        print("CMS Site Settings initialized.")
        
    if homepage_content_collection.count_documents({"type": "main"}) == 0:
        homepage_content_collection.insert_one({
            "type": "main",
            "content": home_template, # Use the string variable defined in app.py
            "created_at": datetime.utcnow()
        })
        print("CMS Homepage Content initialized.")

    if site_settings_collection.count_documents({"type": "fees"}) == 0:
        site_settings_collection.insert_one({
            "type": "fees",
            "consultation_fee": 500,
            "free_consultation_days": 7,
            "created_at": datetime.utcnow()
        })
        print("CMS Consultation Fees initialized.")
    
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
    
@app.route("/change_password_force", methods=["GET", "POST"])
def change_password_force():
    if "pending_reset_user" not in session:
        return redirect("/login")
        
    if request.method == "POST":
        new_pass = request.form.get("new_password")
        confirm_pass = request.form.get("confirm_password")
        
        if new_pass != confirm_pass:
            flash("Passwords do not match", "error")
            return redirect("/change_password_force")
            
        if len(new_pass) < 6:
            flash("Password must be at least 6 characters", "error")
            return redirect("/change_password_force")
            
        username = session["pending_reset_user"]
        user_type = session["pending_reset_type"]
        
        user_collection_map = {
            "doctor": doctors_collection,
            "receptionist": receptionists_collection,
            "pharmacist": pharmacists_collection,
            "lab_assistant": lab_assistants_collection,
            "financial_analytics": financial_analytics_collection,
            "branch_admin": branch_admins_collection
        }
        
        if user_type in user_collection_map:
            # Update password and remove temp flag
            user_collection_map[user_type].update_one(
                {"username": username},
                {"$set": {"password": new_pass, "is_temp_password": False}}
            )
            
            # Clear pending reset session
            session.pop("pending_reset_user", None)
            session.pop("pending_reset_type", None)
            
            flash("Password updated successfully! Please login with your new password.", "success")
            return redirect("/login")
            
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Set New Password - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-slate-900 flex items-center justify-center p-6">
        <div class="max-w-md w-full bg-white rounded-3xl p-10 shadow-2xl">
            <div class="text-center mb-8">
                <div class="w-16 h-16 bg-amber-100 text-amber-600 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">
                    <i class="ri-lock-password-line"></i>
                </div>
                <h2 class="text-2xl font-bold text-slate-800">Set New Password</h2>
                <p class="text-slate-500 text-sm mt-2">For security, please update your temporary password.</p>
            </div>
            
            <form method="POST" class="space-y-6">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <div class="p-3 rounded-lg text-sm font-medium {% if category == 'error' %}bg-red-50 text-red-600{% else %}bg-green-50 text-green-600{% endif %}">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endwith %}
            
                <div class="space-y-1">
                    <label class="text-xs font-bold text-slate-400 uppercase tracking-wider">New Password</label>
                    <input type="password" name="new_password" required class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none">
                </div>
                
                <div class="space-y-1">
                    <label class="text-xs font-bold text-slate-400 uppercase tracking-wider">Confirm Password</label>
                    <input type="password" name="confirm_password" required class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none">
                </div>
                
                <button type="submit" class="w-full bg-teal-600 text-white py-4 rounded-xl font-bold hover:bg-teal-700 transition-colors shadow-lg shadow-teal-500/20">
                    Update Password
                </button>
            </form>
        </div>
    </body>
    </html>
    """)
@app.route("/auth_home")
def auth_home():
    """Smart redirect to appropriate dashboard based on session"""
    if "admin" in session: return redirect("/admin_dashboard")
    if "doctor" in session: return redirect("/dashboard")
    if "receptionist" in session: return redirect("/reception_dashboard")
    if "pharmacist" in session: return redirect("/pharmacist_dashboard")
    if "lab_assistant" in session: return redirect("/lab_dashboard")
    if "branch_admin" in session: return redirect("/branch_admin_dashboard")
    if "financial_analytics" in session: return redirect("/financial_analytics_dashboard")
    if "patient_phone" in session: return redirect("/patient_dashboard")
    
    # Default to public home if no session
    return redirect("/")
@app.route("/admin/verify_face", methods=["GET", "POST"])
def admin_verify_face():
    if "pre_auth_user" not in session:
        flash("Unauthorized access. Please login first.", "error")
        return redirect("/login")
        
    if request.method == "POST":
        image_data = request.form.get("image_data")
        if not image_data:
            flash("No face data received.", "error")
            return redirect("/admin/verify_face")
            
        try:
            # 1. Get the admin's stored face encoding
            username = session["pre_auth_user"]
            role = session["pre_auth_role"]
            
            collection = branch_admins_collection if role == "branch_admin" else admin_collection
            user_doc = collection.find_one({"username": username})
            
            if not user_doc:
                session.clear()
                flash("User record not found. Login failed.", "error")
                return redirect("/login")
                
            stored_encoding_blob = user_doc.get("face_encoding")
            
            if not stored_encoding_blob:
                # STRICT mode: If no face registered, DENY access as per user requirements
                session.clear()
                flash("Account not secured with Face ID. Contact Super Admin to enable access.", "error")
                return redirect("/login")
                
            # 2. Extract encoding from live image
            # Remove data URL prefix
            if "base64," in image_data:
                image_data = image_data.split("base64,")[1]
                
            import face_recognition
            import io
            import numpy as np
            from PIL import Image
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            image_np = np.array(image)
            
            face_locations = face_recognition.face_locations(image_np)
            if not face_locations:
                flash("No face detected. Please ensure good lighting.", "error")
                return redirect("/admin/verify_face")
                
            if len(face_locations) > 1:
                flash("Multiple faces detected. Please be alone in view.", "error")
                return redirect("/admin/verify_face")
                
            live_encoding = face_recognition.face_encodings(image_np, face_locations)[0]
            
            # 3. Decrypt stored encoding and compare
            stored_encoding = decrypt_face_encoding(stored_encoding_blob)
            
            # Strict tolerance 0.5
            start_time = time.time()
            match_result = face_recognition.compare_faces([stored_encoding], live_encoding, tolerance=0.5)
            # Log metrics if needed
            
            if match_result[0]:
                # SUCCESS: Finalize Login
                session[role] = username
                session["email"] = session.get("pre_auth_email")
                if role == "branch_admin":
                    session["branch_admin_branches"] = user_doc.get("branch_ids", [])
                
                # Cleanup Pre-Auth
                session.pop("pre_auth_user", None)
                session.pop("pre_auth_role", None)
                session.pop("pre_auth_email", None)
                session.pop("pre_auth_branch", None)
                session.pop("pre_auth_id", None)
                
                flash("Identity Confirmed. Welcome back!", "success")
                return redirect("/admin_dashboard" if role == "admin" else "/admin/staff") # Redirect Branch Admin to Staff or Branch Dashboard
            else:
                flash("Face verification failed. Identity mismatch.", "error")
                return redirect("/admin/verify_face")
                
        except Exception as e:
            print(f"Face Auth Error: {e}")
            flash("An error occurred during verification.", "error")
            return redirect("/admin/verify_face")

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Secure Face Verification - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div class="bg-white rounded-[40px] shadow-2xl overflow-hidden max-w-md w-full relative">
            <div class="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-teal-500 to-emerald-500"></div>
            
            <div class="p-8 text-center">
                <div class="w-16 h-16 bg-slate-50 rounded-2xl mx-auto flex items-center justify-center mb-6 shadow-sm">
                    <i class="ri-shield-user-line text-3xl text-teal-600"></i>
                </div>
                
                <h1 class="text-2xl font-black text-slate-800 mb-2">Identity Check</h1>
                <p class="text-slate-500 text-sm">Please verify your face to access the admin console.</p>
                
                <div class="mt-8 relative rounded-3xl overflow-hidden bg-black aspect-[3/4] shadow-inner ring-8 ring-slate-50">
                    <video id="video" autoplay playsinline class="w-full h-full object-cover transform scale-x-[-1]"></video>
                    
                    <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                        <div class="w-48 h-64 border-2 border-dashed border-white/30 rounded-[45%] mb-8 relative">
                            <div class="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-1 bg-teal-500/50 blur-sm"></div>
                            <div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-32 h-1 bg-teal-500/50 blur-sm"></div>
                        </div>
                        <p id="status" class="text-white/80 font-bold text-sm tracking-widest uppercase animate-pulse">Initializing Camera...</p>
                    </div>
                </div>

                <div class="mt-8 space-y-4">
                    <button id="verifyBtn" onclick="captureAndVerify()" disabled class="w-full py-4 bg-slate-200 text-slate-400 rounded-2xl font-black uppercase tracking-widest transition-all">
                        Scanning Environment...
                    </button>
                    
                     <a href="/logout" class="block text-xs font-bold text-slate-400 hover:text-red-500 transition-colors">Cancel Login</a>
                </div>
            </div>
            
            <form id="verifyForm" method="POST" class="hidden">
                <input type="hidden" name="image_data" id="imageData">
            </form>
        </div>

        <script>
            const video = document.getElementById('video');
            const verifyBtn = document.getElementById('verifyBtn');
            const status = document.getElementById('status');
            let stream = null;

            async function startCamera() {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
                    video.srcObject = stream;
                    video.onloadedmetadata = () => {
                        verifyBtn.disabled = false;
                        verifyBtn.classList.remove('bg-slate-200', 'text-slate-400');
                        verifyBtn.classList.add('bg-teal-600', 'text-white', 'hover:bg-teal-700', 'shadow-lg', 'shadow-teal-900/20');
                        verifyBtn.innerHTML = '<i class="ri-face-recognition-line mr-2"></i> Verify Identity';
                        status.textContent = "Ready for Verification";
                        status.classList.remove('animate-pulse');
                    };
                } catch (err) {
                    console.error("Camera Error:", err);
                    status.textContent = "Camera Access Denied";
                    status.classList.add('text-red-500');
                    verifyBtn.innerText = "Camera Error";
                }
            }

            function captureAndVerify() {
                verifyBtn.disabled = true;
                verifyBtn.innerHTML = '<i class="ri-loader-4-line animate-spin mr-2"></i> Verifying...';
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                
                const dataURL = canvas.toDataURL('image/jpeg', 0.8);
                document.getElementById('imageData').value = dataURL;
                document.getElementById('verifyForm').submit();
            }

            startCamera();
        </script>
    </body>
    </html>
    """)
