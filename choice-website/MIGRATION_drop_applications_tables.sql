-- ============================================================
-- MIGRATION: Drop Supabase application tables and functions
-- Decision: All rental applications are processed exclusively through the
--           external GAS system at apply-choice-properties.pages.dev.
--           The Supabase applications table and related objects are no longer
--           authoritative and are safe to remove.
--
-- BEFORE RUNNING:
--   1. Verify the applications table row count:
--        SELECT COUNT(*) FROM applications;
--   2. Export any rows you want to keep before proceeding.
--   3. Run in Supabase SQL Editor (project dashboard).
--   4. After running, delete the 7 decommissioned Edge Functions from:
--        Supabase Dashboard -> Edge Functions -> (select each) -> Delete
--      Decommissioned = any function NOT in this list:
--        send-inquiry, send-message, imagekit-upload, imagekit-delete
-- ============================================================

BEGIN;

-- Step 1: Drop application-specific stored functions
DROP FUNCTION IF EXISTS get_application_status(TEXT, TEXT)       CASCADE;
DROP FUNCTION IF EXISTS get_lease_financials(TEXT, TEXT)          CASCADE;
DROP FUNCTION IF EXISTS sign_lease(TEXT, TEXT, TEXT)              CASCADE;
DROP FUNCTION IF EXISTS sign_lease_co_applicant(TEXT, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS submit_tenant_reply(TEXT, TEXT, TEXT)     CASCADE;
DROP FUNCTION IF EXISTS get_my_applications()                     CASCADE;
DROP FUNCTION IF EXISTS claim_application(TEXT, TEXT)             CASCADE;
DROP FUNCTION IF EXISTS get_apps_by_email(TEXT)                   CASCADE;
DROP FUNCTION IF EXISTS get_app_id_by_email(TEXT)                 CASCADE;
DROP FUNCTION IF EXISTS mark_expired_leases()                     CASCADE;
DROP FUNCTION IF EXISTS generate_app_id()                         CASCADE;
DROP FUNCTION IF EXISTS trg_applications_count()                  CASCADE;

-- Step 2: Drop the admin view (depends on applications table)
DROP VIEW IF EXISTS admin_application_view CASCADE;

-- Step 3: Drop co_applicants (FK to applications)
DROP TABLE IF EXISTS co_applicants CASCADE;

-- Step 4: Drop the applications table
-- CASCADE removes any FK-referencing rows in messages (tenant reply threads).
-- If you still use messages for non-application landlord messaging, first run:
--   ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_app_id_fkey;
-- Then replace the CASCADE below with a plain DROP.
DROP TABLE IF EXISTS applications CASCADE;

-- Step 5: Verify (uncomment and run separately to confirm)
-- SELECT table_name FROM information_schema.tables
--   WHERE table_schema = 'public' AND table_name IN ('applications','co_applicants');
-- Expected: 0 rows
--
-- SELECT routine_name FROM information_schema.routines
--   WHERE routine_schema = 'public' AND routine_name IN (
--     'get_application_status','get_lease_financials','sign_lease',
--     'sign_lease_co_applicant','submit_tenant_reply','get_my_applications',
--     'claim_application','get_apps_by_email','get_app_id_by_email',
--     'mark_expired_leases','generate_app_id','trg_applications_count');
-- Expected: 0 rows

COMMIT;
