@app.route("/admin/staff")
def admin_staff():
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    doctors = list(doctors_collection.find({}))
    receptionists = list(receptionists_collection.find({}))
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
                <a href="/admin_dashboard" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Dashboard</a>
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
                                    <div class="flex items-center space-x-2">
                                        <span class="font-bold text-teal-600">{{ doctor.get('leaves_remaining', 20) }}</span>
                                        <span class="text-gray-400">/</span>
                                        <span class="text-gray-500">{{ doctor.get('leave_quota', 20) }}</span>
                                    </div>
                                    <div class="text-xs text-gray-400 mt-0.5">
                                        Taken: {{ doctor.get('leaves_taken', 0) }} days
                                    </div>
                                </td>
                                <td class="p-3">
                                    <a href="/admin/manage_leave_quota/{{ doctor._id }}" class="text-teal-600 hover:text-teal-800 text-xs font-medium flex items-center">
                                        <i class="ri-settings-3-line mr-1"></i> Manage Quota
                                    </a>
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
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            {% for receptionist in receptionists %}
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 font-medium text-gray-800">{{ receptionist.get('name', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ receptionist.get('username', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ receptionist.get('email', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">{{ receptionist.get('phone', 'N/A') }}</td>
                                <td class="p-3 text-gray-600">
                                    {% set branch = branch_lookup.get(receptionist.get('branch_id')) %}
                                    {{ branch.get('name') if branch else 'N/A' }}
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
    """, doctors=doctors, receptionists=receptionists, branch_lookup=branch_lookup)

@app.route("/admin/manage_leave_quota/<doctor_id>", methods=["GET", "POST"])
def manage_leave_quota(doctor_id):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    doctor = doctors_collection.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect("/admin/staff")
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "reset":
            # Reset to full quota
            quota = doctor.get("leave_quota", 20)
            doctors_collection.update_one(
                {"_id": ObjectId(doctor_id)},
                {"$set": {
                    "leaves_remaining": quota,
                    "leaves_taken": 0
                }}
            )
            flash(f"Leave balance reset to {quota} days for {doctor.get('name')}!", "success")
        
        elif action == "adjust_quota":
            try:
                new_quota = int(request.form.get("new_quota", 20))
                if new_quota < 0:
                    flash("Quota cannot be negative.", "error")
                else:
                    current_taken = doctor.get("leaves_taken", 0)
                    new_remaining = new_quota - current_taken
                    
                    doctors_collection.update_one(
                        {"_id": ObjectId(doctor_id)},
                        {"$set": {
                            "leave_quota": new_quota,
                            "leaves_remaining": max(0, new_remaining)
                        }}
                    )
                    flash(f"Leave quota updated to {new_quota} days for {doctor.get('name')}!", "success")
            except ValueError:
                flash("Invalid quota value.", "error")
        
        elif action == "add_extra":
            try:
                extra_days = int(request.form.get("extra_days", 0))
                if extra_days > 0:
                    current_remaining = doctor.get("leaves_remaining", 20)
                    current_quota = doctor.get("leave_quota", 20)
                    
                    doctors_collection.update_one(
                        {"_id": ObjectId(doctor_id)},
                        {"$set": {
                            "leaves_remaining": current_remaining + extra_days,
                            "leave_quota": current_quota + extra_days
                        }}
                    )
                    flash(f"Added {extra_days} extra days to {doctor.get('name')}'s leave balance!", "success")
            except ValueError:
                flash("Invalid number of days.", "error")
        
        return redirect(f"/admin/manage_leave_quota/{doctor_id}")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Manage Leave Quota - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-gray-100">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center">
            <div class="flex items-center">
                <i class="ri-settings-3-line text-2xl mr-2"></i>
                <h1 class="text-xl font-bold">Manage Leave Quota</h1>
            </div>
            <div>
                <a href="/admin/staff" class="bg-white text-teal-700 px-3 py-1 rounded hover:bg-teal-100">Back to Staff</a>
            </div>
        </nav>
        
        <div class="p-6 max-w-4xl mx-auto">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="mb-4 p-3 rounded bg-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-100 text-{{ 'red' if category == 'error' else 'green' if category == 'success' else 'blue' }}-800">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            
            <!-- Doctor Info Card -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <h2 class="text-2xl font-bold text-gray-800 mb-4">{{ doctor.get('name') }}</h2>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-sm text-gray-500">Username</p>
                        <p class="font-medium">{{ doctor.get('username') }}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-500">Email</p>
                        <p class="font-medium">{{ doctor.get('email') }}</p>
                    </div>
                </div>
            </div>
            
            <!-- Current Leave Status -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center">
                    <i class="ri-calendar-check-line mr-2 text-teal-600"></i> Current Leave Status
                </h3>
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-teal-50 p-4 rounded-lg">
                        <p class="text-sm text-gray-600 mb-1">Annual Quota</p>
                        <p class="text-3xl font-bold text-teal-600">{{ doctor.get('leave_quota', 20) }}</p>
                        <p class="text-xs text-gray-500 mt-1">days per year</p>
                    </div>
                    <div class="bg-orange-50 p-4 rounded-lg">
                        <p class="text-sm text-gray-600 mb-1">Leaves Taken</p>
                        <p class="text-3xl font-bold text-orange-600">{{ doctor.get('leaves_taken', 0) }}</p>
                        <p class="text-xs text-gray-500 mt-1">days used</p>
                    </div>
                    <div class="bg-green-50 p-4 rounded-lg">
                        <p class="text-sm text-gray-600 mb-1">Remaining</p>
                        <p class="text-3xl font-bold text-green-600">{{ doctor.get('leaves_remaining', 20) }}</p>
                        <p class="text-xs text-gray-500 mt-1">days left</p>
                    </div>
                </div>
            </div>
            
            <!-- Management Actions -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Reset Balance -->
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h4 class="font-bold text-gray-800 mb-3 flex items-center">
                        <i class="ri-refresh-line mr-2 text-blue-600"></i> Reset Balance
                    </h4>
                    <p class="text-sm text-gray-600 mb-4">Reset taken leaves to 0 and restore full quota</p>
                    <form method="POST">
                        <input type="hidden" name="action" value="reset">
                        <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
                            Reset to Full Quota
                        </button>
                    </form>
                </div>
                
                <!-- Adjust Annual Quota -->
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h4 class="font-bold text-gray-800 mb-3 flex items-center">
                        <i class="ri-settings-4-line mr-2 text-purple-600"></i> Adjust Quota
                    </h4>
                    <p class="text-sm text-gray-600 mb-4">Change annual leave quota</p>
                    <form method="POST">
                        <input type="hidden" name="action" value="adjust_quota">
                        <input type="number" name="new_quota" value="{{ doctor.get('leave_quota', 20) }}" min="0" 
                               class="w-full px-3 py-2 border rounded mb-3 focus:outline-none focus:border-purple-500">
                        <button type="submit" class="w-full bg-purple-600 text-white py-2 rounded hover:bg-purple-700">
                            Update Quota
                        </button>
                    </form>
                </div>
                
                <!-- Add Extra Days -->
                <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h4 class="font-bold text-gray-800 mb-3 flex items-center">
                        <i class="ri-add-circle-line mr-2 text-green-600"></i> Add Extra Days
                    </h4>
                    <p class="text-sm text-gray-600 mb-4">Grant additional leave days</p>
                    <form method="POST">
                        <input type="hidden" name="action" value="add_extra">
                        <input type="number" name="extra_days" placeholder="Number of days" min="1" 
                               class="w-full px-3 py-2 border rounded mb-3 focus:outline-none focus:border-green-500">
                        <button type="submit" class="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700">
                            Add Extra Days
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, doctor=doctor)
