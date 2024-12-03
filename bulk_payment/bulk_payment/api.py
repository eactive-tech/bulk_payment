import frappe, json
@frappe.whitelist()
def bulk_payment_process():
    doc = json.loads(frappe.form_dict.get('doc'))
    
    for item in doc.get('payment'):
        frappe.log_error(message=item,title='item')

    succeed = 0
    total_entries = 0
    successful_entries = []
    errors = []

    if len(doc.get("payment")) > 0:
        total_entries = len(doc.get("payment"))

        for item in doc.get("payment"):
            try:
                payment_entry = frappe.get_doc({
                    "doctype": "Payment Entry",
                    "payment_type": "Pay",
                    "mode_of_payment": item.get("mode_of_payment"),
                    "posting_date": doc.get("payment_posting_date"),
                    "bank_account": doc.get("company_bank_account"),
                    "party_type": "Supplier",
                    "party": item.get("party"),
                    "paid_to": item.get("party_account"),
                    "paid_from": doc.get("paid_from_account"),
                    "paid_amount": item.get("amount_to_pay"),
                    "received_amount": item.get("amount_to_pay"),
                    "reference_no": item.get("reference_number"),
                    "reference_date": item.get("reference_date"),
                    "cf_code": item.get("cf_code"),
                    "branch": item.get("branch"),
                    "source_exchange_rate": 1,
                    "Account Currency" : "INR",
                })
                payment_entry.append("references", dict(
                    doctype="Payment Entry Reference",
                    reference_doctype=item.get("voucher_type"),
                    reference_name=item.get("reference_number"),
                    allocated_amount=item.get("amount_to_pay"),
                    
                ))
                payment_entry.submit()
                succeed = succeed + 1

                
                successful_entries.append({
                    "party": item.get("party"),
                    "voucher_type": item.get("voucher_type"),
                    "posting_date": doc.get("payment_posting_date"),
                    "amount_to_pay": item.get("amount_to_pay"),
                    "reference_no": item.get("reference_no"),
                    "reference_date": item.get("reference_date"),
                    "mode_of_payment": item.get("mode_of_payment"),
                    "cf_code": item.get("cf_code"),
                    "branch": item.get("branch"),
                })

            except Exception as e:
                frappe.db.rollback()
                error_message = f"Error while processing item {item.get('reference_no')}: {str(e)}"
                frappe.log_error(message=error_message,title="error_message")  
                errors.append({
                    "party": item.get("party"),
                    "reference_no": item.get("reference_no"),
                    "error": error_message,
                })



    if succeed == total_entries:
        try:
            bulk_payment_doc = frappe.get_doc("Bulk Payment Tool", doc.get("name")) 
            for entry in successful_entries:
                bulk_payment_doc.append("payment", {
                    "party": entry.get("party"),
                    "voucher_type": entry.get("voucher_type"),
                    "posting_date": entry.get("posting_date"),
                    "amount_to_pay": entry.get("amount_to_pay"),
                    "reference_no": entry.get("reference_no"),
                    "reference_date": entry.get("reference_date"),
                    "mode_of_payment": entry.get("mode_of_payment"),
                    "cf_code": entry.get("cf_code"),
                    "branch": entry.get("branch"),
                })
            bulk_payment_doc.save()
            frappe.db.commit()
            frappe.response["message"] = "All Payment Entries Processed and Updated in Bulk Payment Tool Successfully"
        except Exception as e:
            frappe.response["message"] = f"Error while updating Bulk Payment Tool: {str(e)}"
    else:
        frappe.response["message"] = f"{succeed} out of {total_entries} Payment Entries Processed Successfully. Some Errors Occurred."


    if errors:
        frappe.response["message"] = errors


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
    
    frappe.log_error(message=x, title='Bulk Payment Outstanding Response')
    
    # Check if x["result"] is a list
    if isinstance(x["result"], list):
        # If results exist, pop the last result
        if x["result"]:
            x["result"].pop()

        # Filter the result and assign branch for relevant voucher types
        filtered_result = []

        for a in x["result"]:
            # Ensure 'a' is a dictionary
            if isinstance(a, dict) and "voucher_type" in a:
                if a.get("voucher_type") in ['Sales Invoice', 'Purchase Invoice']:
                    a["branch"] = frappe.db.get_value(a.get("voucher_type"), a.get("voucher_no"), "branch")
                
                if a.get("voucher_type") == 'Journal Entry':
                    a["branch"] = frappe.db.get_value(a.get("voucher_type"), a.get("voucher_no"), "custom_branch")
                
                filtered_result.append(a)
            else:
                frappe.log_error(message=f"Unexpected item in result: {a}", title='Unexpected Result Structure')

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
                'reference_no': res.get('name'),
                'party': res.get('party'),
                'party_account': res.get('party_account'),
                'bill_no': res.get('bill_no'),
                'bill_date': res.get('bill_date'),
                'outstanding': res.get('outstanding'),
                'to_pay': res.get('outstanding'),
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
    