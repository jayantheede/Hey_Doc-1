# Staff Directory Route - Insert this before the process_leave route

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
                                <td class="p-3 text-gray-600">
                                    {% set branch = branch_lookup.get(receptionist.get('branch_id')) %}
                                    {{ branch.get('name') if branch else 'N/A' }}
                                </td>
                                <td class="p-3">
                                    <div class="flex items-center space-x-2">
                                        <span class="font-bold text-teal-600">{{ receptionist.leaves_remaining if receptionist.leaves_remaining is defined else receptionist.get('leaves_remaining', 22) }}</span>
                                        <span class="text-gray-400">/</span>
                                        <span class="text-gray-500">{{ receptionist.leave_quota if receptionist.leave_quota is defined else receptionist.get('leave_quota', 22) }}</span>
                                    </div>
                                    <div class="text-[10px] font-bold text-gray-400 uppercase tracking-tighter mt-0.5">
                                        Taken: {{ receptionist.leaves_taken if receptionist.leaves_taken is defined else receptionist.get('leaves_taken', 0) }}
                                    </div>
                                </td>
                                <td class="p-3">
                                    <div class="flex items-center space-x-2">
                                        <a href="/admin/manage_leave_quota/{{ receptionist._id }}?role=receptionist" class="w-8 h-8 bg-teal-50 text-teal-600 rounded-lg flex items-center justify-center hover:bg-teal-600 hover:text-white transition-all shadow-sm" title="Manage Quota">
                                            <i class="ri-settings-3-line"></i>
                                        </a>
                                        <button onclick="if(confirm('Delete {{ receptionist.name }}?')) window.location.href='/admin/delete_staff/receptionist/{{ receptionist._id }}'" class="w-8 h-8 bg-red-50 text-red-600 rounded-lg flex items-center justify-center hover:bg-red-600 hover:text-white transition-all shadow-sm" title="Delete">
                                            <i class="ri-delete-bin-line"></i>
                                        </button>
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
    """, doctors=doctors, receptionists=receptionists, branch_lookup=branch_lookup)

@app.route("/admin/manage_leave_quota/<user_id>", methods=["GET", "POST"])
def manage_leave_quota(user_id):
    if "admin" not in session:
        flash("Please log in as admin to access this page.", "error")
        return redirect("/login")
    
    role = request.args.get("role", "doctor")
    collection = doctors_collection if role == "doctor" else receptionists_collection
    
    user = collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash(f"{role.capitalize()} not found.", "error")
        return redirect("/admin/staff")
    
    if request.method == "POST":
        action = request.form.get("action")
        
        # Ensure leave_accounts exists
        if "leave_accounts" not in user:
            # Initialize if missing
            initial = {
                "casual": {"granted": user.get("leave_quota", 22), "consumed": user.get("leaves_taken", 0), "balance": user.get("leaves_remaining", 22)},
                "sick": {"granted": 5, "consumed": 0, "balance": 5},
                "lop": {"granted": 0, "consumed": 0, "balance": 0},
                "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
                "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
                "wfh": {"granted": 10, "consumed": 0, "balance": 10}
            }
            collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"leave_accounts": initial}})
            user = collection.find_one({"_id": ObjectId(user_id)})

        if action == "reset":
            accounts = user["leave_accounts"]
            for k in accounts:
                accounts[k]["balance"] = accounts[k]["granted"]
                accounts[k]["consumed"] = 0
            
            collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"leave_accounts": accounts, "leaves_remaining": accounts["casual"]["balance"], "leaves_taken": 0}})
            flash(f"All leave balances reset for {user.get('name')}!", "success")
        
        elif action == "adjust_quota":
            try:
                type_key = request.form.get("type_key", "casual")
                new_granted = int(request.form.get("new_granted", 0))
                
                accounts = user["leave_accounts"]
                if type_key in accounts:
                    old_granted = accounts[type_key]["granted"]
                    consumed = accounts[type_key]["consumed"]
                    
                    accounts[type_key]["granted"] = new_granted
                    accounts[type_key]["balance"] = new_granted - consumed
                    
                    update_doc = {"leave_accounts": accounts}
                    if type_key == "casual":
                        update_doc["leave_quota"] = new_granted
                        update_doc["leaves_remaining"] = accounts[type_key]["balance"]
                        
                    collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_doc})
                    flash(f"{type_key.replace('_', ' ').capitalize()} quota updated to {new_granted} days!", "success")
            except ValueError:
                flash("Invalid quota value.", "error")
        
        return redirect(f"/admin/manage_leave_quota/{user_id}?role={role}")
    
    # Ensure UI has accounts
    if "leave_accounts" not in user:
         user["leave_accounts"] = {
            "casual": {"granted": user.get("leave_quota", 22), "consumed": user.get("leaves_taken", 0), "balance": user.get("leaves_remaining", 22)},
            "sick": {"granted": 5, "consumed": 0, "balance": 5},
            "lop": {"granted": 0, "consumed": 0, "balance": 0},
            "comp_off": {"granted": 0, "consumed": 0, "balance": 0},
            "bereavement": {"granted": 3, "consumed": 0, "balance": 3},
            "wfh": {"granted": 10, "consumed": 0, "balance": 10}
        }

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Manage Leave Quota - Hey Doc!</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
    </head>
    <body class="min-h-screen bg-gray-100 pb-12">
        <nav class="bg-teal-600 p-4 text-white flex justify-between items-center shadow-lg sticky top-0 z-50">
            <div class="flex items-center">
                <i class="ri-settings-3-line text-2xl mr-2"></i>
                <h1 class="text-xl font-bold">Manage Leave Quota</h1>
            </div>
            <div>
                <a href="/admin/staff" class="bg-white text-teal-700 px-4 py-1.5 rounded-lg font-bold hover:bg-teal-50 transition-colors">Back to Staff</a>
            </div>
        </nav>
        
        <div class="p-6 max-w-5xl mx-auto space-y-6">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="p-4 rounded-xl {% if category == 'error' %}bg-red-100 text-red-700 border border-red-200{% else %}bg-green-100 text-green-700 border border-green-200{% endif %} font-medium shadow-sm">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endwith %}
            
            <div class="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 flex justify-between items-center">
                <div>
                    <h2 class="text-3xl font-black text-gray-900 mb-1">{{ user.get('name') }}</h2>
                    <p class="text-gray-500 flex items-center">
                        <span class="bg-teal-100 text-teal-700 px-2.5 py-0.5 rounded-full text-xs font-bold mr-3 uppercase">{{ role }}</span>
                        <i class="ri-mail-line mr-1 text-teal-600"></i> {{ user.get('email') }}
                    </p>
                </div>
                <form method="POST" onsubmit="return confirm('Reset all balances to default quotas?')">
                    <input type="hidden" name="action" value="reset">
                    <button type="submit" class="bg-red-50 text-red-600 px-6 py-2.5 rounded-xl font-bold hover:bg-red-100 transition-all border border-red-100 hover:shadow-md active:scale-95">
                        <i class="ri-restart-line mr-2"></i> Reset All Balances
                    </button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for key, account in user.leave_accounts.items() %}
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                    <div class="flex items-center justify-between mb-6">
                        <h3 class="text-sm font-black uppercase tracking-widest text-gray-400 font-clash">{{ key.replace('_', ' ') }}</h3>
                        <div class="w-8 h-8 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
                            <i class="ri-calendar-check-line"></i>
                        </div>
                    </div>
                    
                    <div class="flex items-end space-x-2 mb-6">
                        <span class="text-4xl font-black text-gray-900">{{ account.balance }}</span>
                        <span class="text-gray-400 font-bold mb-1">/ {{ account.granted }} Days</span>
                    </div>

                    <form method="POST" class="space-y-3 pt-4 border-t border-gray-50">
                        <input type="hidden" name="action" value="adjust_quota">
                        <input type="hidden" name="type_key" value="{{ key }}">
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-500">Update Granted Quota</label>
                        <div class="flex space-x-2">
                            <input type="number" name="new_granted" value="{{ account.granted }}" min="0" class="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm font-bold focus:ring-2 focus:ring-teal-500 outline-none">
                            <button type="submit" class="bg-teal-600 text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-teal-700 shadow-lg shadow-teal-100 transition-all active:scale-95">
                                Set
                            </button>
                        </div>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    """, user=user, role=role)
