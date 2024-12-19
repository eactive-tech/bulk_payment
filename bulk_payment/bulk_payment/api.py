import frappe, json

@frappe.whitelist()
def bulk_payment_outstanding():
    doc = json.loads(frappe.form_dict.get('doc'))
    name = doc.get('name')
    
    bp = frappe.get_doc("Bulk Payment Tool", name)

    x = frappe.call(
        "frappe.desk.query_report.run",
        report_name="Accounts Payable",

        filters={
            "company": doc.get('company'),
            "report_date": doc.get('as_on_date'),
            "ageing_based_on": "Due Date",
            "range": "30, 60, 90, 120",
            "party_type": "Supplier",
        },
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
    
    
    
# @frappe.whitelist()
# def get_party_detail():
#     doc = json.loads(frappe.form_dict.get('doc'))
#     party = doc.get('party')
    
#     address = frappe.db.get_value('Dynamic Link',{'parenttype':'Address','link_name':party},['parent'],as_dict=1)
    
#     email = frappe.get_doc('Address',address.parent).email_id
    
#     bank_details = frappe.db.get_value('Bank Account', {'party':party},['account_name','bank_account_no','branch_code'],as_dict=1)
    
#     bank_details['email'] = email
    
#     return bank_details
    
@frappe.whitelist()
def generate_csv():
    doc = json.loads(frappe.form_dict)
    
    

    