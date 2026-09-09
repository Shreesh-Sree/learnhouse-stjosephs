"""Setup Placement Cell Module, Custom DocTypes, and Seed Data in Frappe ERPNext."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_placement_cell():
    frappe.init(site="frontend", sites_path="sites")
    frappe.connect()
    print("Connected to Frappe database.")

    # 1. Module Def
    if not frappe.db.exists("Module Def", "Placement Cell"):
        mod = frappe.get_doc({
            "doctype": "Module Def",
            "module_name": "Placement Cell",
            "app_name": "erpnext",
            "custom": 1,
        })
        mod.insert(ignore_permissions=True)
        print("Created Module Def: Placement Cell")
    else:
        print("Module Def: Placement Cell already exists.")

    # Helper function to create Custom DocType safely
    def create_custom_doctype(doc_dict):
        name = doc_dict["name"]
        if frappe.db.exists("DocType", name):
            print(f"DocType {name} already exists.")
            return

        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": name,
            "module": "Placement Cell",
            "custom": 1,
            "autoname": doc_dict.get("autoname", "autoincrement"),
            "naming_rule": doc_dict.get("naming_rule", "Autoincrement"),
            "allow_import": 1,
            "is_submittable": 0,
            "quick_entry": 1,
            "track_changes": 1,
            "fields": doc_dict.get("fields", []),
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1,
                    "export": 1,
                    "import": 1,
                    "share": 1,
                },
                {
                    "role": "HR Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 0,
                    "export": 1,
                    "share": 1,
                },
                {
                    "role": "All",
                    "read": 1,
                    "write": 0,
                    "create": 0,
                    "delete": 0,
                }
            ],
        })
        doc.insert(ignore_permissions=True)
        print(f"Successfully created DocType: {name}")

    # 2. DocType: Placement Company
    create_custom_doctype({
        "name": "Placement Company",
        "autoname": "field:company_name",
        "naming_rule": "By fieldname",
        "fields": [
            {"fieldname": "company_name", "label": "Company Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1, "unique": 1},
            {"fieldname": "website", "label": "Website", "fieldtype": "Data"},
            {"fieldname": "tier", "label": "Tier", "fieldtype": "Select", "options": "Tier 1 (Super Dream > 10 LPA)\nTier 2 (Dream 5 - 10 LPA)\nTier 3 (Regular < 5 LPA)", "default": "Tier 2 (Dream 5 - 10 LPA)", "in_list_view": 1},
            {"fieldname": "col_break_1", "fieldtype": "Column Break"},
            {"fieldname": "hr_contact_name", "label": "HR Contact Name", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "hr_email", "label": "HR Email", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "hr_phone", "label": "HR Phone", "fieldtype": "Data"},
            {"fieldname": "sec_break_1", "fieldtype": "Section Break", "label": "Address & Overview"},
            {"fieldname": "address", "label": "Headquarters / Address", "fieldtype": "Small Text"},
        ]
    })

    # 3. DocType: Placement Student
    create_custom_doctype({
        "name": "Placement Student",
        "autoname": "field:register_number",
        "naming_rule": "By fieldname",
        "fields": [
            {"fieldname": "sec_academic", "fieldtype": "Section Break", "label": "Student Academic Info"},
            {"fieldname": "register_number", "label": "Register Number / USN", "fieldtype": "Data", "reqd": 1, "in_list_view": 1, "unique": 1},
            {"fieldname": "student_name", "label": "Full Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
            {"fieldname": "department", "label": "Department", "fieldtype": "Select", "options": "CSE\nIT\nAIDS\nAIML\nECE\nEEE\nMECH\nCIVIL\nBIOTECH", "reqd": 1, "in_list_view": 1, "in_filter": 1},
            {"fieldname": "col_acad", "fieldtype": "Column Break"},
            {"fieldname": "degree", "label": "Degree", "fieldtype": "Select", "options": "B.E.\nB.Tech\nM.E.\nM.Tech\nMBA\nMCA", "default": "B.E.", "in_filter": 1},
            {"fieldname": "batch", "label": "Batch (Graduation Year)", "fieldtype": "Select", "options": "2021-2025\n2022-2026\n2023-2027\n2024-2028", "default": "2022-2026", "in_filter": 1},
            {"fieldname": "college_email", "label": "College Email", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
            {"fieldname": "mobile_no", "label": "Mobile Number", "fieldtype": "Data"},

            {"fieldname": "sec_eligibility", "fieldtype": "Section Break", "label": "Academic Performance & Eligibility"},
            {"fieldname": "cgpa", "label": "Current CGPA", "fieldtype": "Float", "precision": "2", "reqd": 1, "in_list_view": 1},
            {"fieldname": "active_arrears", "label": "Active Standing Arrears", "fieldtype": "Int", "default": "0", "in_list_view": 1, "in_filter": 1},
            {"fieldname": "history_of_arrears", "label": "History of Arrears", "fieldtype": "Int", "default": "0"},
            {"fieldname": "col_marks", "fieldtype": "Column Break"},
            {"fieldname": "tenth_percentage", "label": "10th Percentage", "fieldtype": "Percent"},
            {"fieldname": "twelfth_percentage", "label": "12th / Diploma Percentage", "fieldtype": "Percent"},
            {"fieldname": "placement_status", "label": "Placement Status", "fieldtype": "Select", "options": "Eligible\nPlaced - Regular\nPlaced - Dream\nPlaced - Super Dream\nHigher Studies\nOpted Out", "default": "Eligible", "in_list_view": 1, "in_filter": 1},

            {"fieldname": "sec_lms", "fieldtype": "Section Break", "label": "LMS Training & Resume"},
            {"fieldname": "resume_url", "label": "Resume File", "fieldtype": "Attach"},
            {"fieldname": "training_completed", "label": "LMS Training Verified", "fieldtype": "Check", "default": "0"},
            {"fieldname": "col_lms", "fieldtype": "Column Break"},
            {"fieldname": "lms_user_id", "label": "LearnHouse LMS User ID", "fieldtype": "Data"},
            {"fieldname": "lms_completed_courses", "label": "Completed LMS Courses", "fieldtype": "Small Text"},
        ]
    })

    # 4. DocType: Placement Drive
    create_custom_doctype({
        "name": "Placement Drive",
        "autoname": "format:DRIVE-{company}-{YYYY}-{MM}-###",
        "naming_rule": "Expression",
        "fields": [
            {"fieldname": "sec_drive", "fieldtype": "Section Break", "label": "Drive Information"},
            {"fieldname": "drive_title", "label": "Drive Title", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
            {"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Placement Company", "reqd": 1, "in_list_view": 1, "in_filter": 1},
            {"fieldname": "job_role", "label": "Job Role / Title", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
            {"fieldname": "job_location", "label": "Job Location", "fieldtype": "Data", "default": "Chennai"},
            {"fieldname": "col_drive", "fieldtype": "Column Break"},
            {"fieldname": "ctc_lpa", "label": "Package (CTC in LPA)", "fieldtype": "Float", "precision": "2", "reqd": 1, "in_list_view": 1},
            {"fieldname": "drive_date", "label": "Drive Date", "fieldtype": "Date", "reqd": 1, "in_list_view": 1, "in_filter": 1},
            {"fieldname": "drive_status", "label": "Drive Status", "fieldtype": "Select", "options": "Announced\nRegistration Open\nIn-Progress\nCompleted\nCancelled", "default": "Announced", "in_list_view": 1, "in_filter": 1},

            {"fieldname": "sec_criteria", "fieldtype": "Section Break", "label": "Eligibility Criteria"},
            {"fieldname": "min_cgpa", "label": "Minimum CGPA Cutoff", "fieldtype": "Float", "default": "7.0", "precision": "2"},
            {"fieldname": "max_active_arrears", "label": "Max Allowed Active Arrears", "fieldtype": "Int", "default": "0"},
            {"fieldname": "col_crit", "fieldtype": "Column Break"},
            {"fieldname": "allowed_departments", "label": "Allowed Departments", "fieldtype": "Small Text", "default": "CSE, IT, AIDS, AIML, ECE, EEE"},
            {"fieldname": "selection_process", "label": "Selection Process / Rounds", "fieldtype": "Text", "default": "Round 1: Online Aptitude (LMS)\nRound 2: Technical Coding\nRound 3: HR Interview"},
        ]
    })

    # 5. DocType: Placement Application
    create_custom_doctype({
        "name": "Placement Application",
        "autoname": "format:APP-{student}-{placement_drive}-###",
        "naming_rule": "Expression",
        "fields": [
            {"fieldname": "sec_app", "fieldtype": "Section Break", "label": "Application Details"},
            {"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "Placement Student", "reqd": 1, "in_list_view": 1, "in_filter": 1},
            {"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "fetch_from": "student.student_name", "in_list_view": 1},
            {"fieldname": "col_app", "fieldtype": "Column Break"},
            {"fieldname": "placement_drive", "label": "Placement Drive", "fieldtype": "Link", "options": "Placement Drive", "reqd": 1, "in_list_view": 1, "in_filter": 1},
            {"fieldname": "company_name", "label": "Company", "fieldtype": "Data", "fetch_from": "placement_drive.company", "in_list_view": 1},

            {"fieldname": "sec_status", "fieldtype": "Section Break", "label": "Interview Stages & Outcome"},
            {"fieldname": "current_round", "label": "Current Round", "fieldtype": "Select", "options": "Registered\nRound 1: Online Aptitude / LMS Test\nRound 2: Technical Coding\nRound 3: Group Discussion\nRound 4: Technical Interview\nRound 5: HR Interview", "default": "Registered", "in_list_view": 1, "in_filter": 1},
            {"fieldname": "status", "label": "Application Status", "fieldtype": "Select", "options": "Applied\nShortlisted\nRejected\nOffered\nOffer Accepted\nOffer Declined", "default": "Applied", "in_list_view": 1, "in_filter": 1},
            {"fieldname": "col_status", "fieldtype": "Column Break"},
            {"fieldname": "offered_ctc_lpa", "label": "Offered CTC (LPA)", "fieldtype": "Float", "precision": "2"},
            {"fieldname": "offer_letter", "label": "Offer Letter Document", "fieldtype": "Attach"},
            {"fieldname": "remarks", "label": "Interview Feedback / Remarks", "fieldtype": "Small Text"},
        ]
    })

    frappe.db.commit()
    print("All DocTypes committed to database.")

    # 6. Insert Seed Data
    # Companies
    companies_data = [
        {"company_name": "Zoho Corporation", "tier": "Tier 2 (Dream 5 - 10 LPA)", "website": "https://zoho.com", "hr_contact_name": "Priya Raman", "hr_email": "campus@zohocorp.com"},
        {"company_name": "Amazon India", "tier": "Tier 1 (Super Dream > 10 LPA)", "website": "https://amazon.jobs", "hr_contact_name": "Karan Malhotra", "hr_email": "university-india@amazon.com"},
        {"company_name": "Cognizant", "tier": "Tier 3 (Regular < 5 LPA)", "website": "https://cognizant.com", "hr_contact_name": "Sneha Nair", "hr_email": "campus-recruitment@cognizant.com"},
    ]
    for comp in companies_data:
        if not frappe.db.exists("Placement Company", comp["company_name"]):
            frappe.get_doc({"doctype": "Placement Company", **comp}).insert(ignore_permissions=True)
            print(f"Inserted Company: {comp['company_name']}")

    # Students
    students_data = [
        {
            "register_number": "312421104001",
            "student_name": "Arun Kumar M",
            "department": "CSE",
            "batch": "2022-2026",
            "college_email": "arunkumar.cse26@stjosephs.ac.in",
            "cgpa": 8.75,
            "active_arrears": 0,
            "tenth_percentage": 92.5,
            "twelfth_percentage": 94.0,
            "placement_status": "Eligible",
            "training_completed": 1,
            "lms_completed_courses": "Data Structures & Algorithms, Python Masterclass",
        },
        {
            "register_number": "312421104002",
            "student_name": "Divya Bharathi S",
            "department": "IT",
            "batch": "2022-2026",
            "college_email": "divyabharathi.it26@stjosephs.ac.in",
            "cgpa": 9.20,
            "active_arrears": 0,
            "tenth_percentage": 96.0,
            "twelfth_percentage": 95.5,
            "placement_status": "Eligible",
            "training_completed": 1,
            "lms_completed_courses": "Full Stack Web Development, Advanced Aptitude",
        },
        {
            "register_number": "312421104003",
            "student_name": "Karthik Raja V",
            "department": "ECE",
            "batch": "2022-2026",
            "college_email": "karthikraja.ece26@stjosephs.ac.in",
            "cgpa": 7.80,
            "active_arrears": 0,
            "tenth_percentage": 88.0,
            "twelfth_percentage": 86.5,
            "placement_status": "Eligible",
            "training_completed": 1,
            "lms_completed_courses": "Embedded Systems & C, Placement Aptitude",
        },
    ]
    for stu in students_data:
        if not frappe.db.exists("Placement Student", stu["register_number"]):
            frappe.get_doc({"doctype": "Placement Student", **stu}).insert(ignore_permissions=True)
            print(f"Inserted Student: {stu['register_number']} - {stu['student_name']}")

    # Drives
    drives_data = [
        {
            "drive_title": "Zoho SDE Campus Recruitment 2026",
            "company": "Zoho Corporation",
            "job_role": "Software Development Engineer",
            "job_location": "Chennai",
            "ctc_lpa": 8.4,
            "drive_date": "2026-09-25",
            "drive_status": "Registration Open",
            "min_cgpa": 7.0,
            "max_active_arrears": 0,
            "allowed_departments": "CSE, IT, AIDS, AIML, ECE",
        },
        {
            "drive_title": "Amazon Graduate SDE Drive 2026",
            "company": "Amazon India",
            "job_role": "SDE-1",
            "job_location": "Hyderabad / Bangalore",
            "ctc_lpa": 16.5,
            "drive_date": "2026-10-10",
            "drive_status": "Announced",
            "min_cgpa": 8.0,
            "max_active_arrears": 0,
            "allowed_departments": "CSE, IT, AIDS",
        },
    ]
    for drv in drives_data:
        existing = frappe.db.get_value("Placement Drive", {"drive_title": drv["drive_title"]}, "name")
        if not existing:
            doc = frappe.get_doc({"doctype": "Placement Drive", **drv}).insert(ignore_permissions=True)
            print(f"Inserted Drive: {drv['drive_title']} ({doc.name})")

    # Applications
    zoho_drive = frappe.db.get_value("Placement Drive", {"drive_title": "Zoho SDE Campus Recruitment 2026"}, "name")
    if zoho_drive:
        for stu_id in ["312421104001", "312421104002"]:
            app_exists = frappe.db.get_value("Placement Application", {"student": stu_id, "placement_drive": zoho_drive}, "name")
            if not app_exists:
                app_doc = frappe.get_doc({
                    "doctype": "Placement Application",
                    "student": stu_id,
                    "placement_drive": zoho_drive,
                    "current_round": "Round 1: Online Aptitude / LMS Test",
                    "status": "Applied",
                }).insert(ignore_permissions=True)
                print(f"Created Application for {stu_id} in Zoho Drive: {app_doc.name}")

    # 7. Create Workspace
    if not frappe.db.exists("Workspace", "Placement Cell"):
        workspace = frappe.get_doc({
            "doctype": "Workspace",
            "label": "Placement Cell",
            "name": "Placement Cell",
            "title": "Placement Cell",
            "category": "Modules",
            "icon": "award",
            "is_standard": 0,
            "public": 1,
            "module": "Placement Cell",
            "roles": [{"role": "System Manager"}, {"role": "HR Manager"}],
            "shortcuts": [
                {"type": "DocType", "link_to": "Placement Student", "label": "Students Dossier"},
                {"type": "DocType", "link_to": "Placement Drive", "label": "Campus Drives"},
                {"type": "DocType", "link_to": "Placement Application", "label": "Drive Applications"},
                {"type": "DocType", "link_to": "Placement Company", "label": "Companies Master"},
            ],
            "links": [
                {
                    "label": "Placement Operations",
                    "type": "Card Break",
                    "link_type": "DocType",
                    "link_to": "Placement Student",
                },
                {"label": "Placement Students", "type": "Link", "link_type": "DocType", "link_to": "Placement Student"},
                {"label": "Placement Drives", "type": "Link", "link_type": "DocType", "link_to": "Placement Drive"},
                {"label": "Placement Applications", "type": "Link", "link_type": "DocType", "link_to": "Placement Application"},
                {"label": "Placement Companies", "type": "Link", "link_type": "DocType", "link_to": "Placement Company"},
            ],
        })
        workspace.insert(ignore_permissions=True)
        print("Created Workspace: Placement Cell")
    else:
        print("Workspace: Placement Cell already exists.")

    frappe.db.commit()
    frappe.destroy()
    print("=== PLACEMENT CELL SETUP COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    setup_placement_cell()
