# Copyright (c) 2024, Eactive Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from bulk_payment.bulk_payment.api import process_payments, get_default_bank_account

class BulkPaymentTool(Document):

	def validate(self):
		self.validate_amount_to_pay()
		self.update_payment_entries()

	def before_submit(self):

		self.items = [item for item in self.get("items") if item.to_pay != 0]

		if len(self.get("payment")) > 0:
			for item in self.get("payment"):
				payment_entry = frappe.get_doc({
					"doctype": "Payment Entry",
					"payment_type": "Pay",
					"mode_of_payment": self.mode_of_payment,
					"posting_date": self.get("payment_posting_date"),
					"bank_account": self.get("company_bank_account"),
					"party_bank_account": item.get("bank_account"),
					"party_type": "Supplier",
					"party": item.get("party"),
					"paid_to": item.get("party_account"),
					"paid_from": self.get("paid_from_account"),
					"paid_amount": item.get("amount_to_pay"),
					"received_amount": item.get("amount_to_pay"),
					"reference_no": item.get("reference_number"),
					"reference_date": item.get("reference_date"),
					"branch": self.branch,
					"source_exchange_rate": 1,
					"Account Currency" : frappe.db.get_value("Account", self.get("paid_from_account"), "account_currency"),
					"custom_bulk_payment": self.name,
					"cf_code": item.get('cf_code')
				})

				for invoice in self.items:
					if invoice.party == item.party:
						payment_entry.append("references", dict(
							doctype="Payment Entry Reference",
							reference_doctype=invoice.get("voucher_type"),
							reference_name=invoice.get("reference_no"),
							outstanding_amount=invoice.get("outstanding"),
							allocated_amount=invoice.get("to_pay"),
						))

				for invoice in self.advances:
					if invoice.party == item.party:
						payment_entry.append("references", dict(
							doctype="Payment Entry Reference",
							reference_doctype=invoice.get("voucher_type"),
							reference_name=invoice.get("reference_no"),
							outstanding_amount=invoice.get("outstanding"),
							allocated_amount=invoice.get("to_pay"),
						))
				payment_entry.save()
				payment_entry.submit()


				item.payment_entry = payment_entry.name


	def validate_amount_to_pay(self):

		# if len(self.items):
		# 	frappe.throw("Please Pull Outstandings")

		for item in self.get("items"):
			if item.outstanding < 0:
				if item.to_pay > 0 or item.outstanding > item.to_pay:
					frappe.throw(f"Please Enter Correct Value at row no {item.idx}" )
				
	def update_payment_entries(self):
		self.payment = []
		grouped_data = {}
		for record in self.items:
			party = record.party
			to_pay = record.to_pay
			if party in grouped_data:
				grouped_data[party] += to_pay
			else:
				grouped_data[party] = to_pay

		for record in self.advances:
			party = record.party
			to_pay = record.to_pay
			if party in grouped_data:
				grouped_data[party] += to_pay
			else:
				grouped_data[party] = to_pay

		for party, amount in grouped_data.items():
			
			if amount > 0:
				default_bank_account = get_default_bank_account(party)
				self.append("payment", {
					"party": party,
					"party_name": frappe.db.get_value("Supplier", party,"supplier_name"),
					"posting_date": self.payment_posting_date,
					"amount_to_pay": amount,
					"mode_of_payment": self.mode_of_payment,
					# "reference_number": "",
					# "reference_date": "",
					# "cheque_reference_no": "", 
					# "cheque_reference_date": "",
					"bank_account": default_bank_account,
					"account_number": frappe.db.get_value("Bank Account", default_bank_account, "bank_account_no"),
					"beneficiary_name": frappe.db.get_value("Bank Account", default_bank_account, "account_name"),
					# "transaction_type": frappe.db.get_value("Bank Account", default_bank_account, ""),
					"bank_name": frappe.db.get_value("Bank Account", default_bank_account, "bank"),
					"ifsc_code": frappe.db.get_value("Bank Account", default_bank_account, "branch_code"),
					"reference_number" : "-",
					"reference_date": self.payment_posting_date
				})
	

	def before_cancel(self):
		payments = frappe.db.get_all("Payment Entry", filters={"custom_bulk_payment": self.name})
		for payment in payments:
			p = frappe.get_doc("Payment Entry", payment.name)
			p.cancel()