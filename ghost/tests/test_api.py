import frappe
import unittest
from ghost.api.ghost import create_ghost_session

class TestFrappeIdentityAPI(unittest.TestCase):
	def setUp(self):
		# Ensure settings are enabled
		settings = frappe.get_single("Ghost Settings")
		settings.enable_ghost_feature = 1
		settings.save()

	def test_create_ghost_session(self):
		# Create a ghost
		result = create_ghost_session()
		
		# Verify return structure
		self.assertIn("user", result)
		self.assertIn("api_key", result)
		self.assertIn("api_secret", result)
		
		email = result["user"]
		self.assertTrue(email.startswith("ghost_"))
		
		# Verify User document
		user = frappe.get_doc("User", email)
		self.assertTrue(user)
		
		# Verify Role
		roles = [r.role for r in user.roles]
		self.assertIn("Ghost", roles)
		
		# Verify API Key matches (hashed secret can't be verified easily, but key exists)
		self.assertEqual(user.api_key, result["api_key"])
		
		print(f"\n[Success] Created Ghost User: {email}")

	def tearDown(self):
		pass

	def test_cleanup_logic(self):
		from frappe.utils import add_days, now_datetime
		from ghost.tasks import delete_expired_ghost_users
		
		# Setup: Enable cleanup
		settings = frappe.get_single("Ghost Settings")
		settings.enable_auto_cleanup = 1
		settings.expiration_days = 30
		settings.save()

		# Create Old Ghost (expired)
		old_email = "old_ghost@guest.local"
		if not frappe.db.exists("User", old_email):
			u = frappe.get_doc({
				"doctype": "User",
				"email": old_email,
				"first_name": "Old",
				"roles": [{"role": "Ghost"}]
			}).insert(ignore_permissions=True)
			# Hack creation date
			frappe.db.set_value("User", old_email, "creation", add_days(now_datetime(), -35))
		
		# Create New Ghost (not expired)
		new_email = "new_ghost@guest.local"
		if not frappe.db.exists("User", new_email):
			frappe.get_doc({
				"doctype": "User",
				"email": new_email,
				"first_name": "New",
				"roles": [{"role": "Ghost"}]
			}).insert(ignore_permissions=True)

		# Run Cleanup
		delete_expired_ghost_users()

		# Verify
		self.assertFalse(frappe.db.exists("User", old_email), "Old ghost should be deleted")
		self.assertTrue(frappe.db.exists("User", new_email), "New ghost should be kept")
		print("\n[Success] Verified Cleanup: Old deleted, New kept.")

	def test_cleanup_disabled(self):
		from frappe.utils import add_days, now_datetime
		from ghost.tasks import delete_expired_ghost_users

		# Setup: DISABLE cleanup
		settings = frappe.get_single("Ghost Settings")
		settings.enable_auto_cleanup = 0
		settings.save()

		# Create Old Ghost
		old_email = "kept_ghost@guest.local"
		if not frappe.db.exists("User", old_email):
			u = frappe.get_doc({
				"doctype": "User",
				"email": old_email,
				"first_name": "Kept",
				"roles": [{"role": "Ghost"}]
			}).insert(ignore_permissions=True)
			frappe.db.set_value("User", old_email, "creation", add_days(now_datetime(), -35))

		# Run Cleanup
		delete_expired_ghost_users()

		# Verify
		self.assertTrue(frappe.db.exists("User", old_email), "Old ghost should remain when cleanup is disabled")
		print("\n[Success] Verified Control: Cleanup respects disabled setting.")

	def test_convert_to_real_user(self):
		from ghost.api.ghost import create_ghost_session, convert_to_real_user
		
		# 1. Create Ghost
		ghost_data = create_ghost_session()
		ghost_email = ghost_data["user"]
		
		# 2. Simulate some data (e.g. assign a role or a doc)
		# For simplicity, just verify existence
		self.assertTrue(frappe.db.exists("User", ghost_email))
		
		# 3. Convert
		real_email = "real_user@example.com"
		if frappe.db.exists("User", real_email):
			frappe.delete_doc("User", real_email, force=True)

		result = convert_to_real_user(ghost_email, real_email, "Real", "Human")
		
		# 4. Verify
		self.assertFalse(frappe.db.exists("User", ghost_email), "Ghost email should be renamed")
		self.assertTrue(frappe.db.exists("User", real_email), "Real email should exist")
		
		user = frappe.get_doc("User", real_email)
		self.assertEqual(user.first_name, "Real")
		self.assertEqual(user.last_name, "Human")
		
		roles = [r.role for r in user.roles]
		self.assertNotIn("Ghost", roles, "Ghost role should be removed")
		self.assertIn("Website User", roles, "Should have default role")
		
		print(f"\n[Success] Converted {ghost_email} -> {real_email}")
