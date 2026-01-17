import frappe
from frappe.utils import add_days, now_datetime

def delete_expired_ghost_users():
	"""
	Deletes Ghost users that have exceeded the expiration days.
	"""
	settings = frappe.get_single("Ghost Settings")
	if not settings.enable_ghost_feature or not settings.enable_auto_cleanup:
		return

	expiration_days = settings.expiration_days or 30
	# Safety check: Don't allow very short expiration by mistake, unless 0 (immediate? No, 0 usually means disable or massive bug risk).
	if expiration_days < 1:
		expiration_days = 1

	expiry_date = add_days(now_datetime(), -expiration_days)
	ghost_domain = settings.ghost_email_domain or "guest.local"

	# Find users to delete
	# Criteria:
	# 1. Role contains 'Ghost' (Checked via User Role usually, but checking query is faster)
	# 2. Email ends with ghost domain
	# 3. Creation < expiry_date
	# 4. Filter by specific 'Ghost' role to be safe.
	
	users = frappe.db.sql("""
		SELECT name FROM `tabUser`
		WHERE creation < %s
		AND email LIKE %s
		AND name IN (
			SELECT parent FROM `tabHas Role` WHERE role = %s
		)
	""", (expiry_date, f"%@{ghost_domain}", settings.ghost_role), as_dict=True)

	for u in users:
		# Use frappe.delete_doc to ensure strict cleanup (links etc)
		# This might be slow if there are thousands. 
		# For extreme scalability, we might use bulk delete if no important links exist.
		# But standard delete is safer for now.
		try:
			frappe.delete_doc("User", u.name, ignore_permissions=True, force=1)
			# Commit every 100 to avoid long transaction? 
			# frappe.db.commit() # optional, depends on volume
		except Exception:
			frappe.log_error(f"Failed to delete ghost user {u.name}", "Ghost Cleanup")

