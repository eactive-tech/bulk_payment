# Copyright (c) 2024, Eactive Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BulkPaymentTool(Document):

	def validate(self):
		self.validate_amount_to_pay()

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
					"custom_bulk_payment": self.name
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
				payment_entry.save()
				payment_entry.submit()


				item.payment_entry = payment_entry.name


	def validate_amount_to_pay(self):
		for item in self.get("items"):
			if item.outstanding < 0:
				if item.to_pay > 0 or item.outstanding > item.to_pay:
					frappe.throw(f"Please Enter Correct Value at row no {item.idx}" )
				