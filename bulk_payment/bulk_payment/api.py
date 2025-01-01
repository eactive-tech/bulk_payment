import frappe, json
import os
import re

@frappe.whitelist()
def bulk_payment_outstanding():
    doc = json.loads(frappe.form_dict.get('doc'))
    name = doc.get('name')
    
    bp = frappe.get_doc("Bulk Payment Tool", name)

    filters = {}
    has_range1_filter = get_accounts_payable_filters("erpnext", "accounts_payable")

    if has_range1_filter:
        filters = {
            "company": doc.get('company'),
            "report_date": doc.get('as_on_date'),
            "ageing_based_on": "Due Date",
            "range1": "30",
            "range2": "60",
            "range3": "90",
            "range4": "120",
            "party_type": "Supplier",
        }
    else:
        {
            "company": doc.get('company'),
            "report_date": doc.get('as_on_date'),
            "ageing_based_on": "Due Date",
            "range": "30, 60, 90, 120",
            "party_type": "Supplier",
        }

    if doc.get("supplier"):
        filters["party"] = [doc.get("supplier")]

    if doc.get("supplier_group"):
        filters["supplier_group"] = doc.get("supplier_group")

    x = frappe.call(
        "frappe.desk.query_report.run",
        report_name="Accounts Payable",

        filters=filters,
        ignore_prepared_report=True
    ) 
    
    # Check if x["result"] is a list
    if isinstance(x["result"], list):
        # If results exist, pop the last result
        if x["result"]:
            x["result"].pop()

        # Filter the result and assign branch for relevant voucher types
        filtered_result = x["result"]

        # for a in x["result"]:
        #     # Ensure 'a' is a dictionary
        #     if isinstance(a, dict) and "voucher_type" in a:
        #         if a.get("voucher_type") in ['Sales Invoice', 'Purchase Invoice']:
        #             a["branch"] = frappe.db.get_value(a.get("voucher_type"), a.get("voucher_no"), "branch")
                
        #         if a.get("voucher_type") == 'Journal Entry':
        #             a["branch"] = frappe.db.get_value(a.get("voucher_type"), a.get("voucher_no"), "branch")
                
        #         filtered_result.append(a)
        #     else:
        #         frappe.log_error(message=f"Unexpected item in result: {a}", title='Unexpected Result Structure')

        # Loop through filtered result and append items to the document
        bp.items = []
        for res in filtered_result:
            # Validate that the party exists in the Customer or Supplier doctype
            if not frappe.db.exists("Customer", res.get('party')) and not frappe.db.exists("Supplier", res.get('party')):
                frappe.log_error(f"Invalid or missing party: {res.get('party')} for reference {res.get('name')}", "Bulk Payment Tool Validation")
                continue  # Skip this row if party is invalid
            
            # Append validated data to doc.items
            bp.append("items", {
                'posting_date': res.get('posting_date'),
                'reference_no': res.get('voucher_no'),
                'party': res.get('party'),
                'party_account': res.get('party_account'),
                'bill_no': res.get('bill_no'),
                'bill_date': res.get('bill_date'),
                'outstanding': res.get('outstanding'),
                'to_pay': 0,
                'voucher_type': res.get('voucher_type'),
                'branch': res.get('branch'),
                'cheque_reference_no': res.get('cheque_reference_no', '-'),
                'cheque_reference_date': res.get('cheque_reference_date', res.get('posting_date')),
                'mode_of_payment': doc.get('mode_of_payment')
            })

        # Save the document
        bp.save()
        # Respond with success
        frappe.response["message"] = "Success"
    else:
        frappe.log_error(message="Expected a list for x['result']", title='Unexpected Result Structure')
    
@frappe.whitelist()
def process_payments():
    doc = json.loads(frappe.form_dict.get('doc'))
    name = doc.get('name')

    bp = frappe.get_doc("Bulk Payment Tool", name)
    bp.save()

    total_payments = sum(item.to_pay for item in bp.items)

    if total_payments <= 0:
        frappe.throw("Total payment amount must be greater than 0")

    bp.payment = []

    # for item in items:
    grouped_data = {}
    for record in bp.items:
        party = record.party
        to_pay = record.to_pay
        if party in grouped_data:
            grouped_data[party] += to_pay
        else:
            grouped_data[party] = to_pay
    
    for party, amount in grouped_data.items():
        
        if amount > 0:
            default_bank_account = get_default_bank_account(party)
            bp.append("payment", {
                "party": party,
                "posting_date": bp.payment_posting_date,
                "amount_to_pay": amount,
                "mode_of_payment": bp.mode_of_payment,
                # "reference_number": "",
                # "reference_date": "",
                # "cheque_reference_no": "", 
                # "cheque_reference_date": "",
                "bank_account": default_bank_account,
                "branch": bp.branch,
                "reference_number" : "-",
                "reference_date": bp.payment_posting_date
            })

    bp.save()

    frappe.response["message"] = "Success"

def get_default_bank_account(party):
    bank_accounts = frappe.db.get_all("Bank Account", filters={"party_type": "Supplier", "party": party, "is_default": 1})

    if bank_accounts:
        return bank_accounts[0].name
    
    frappe.throw(f"Default Bank Account is not specifie for {party}")




def get_accounts_payable_filters(app_name, report_name):

    has_range1_filter = False

    js_file_path = os.path.join(
        frappe.get_app_path(app_name),
        "accounts",
        "report",
        "accounts_payable",
        f"{report_name.replace(' ', '_').lower()}.js"
    )
    
    with open(js_file_path, 'r') as file:
        content = file.read()
        if "range1" in content:
            has_range1_filter = True

    return has_range1_filter