# Attendance Import And Late Deduction Implementation Plan

This document tracks the planned implementation for attendance import and late-coming leave deduction in the Leave Management MST project.

The goal is to build this feature carefully, with full HR/admin control, because attendance data can come from different sources and can sometimes be incomplete or wrong.

## Current Decision Status

| Area | Status |
|---|---|
| Attendance data entry sources | Decided |
| Employee matching strategy | Decided |
| Office start and grace rules | Decided |
| Late-coming monthly threshold | Decided |
| Deduction type and amount | Decided |
| HR approval before deduction | Decided |
| Employee visibility | Decided |
| Employee-specific schedule/flexibility grants | Decided |
| Secure preview connector architecture | Decided |

## Project Progress

### Planning

| Item | Status |
|---|---|
| Create planning document | Done |
| Decide attendance data entry sources | Done |
| Decide employee matching identifiers | Done |
| Decide office start and grace timing | Done |
| Decide late mark threshold and deduction amount | Done |
| Decide leave deduction priority | Done |
| Decide insufficient leave balance handling | Done |
| Decide deduction cycle controls | Done |
| Decide late exception/allowed flow | Done |
| Decide automatic deduction modes | Done |
| Decide admin-configurable effective-dated policy settings | Done |
| Decide employee visibility and dedicated page/report | Done |
| Decide configurable email notifications | Done |
| Decide leave record visibility for late deductions | Done |
| Decide default my_leave approved display for late deductions | Done |
| Decide HR/admin unified tabbed management page | Done |
| Decide attendance upload columns/template | Done |
| Decide duplicate attendance handling | Done |
| Decide HR report integration | Done |
| Add developer implementation specification | Done |
| Add enterprise readiness expansion | Done |
| Decide employee-specific attendance schedule/flexibility grants | Done |
| Add total control final guardrails | Done |
| Add secure preview connector architecture | Done |
| Add notification orchestration specification | Done |
| Add final deep scan enterprise additions | Done |

### Implementation

| Item | Status |
|---|---|
| Database models | Not started |
| Admin/HR attendance UI | Not started |
| CSV/Excel upload flow | Not started |
| Manual attendance entry flow | Not started |
| Late-coming calculation engine | Not started |
| Leave deduction application | Not started |
| Tests | Not started |
| Production documentation updates | Not started |

## Decision 1: Attendance Data Entry Sources

Attendance should support multiple input methods.

### What We Will Build

The system will support these attendance entry paths:

1. Manual single employee entry
2. Manual CSV/Excel file upload
3. Future automatic biometric import

### Why This Is Needed

The company needs total operational control.

Biometric attendance may work most of the time, but there can be real-world problems:

- biometric machine failure
- network or sync failure
- missed punch
- wrong punch
- employee code mismatch
- delayed export
- manual HR correction

Because of this, attendance cannot depend only on automatic biometric data.

### How It Will Work

All attendance sources will write into one common attendance record system.

Each attendance record should store fields similar to:

```text
employee
date
check_in_time
check_out_time
source
created_by
updated_by
remarks
```

The `source` field should identify where the record came from:

```text
manual
file_upload
biometric
```

The late-coming deduction engine should read the final attendance records and should not care whether the record came from manual entry, uploaded file, or biometric sync.

This keeps the deduction logic consistent and prevents duplicate systems.
## Decision 2: Employee Matching Strategy

Attendance imports and manual entries should support all practical employee identifiers.

### What We Will Build

The system should be able to match employees using:

1. Employee Code / Employee ID
2. Email
3. Employee Name
4. Phone Number
5. Biometric Device ID

### Why This Is Needed

Different attendance sources may provide different identifiers.

For example:

- HR-prepared CSV files may use employee code or email.
- Biometric exports may use biometric device user id.
- Manual corrections may be easier by employee name.
- Some files may include phone number instead of employee code.

Supporting all identifiers gives HR/admin flexibility and reduces failed imports.

### How It Will Work

The import system should use a predictable matching priority when multiple identifiers are available.

Recommended matching priority:

```text
1. Employee Code / Employee ID
2. Biometric Device ID
3. Email
4. Phone Number
5. Employee Name
```

Employee name should be the last fallback because names can be duplicated, misspelled, abbreviated, or formatted differently across systems.

If a row cannot be matched safely, the system should not guess silently. It should mark the row as unmatched and show it to HR/admin for correction.

If a row matches more than one employee, the system should mark it as ambiguous and require HR/admin review.

### Data We May Need On Employee Profile

To support this fully, the employee/profile model may need fields such as:

```text
employee_code
biometric_device_id
phone_number
```

Email and employee name may already exist through the user account/profile data.

The implementation phase should inspect the existing models before adding new fields.
## Decision 3: Office Start And Grace Rule

Late coming should be calculated using a fixed office start time and grace period.

### What We Will Build

The standard office timing rule will be:

```text
Office start: 10:00 AM
On-time limit: 10:15 AM
Warning window: after 10:15 AM to 10:30 AM
Deduction-counted late after: 10:30 AM
```

An employee is considered fully on time when check-in is at or before 10:15 AM.

An employee gets a warning-only late entry when check-in is after 10:15 AM and at or before 10:30 AM. This warning should not count for leave deduction.

An employee gets a deduction-counted late mark when check-in is after 10:30 AM.

### Why This Is Needed

A clear timing rule prevents confusion during attendance calculation and leave deduction.

The warning window gives employees a controlled buffer while still allowing HR/admin to track repeated late arrivals separately from deduction-counted late marks.

### How It Will Work

For each attendance record, the late-coming engine should compare the employee check-in time with the on-time limit, warning window, and deduction-counted late limit.

Examples:

```text
10:00 AM -> on time
10:15 AM -> on time
10:16 AM -> warning only, not counted for deduction
10:30 AM -> warning only, not counted for deduction
10:31 AM -> counted late mark for deduction
11:00 AM -> counted late mark for deduction
```

The initial implementation will treat this as the standard rule for all employees.

If shift-based timing is needed later, the design should allow adding employee-specific or shift-specific timing rules without rewriting the attendance records.
## Decision 4: Monthly Late Mark Deduction Rule

Leave deduction should happen for every group of three deduction-counted late marks in a month.

### What We Will Build

The monthly rule will be:

```text
Every 3 deduction-counted late marks deduct 0.5 day leave
```

Warning-only entries from 10:16 AM to 10:30 AM do not count toward this deduction.

Only check-ins after 10:30 AM count as deduction-counted late marks.

### Why This Is Needed

This creates a clear and repeatable rule that HR/admin can verify easily.

The rule avoids deducting leave for minor warning-window delays while still enforcing repeated late arrivals after the allowed limit.

### How It Will Work

For each employee and month, the system should count deduction-counted late marks.

Deduction examples:

```text
0 late marks -> 0 day deduction
1 late mark -> 0 day deduction
2 late marks -> 0 day deduction
3 late marks -> 0.5 day deduction
4 late marks -> 0.5 day deduction
5 late marks -> 0.5 day deduction
6 late marks -> 1.0 day deduction
7 late marks -> 1.0 day deduction
8 late marks -> 1.0 day deduction
9 late marks -> 1.5 day deduction
```

Formula:

```text
deduction_days = floor(deduction_counted_late_marks / 3) * 0.5
```

The system should keep the late mark count and deduction amount visible to HR/admin before applying the deduction.
## Decision 5: Leave Deduction Priority

Late-coming deductions should use available paid leave balances before becoming unpaid.

### What We Will Build

The deduction priority will be:

```text
1. Earned Leave
2. Sick Leave
```

Earned Leave should be deducted first.

If Earned Leave balance is not enough, the remaining deduction should use Sick Leave.

### Why This Is Needed

Earned Leave is the primary balance for attendance-related penalties. Sick Leave is a fallback only when Earned Leave is not available or not enough.

This keeps the policy predictable while avoiding immediate unpaid deduction when the employee still has available paid leave.

### How It Will Work

Example for a 0.5 day late-coming deduction:

```text
Earned Leave balance 2.0, Sick Leave balance 3.0 -> deduct 0.5 from Earned Leave
Earned Leave balance 0.25, Sick Leave balance 3.0 -> deduct 0.25 from Earned Leave and 0.25 from Sick Leave
Earned Leave balance 0.0, Sick Leave balance 3.0 -> deduct 0.5 from Sick Leave
```

The system should record exactly how much was deducted from each leave type so HR/admin and the employee can understand the adjustment later.
## Decision 6: Insufficient Leave Balance Handling

When Earned Leave and Sick Leave are not enough, HR/admin should have all available control options.

### What We Will Build

If the required late-coming deduction is greater than available Earned Leave and Sick Leave, the system should support all three outcomes:

1. Remaining amount becomes Unpaid/LOP
2. HR/admin handles the remaining amount manually
3. HR/admin allows negative leave balance

### Why This Is Needed

Different cases may need different handling.

For example:

- Unpaid/LOP is useful when policy must be applied directly.
- Manual handling is useful when HR wants to verify payroll impact or special approval.
- Negative leave balance is useful when the company wants to recover the leave from future credit instead of marking it unpaid immediately.

### How It Will Work

The system should calculate the shortage after using Earned Leave first and Sick Leave second.

Example:

```text
Required deduction: 1.0 day
Earned Leave available: 0.25 day
Sick Leave available: 0.25 day
Shortage: 0.5 day
```

HR/admin should then be able to choose one of these actions for the shortage:

```text
Convert 0.5 day to Unpaid/LOP
Keep 0.5 day pending for manual HR/admin handling
Allow -0.5 day balance
```

The system should record which option was selected, who selected it, when it was selected, and why.

Default shortage handling during calculation preview:

```text
Remaining amount becomes Unpaid/LOP
```

This is the standard/default policy. HR/admin can still override the shortage handling to manual review or negative balance before the deduction is applied.
## Decision 7: Deduction Cycle Controls

Late-coming deduction should be controlled from the admin/HR panel by cycle.

### What We Will Build

Admin/HR should be able to run late-coming deduction by:

1. Weekly cycle
2. Monthly cycle
3. Custom date range

Default cycle:

```text
Monthly
```

### Why This Is Needed

Different HR workflows may need different deduction periods.

Monthly deduction is useful for payroll and leave closing.

Weekly deduction is useful for stricter attendance monitoring.

Custom date range is useful when HR/admin wants to process a specific period, recheck a correction period, or handle special cases.

### How It Will Work

Admin/HR should have a policy/control screen with settings like:

```text
Deduction cycle: Weekly / Monthly / Custom
Weekly run day: Monday / Tuesday / Wednesday / Thursday / Friday / Saturday / Sunday
Monthly run day: selected date or last day of month
Custom range: from date to date
```

Custom date range should be manually triggered by HR/admin.

The deduction engine should calculate late marks only inside the selected cycle or custom range.

## Decision 8: Late Exception / Allowed Flow

HR/admin should be able to mark a late record as allowed or excused so it does not count for deduction.

### What We Will Build

Each attendance record should have a final late/deduction status such as:

```text
On time
Warning only
Counted for deduction
Allowed / Excused
Pending review
Invalid / Needs correction
```

If an employee comes late but HR/admin allows it, the record should be marked:

```text
Allowed / Excused
```

Allowed/excused records should not count toward late-coming deduction.

### Why This Is Needed

Some late arrivals are valid and should not cause leave deduction.

Examples:

- employee informed HR/admin in advance
- client visit
- official work
- medical reason
- transport issue approved by HR/admin
- biometric or attendance correction
- management-approved exception

### How It Will Work

System classification should happen first:

```text
10:15 AM or earlier -> On time
10:16 AM to 10:30 AM -> Warning only
10:31 AM or later -> Counted for deduction
```

Then HR/admin can override a counted late record to:

```text
Allowed / Excused
```

The override should store audit details:

```text
approved_by
approved_at
reason
remarks
previous_status
new_status
```

The deduction engine should count only records whose final status is:

```text
Counted for deduction
```

It should ignore:

```text
On time
Warning only
Allowed / Excused
Invalid / Needs correction
```

Pending review records should not be auto-applied.

## Decision 9: Deduction Application Modes And Automation

The system should support manual and automatic deduction modes, controlled from the admin/HR panel.

### What We Will Build

Deduction mode options:

```text
Manual Review Only
Auto Apply Clean Records
Fully Automatic
```

Default mode:

```text
Manual Review Only
```

Recommended production mode after testing:

```text
Auto Apply Clean Records
```

### Why This Is Needed

Late-coming deduction affects leave balance and payroll impact, so the system needs strong control.

Manual review is safest when the feature is new or attendance data quality is uncertain.

Auto apply is useful after the company trusts the import process and policy configuration.

Fully automatic is available for strict operations, but should still skip invalid, unmatched, or ambiguous data.

### How It Will Work

Manual Review Only:

```text
System calculates late marks and deduction preview.
HR/admin must review and apply deductions manually.
```

Auto Apply Clean Records:

```text
System automatically applies deductions only for clean records.
Risky records stay in Needs Review.
```

Fully Automatic:

```text
System applies all eligible deductions using configured defaults.
Invalid, unmatched, ambiguous, or blocked records are skipped and sent to review.
```

A clean record means:

```text
employee matched confidently
attendance record is valid
no duplicate/conflicting attendance for the date
late record is not Allowed / Excused
no approved leave conflict
no approved WFH conflict
no pending correction request
deduction balance can be calculated clearly
shortage can follow default Unpaid/LOP rule
```

A risky record means:

```text
employee unmatched or ambiguous
manual correction needed
employee already has approved leave on that day
employee already has approved WFH on that day
attendance has missing or invalid time
duplicate import changed previous data
HR/admin marked employee/date as exception
shortage needs HR/admin override
```

Automatic schedule controls should include:

```text
Auto deduction enabled: Yes / No
Deduction cycle: Weekly / Monthly / Custom
Run time: selected time
Weekly run day: selected weekday
Monthly run day: selected date or last day of month
```

Custom date range should always require HR/admin trigger.

Every automatic run should create an audit log:

```text
run date/time
cycle covered
trigger type: system scheduler / HR admin / admin
employees processed
deductions applied
records skipped
records needing review
errors
```
## Decision 10: Admin-Configurable Effective-Dated Policy Settings

All late-coming policy values should be configurable from the admin/HR panel, with default values and effective dates.

### What We Will Build

Admin should be able to configure late policy settings such as:

```text
On-time until: 10:15 AM
Warning until: 10:30 AM
Count deduction after: 10:30 AM
Every X counted late marks: 3
Deduct days: 0.5
Deduction cycle: Weekly / Monthly / Custom
Default shortage handling: Unpaid/LOP
Deduction mode: Manual Review Only / Auto Apply Clean Records / Fully Automatic
```

Default values should be:

```text
On-time until: 10:15 AM
Warning until: 10:30 AM
Count deduction after: 10:30 AM
Every X counted late marks: 3
Deduct days: 0.5
Deduction cycle: Monthly
Default shortage handling: Unpaid/LOP
Deduction mode: Manual Review Only
```

### Why This Is Needed

Company attendance policy can change over time.

Admin must be able to change rules without code changes, but old attendance and old deductions must remain tied to the policy that was active at that time.

This is similar to WFH or holiday policy behavior: if a rule changes from a certain date, it should apply going forward and should not unexpectedly change previous records.

### How It Will Work

Policy settings should be effective-dated.

Each policy version should store:

```text
name
effective_from
effective_to
on_time_until
warning_until
count_deduction_after
late_marks_per_deduction
deduction_days
deduction_cycle
default_shortage_handling
deduction_mode
created_by
created_at
updated_by
updated_at
change_reason
is_active
```

When admin changes a policy, the system should not overwrite history silently.

Instead, it should create a new policy version with a new `effective_from` date.

Example:

```text
Old policy:
effective_from: 2026-07-01
effective_to: 2026-07-31
On-time until: 10:15 AM
Warning until: 10:30 AM

New policy:
effective_from: 2026-08-01
effective_to: blank/current
On-time until: 10:10 AM
Warning until: 10:25 AM
```

Attendance records dated in July should use the July policy.

Attendance records dated on or after August 1 should use the new policy.

### Policy Snapshot Requirement

When a deduction is calculated or applied, the system should store a snapshot/reference of the policy used.

This prevents future policy changes from altering old deduction history.

Each deduction run should record:

```text
policy_version
policy_snapshot
period_start
period_end
calculated_at
applied_at
applied_by
```

### Admin Control Rule

Admin can configure all policy values, but the system should require:

```text
effective_from date
change reason
```

The `effective_from` date can be:

```text
past date
current date
future date
```

This gives admin full control to create policy versions for backdated corrections, immediate changes, or planned future changes.

When a policy is created with a past effective date, the system should adjust the policy timeline from that date, but it should not silently change already-applied deductions.

Past effective date behavior should be:

```text
1. Create or update the policy timeline from the selected effective date.
2. Show impacted attendance/deduction periods if records already exist.
3. Require admin confirmation before recalculating any existing pending deduction previews.
4. Never modify already-applied deductions automatically.
5. If already-applied deductions need correction, create a separate adjustment/reversal flow with audit logging.
```

Future effective date behavior should be:

```text
1. Save the future policy version.
2. Keep current policy active until the future date.
3. Automatically use the future policy for attendance dates on or after effective_from.
```

Current date behavior should be:

```text
1. Close the previous active policy as of the day before the new effective_from date.
2. Use the new policy from effective_from onward.
```

This keeps policy changes auditable and prevents accidental silent changes to old deduction history.

Retroactive recalculation should not happen automatically. If ever needed, it should be a separate admin action with clear confirmation and audit logging.
## Decision 11: Employee Visibility, Notifications, And Dedicated Page

Employees should have a dedicated page to view their attendance, late marks, deductions, and correction/exception requests.

### What We Will Build

Employee portal should include a dedicated attendance/late-coming page.

Employees should be able to see:

```text
warning-only late records
counted late marks
allowed/excused late records
deduction preview before applied
final applied deduction
notification history/status
correction/exception request status
```

Employees should also be able to request correction or exception from their portal.

### Why This Is Needed

Late-coming deduction affects leave balance and possibly payroll, so employees need transparency.

A dedicated page reduces confusion and HR back-and-forth because employees can see:

- which days were warnings
- which days counted for deduction
- which late records were excused
- how deductions were calculated
- whether HR/admin has approved or rejected a correction request

### How It Will Work

The employee page should include filters such as:

```text
month
custom date range
status
```

Each attendance row should show:

```text
date
check-in time
check-out time
system status
final status
source
policy used
remarks
```

Late status examples:

```text
On time
Warning only
Counted for deduction
Allowed / Excused
Pending review
Invalid / Needs correction
```

Deduction preview section should show pending deductions that are calculated but not yet applied:

```text
period
counted late marks
deduction days
expected deduction split
status
```

Final applied deduction section should show completed deductions:

```text
period
late marks counted
earned leave deducted
sick leave deducted
unpaid/LOP amount
negative balance amount if allowed
applied by
applied at
```

### Correction / Exception Request Flow

Employee should be able to submit a request for a late record.

Request fields should include:

```text
attendance record
request type: correction / exception
reason
remarks
supporting attachment optional
submitted_at
status
reviewed_by
reviewed_at
review_remarks
```

Request statuses:

```text
Pending
Approved
Rejected
Cancelled
```

If approved, HR/admin can update the attendance record final status, such as changing a counted late mark to:

```text
Allowed / Excused
```

If rejected, the attendance record remains counted according to policy.

### Notifications

Employees should receive notifications when:

```text
new warning-only late record is recorded
new counted late mark is recorded
deduction preview is generated
deduction is applied
late record is allowed/excused
correction/exception request is approved
correction/exception request is rejected
```

Notifications should use the existing project notification system where possible.
### Employee Personal Attendance Report

Employees should also have a personal attendance report page/view.

This should be separate from HR/admin reports and should show only the logged-in employee's own data.

Employee personal report should include:

```text
attendance records
warning-only late records
counted late marks
allowed/excused late records
pending correction/exception requests
approved/rejected correction/exception requests
deduction previews for that employee
final applied deductions for that employee
```

The employee should be able to filter their own report by:

```text
month
custom date range
status
```

The employee report should show clear per-period summaries, such as:

```text
total working attendance records
warning-only count
counted late mark count
allowed/excused count
deduction days pending
deduction days applied
earned leave deducted
sick leave deducted
unpaid/LOP amount
```

Privacy rule:

```text
Employee can only see their own attendance, late marks, requests, and deductions.
HR/admin can see all employees based on permissions.
```
## Decision 16: Configurable Email Notifications

Attendance and late-coming notifications should be sent by email according to admin configuration.

### What We Will Build

Admin should be able to configure which attendance events send email notifications.

Email notification events may include:

```text
warning-only late record created
counted late mark created
late record marked allowed/excused
deduction preview generated
deduction applied
correction/exception request submitted
correction/exception request approved
correction/exception request rejected
attendance import completed
attendance import has errors
automatic deduction run completed
automatic deduction run has records needing review
```

Recipients should be configurable by event where useful:

```text
employee
HR
admin
custom email list
```

### Why This Is Needed

Different organizations want different notification levels.

Some may want employees emailed for every warning. Others may only want emails when deductions are applied.

Admin configuration prevents hard-coded notification behavior.

### How It Will Work

Admin should have email notification settings for attendance/late-coming.

Suggested settings:

```text
enable email notifications: Yes / No
send employee warning emails: Yes / No
send employee counted late emails: Yes / No
send deduction preview emails: Yes / No
send deduction applied emails: Yes / No
send correction request status emails: Yes / No
send import summary emails to HR/admin: Yes / No
send automatic run summary emails to HR/admin: Yes / No
```

Employee emails should use the employee email stored in the system.

HR/admin emails should use existing configured recipients or an attendance-specific configured recipient list.

Email sending should use the existing project email system where possible.

Each sent email should be logged with:

```text
recipient
subject/event
delivery status
sent_at
related attendance record or deduction run
error if failed
```

### Important Rule

Email notification should not replace in-app notification.

Where possible, important events should create both:

```text
in-app notification
email notification if enabled by admin
```
## Decision 17: Leave Record Visibility For Late Deductions

Late-coming deductions must appear in leave records because they affect leave balance.

### What We Will Build

When every 3 counted late marks create a 0.5 day deduction, the deduction should be visible in the employee's leave record/history.

The leave record should clearly explain in the existing reason/detail field that it was created from attendance late-coming deduction, not from a normal employee leave request.

Example leave history entry using existing fields:

```text
Type: Earned Leave / Sick Leave / Unpaid-LOP
Days: 0.5
Reason: Late Coming Deduction - 3 counted late marks for period 2026-07-01 to 2026-07-31. Applied by HR/Admin/System on date-time.
Status: Applied
```

The exact text can include policy, period, late mark count, deduction split, and deduction run reference if available.

### Why This Is Needed

Employees and HR/admin must be able to understand why leave balance changed.

If leave is deducted but does not appear in leave records, the balance will look confusing and difficult to audit.

### How It Will Work

The attendance deduction system should create or link to leave-balance adjustment records when deductions are applied.

The record should include:

```text
attendance deduction run
employee
period_start
period_end
counted_late_marks
deduction_days
earned_leave_deducted
sick_leave_deducted
unpaid_lop_amount
negative_balance_amount
source: late_coming_deduction
policy_version
```

The existing leave history/leave balance views should show these deductions through the existing record structure where possible.

The reason/detail field should make the entry clearly distinguishable from normal leave applications.

### Important Rule

Late-coming deductions should not pretend to be employee-submitted leave requests.

They should be shown using the existing leave record structure where possible, with the reason/detail field clearly stating that the deduction was caused by attendance late-coming policy.
## Decision 18: Default `my_leave` Approved Display For Late Deductions

Late-coming deduction entries should appear in the employee `my_leave` Approved section using the existing table structure by default.

This display plan is the default for now and can be reviewed again during UI implementation.

### What We Will Build By Default

Late deduction records should appear under:

```text
My Leave -> Approved Leaves
```

They should use the existing approved table columns:

```text
Type
Schedule
Days
Applied
Approved
Approved By
Reason
```

### Column Meaning For Late Deductions

For normal leave, the schedule column means the leave dates.

For late-coming deductions, the schedule column should mean the deduction calculation period.

Examples:

```text
Weekly cycle: week start date -> week end date
Monthly cycle: month start date -> month end date
Custom cycle: selected from date -> selected to date
```

Example schedule values:

```text
Weekly: Jul 06, 2026 -> Jul 12, 2026
Monthly: Jul 01, 2026 -> Jul 31, 2026
Custom: Jul 10, 2026 -> Jul 20, 2026
```

Column mapping:

```text
Type:
Earned / Sick / Unpaid

Schedule:
Deduction calculation period, such as Jul 01, 2026 -> Jul 31, 2026

Days:
Deducted leave amount, such as 0.5 day

Applied:
When the deduction record was created/generated

Approved:
When HR/admin/system finally applied the deduction

Approved By:
HR/admin name, or System if auto-applied

Reason:
Full late-coming deduction detail
```

Example row:

```text
Type: Earned
Schedule: Jul 01, 2026 -> Jul 31, 2026
Days: 0.5
Applied: Jul 31, 2026 06:00 PM
Approved: Aug 01, 2026 10:00 AM
Approved By: HR Admin
Reason: Late Coming Deduction - 3 counted late marks in Jul 2026. Deducted 0.5 day from Earned Leave. Policy: every 3 late marks = 0.5 day.
```

### Split Deduction Display

If a deduction is split across leave types, show separate approved rows.

Example:

```text
Earned | Jul 01, 2026 -> Jul 31, 2026 | 0.25 day | Late deduction split
Sick   | Jul 01, 2026 -> Jul 31, 2026 | 0.25 day | Late deduction split
```

### Unpaid/LOP Display

If shortage becomes Unpaid/LOP, show it as an Unpaid approved entry.

Example:

```text
Unpaid | Jul 01, 2026 -> Jul 31, 2026 | 0.5 day | Late deduction shortage converted to Unpaid/LOP
```

### Review Later

This is the default display plan. During implementation, the UI can be reviewed to decide whether to add a small label such as:

```text
Attendance Deduction
```

The first implementation should avoid changing the `my_leave` table columns unless needed.
## Decision 12: HR/Admin Unified Tabbed Attendance Management Page

HR/admin should manage the attendance and late-coming system from one dedicated page with grouped tabs.

### What We Will Build

Instead of many separate pages, HR/admin should have one main page:

```text
Attendance Management
```

This page should contain grouped tabs for:

```text
Attendance Import
Manual Attendance Entry
Attendance Records
Late Review / Exceptions
Deduction Preview & Apply
Late Policy Settings
Employee Correction Requests
Deduction Run History / Logs
```

### Why This Is Needed

This keeps the workflow in one place and makes the feature easier for HR/admin to operate.

It should feel similar to the existing `my_leave` style where records can be filtered by status such as pending, approved, and rejected.

For attendance, tab and status filters should help HR/admin quickly move between import, review, exception, deduction, and history tasks.

### How It Will Work

The page should use top-level grouped tabs.

Suggested tab structure:

```text
1. Import
   - CSV/Excel upload
   - import preview
   - unmatched rows
   - validation errors

2. Manual Entry
   - add attendance for one employee/date
   - edit/correct existing attendance

3. Records
   - all attendance records
   - filters by employee, date range, source, status

4. Late Review
   - warning-only records
   - counted late marks
   - allowed/excused records
   - pending review records
   - mark selected late record as allowed/excused

5. Deductions
   - generate preview
   - weekly/monthly/custom range selection
   - apply deductions
   - shortage handling choices

6. Policy Settings
   - effective-dated policy settings
   - future/past/current effective date changes
   - policy version history

7. Requests
   - employee correction requests
   - employee exception requests
   - approve/reject with remarks

8. Logs
   - deduction run history
   - import history
   - automatic run logs
   - skipped records/errors
```

Inside relevant tabs, status filters should work like the leave pages.

Examples:

```text
Pending
Approved
Rejected
Allowed / Excused
Needs Review
Applied
Skipped
Invalid
```

The page should keep state through query parameters where useful, for example:

```text
?tab=late-review&status=pending&month=2026-07
```

This will make sharing, refreshing, and returning to the same filtered view easier.
## Decision 13: Attendance Import File Columns And Template

CSV/Excel upload should support a standard attendance import template.

### What We Will Build

The attendance upload template should support these columns:

```text
employee_code
email
employee_name
phone_number
biometric_device_id
date
check_in_time
check_out_time
remarks
```

The system should provide a downloadable sample template for HR/admin.

### Why This Is Needed

A standard template reduces import mistakes and makes manual CSV/Excel upload predictable.

The template includes multiple employee identifiers because attendance files may come from HR, manual records, or biometric export formats.

### How It Will Work

Required fields:

```text
date
check_in_time
at least one employee identifier
```

Employee identifiers can be any of:

```text
employee_code
email
employee_name
phone_number
biometric_device_id
```

Optional fields:

```text
check_out_time
remarks
```

The import parser should match employees using the decided priority:

```text
1. Employee Code / Employee ID
2. Biometric Device ID
3. Email
4. Phone Number
5. Employee Name
```

The import screen should show a preview before saving records.

Preview should include:

```text
matched employee
attendance date
check-in time
check-out time
system status
warnings
errors
```

Rows with errors should not be silently imported.

Error examples:

```text
missing date
missing check_in_time
no employee identifier
unmatched employee
ambiguous employee match
invalid date format
invalid time format
duplicate row conflict
```

Accepted formats should be flexible where possible:

```text
Date: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY
Time: HH:MM, HH:MM AM/PM
```

The final implementation should document exact accepted formats in the upload screen.
## Decision 14: Duplicate Attendance Handling

Duplicate attendance should be handled with total HR/admin control, but the default behavior should be safe.

### What We Will Build

If attendance already exists for the same employee and date, the import/manual entry flow should support all these actions:

```text
Skip duplicate
Overwrite existing record
Update only empty fields
Keep both as conflict for review
Ask HR/admin during import
```

Default behavior:

```text
Ask HR/admin during import
```

Recommended safe action when HR/admin does not choose explicitly:

```text
Keep both as conflict for review
```

### Why This Is Needed

Attendance data can arrive from multiple places: manual entry, CSV/Excel upload, and future biometric sync.

A duplicate does not always mean the new row is wrong. It may be:

- a correction
- a biometric re-sync
- a second upload from HR
- a manual fix
- a conflicting record that needs review

Because attendance affects leave deduction, the system should not silently overwrite old data.

### How It Will Work

During import preview, duplicate rows should be clearly marked.

For each duplicate row, HR/admin should see:

```text
existing attendance record
new imported row
changed fields
source of existing record
source of new row
previous status
new calculated status
```

HR/admin can choose an action per duplicate row or apply one action to all duplicates in the import batch.

Available actions:

```text
Skip duplicate:
Keep the existing attendance record unchanged and ignore the new row.

Overwrite existing record:
Replace existing attendance values with the new imported/manual values.

Update only empty fields:
Fill missing values only, such as check_out_time or remarks, without changing existing non-empty values.

Keep both as conflict for review:
Do not finalize the duplicate. Mark it as a conflict that HR/admin must resolve later.

Ask HR/admin during import:
Show duplicates in preview and require HR/admin choice before final save.
```

### Audit Requirement

Every duplicate decision should be audited.

Audit details should include:

```text
employee
date
old values
new values
action selected
selected_by
selected_at
reason/remarks
import batch
source
```

### Deduction Safety Rule

Attendance records with unresolved duplicate conflicts should not be used for automatic deduction.

They should appear as:

```text
Needs Review
```

Only resolved/final attendance records should be used by the late-coming deduction engine.
## Decision 15: HR Report Integration

Attendance, late marks, exceptions, and deductions should have a separate dedicated HR attendance report page.

### What We Will Build

A new dedicated HR attendance report page should be built separately from the leave report page, but it should follow the same style and workflow pattern as the already implemented leave report page.

Reports should include:

```text
attendance records report
warning-only late records report
counted late marks report
allowed/excused late records report
employee correction/exception request report
deduction preview report
final applied deduction report
unpaid/LOP shortage report
negative balance report if allowed
deduction run history report
import batch/error report
```

### Why This Is Needed

HR needs a separate reporting place to review attendance and late-coming impact without mixing it into leave reports.

Late-coming deduction affects leave balance and can affect payroll through Unpaid/LOP, so it should be visible in its own attendance report instead of only inside the attendance management page.

This helps HR answer questions such as:

- who came late in a selected period
- which late records were only warnings
- which late records counted for deduction
- which late records were allowed/excused
- who approved exceptions
- which employees had leave deducted
- which employees had Unpaid/LOP due to shortage
- which imports had errors or unmatched employees

### How It Will Work

The dedicated HR attendance report page should add attendance/late-coming filters and report tabs/sections.

Suggested filters:

```text
employee
department
month
custom date range
attendance status
late status
deduction status
source: manual / file_upload / biometric
policy version
```

Report rows should show enough detail for audit:

```text
employee
date
check-in time
check-out time
source
system status
final status
exception reason
approved_by
policy used
deduction period
earned leave deducted
sick leave deducted
unpaid/LOP amount
negative balance amount
applied_by
applied_at
```

The dedicated HR attendance report should support export where the existing report system supports export.

Export formats should follow the current project pattern, such as CSV, Excel, or PDF if already available in the report page.

### Important Rule

The attendance management page is for operations.

The dedicated HR attendance report page is for analysis, audit, export, and management review.

This report page should be separate from the leave report page, but visually and functionally similar where useful.

Both should read from the same attendance and deduction records so data stays consistent.


## Decision 19: Employee-Specific Attendance Schedule And Flexibility Grants

Some employees may be granted different attendance timing by HR/admin. Their late coming should be calculated using their assigned employee-specific schedule or exemption, not only the global office policy.

### What We Will Build

HR/admin should be able to configure employee-specific attendance rules.

Supported grant types:

```text
Custom arrival/departure timing
Flexible arrival window
Extended grace time
No late deduction / exempt from late counting
Temporary schedule override
Permanent schedule override
Specific date override
Date-range override
Weekday-based override
```

Examples:

```text
Employee A can arrive until 11:00 AM, late only after 11:00 AM.
Employee B can come any time between 10:00 AM and 12:00 PM and must complete required work hours.
Employee C is exempt from late deduction from 2026-07-10 to 2026-07-20 because of official duty.
Employee D has a custom shift from 12:00 PM to 9:00 PM.
Employee E has no late deduction, but attendance is still recorded for reporting.
```

### Why This Is Needed

Some employees may have special approval due to:

```text
role requirements
client site work
field work
medical reasons
transport constraints
management approval
temporary project assignment
custom shift timing
partial remote/WFH arrangement
```

Without employee-specific rules, these employees would incorrectly appear late under the standard policy.

### How It Will Work

Employee-specific schedule/flexibility should override the global policy for the applicable employee and date.

Policy priority should be:

```text
1. Employee-specific date override
2. Employee-specific date-range override
3. Employee-specific weekday/recurring override
4. Employee-specific permanent override
5. Shift/roster policy
6. Department/location policy
7. Global attendance policy
```

If an employee has an active custom schedule, the late classification engine should use that schedule's timing.

If an employee has an active no-late-deduction exemption, attendance should still be recorded, but late marks should not count for deduction.

Possible final status:

```text
Covered / Excluded - Employee Flex Schedule
Covered / Excluded - Late Deduction Exempt
Counted Late - Employee Custom Schedule
Warning Only - Employee Custom Schedule
On Time - Employee Custom Schedule
```

### Required Fields

A future `EmployeeAttendanceSchedule` or similar model should support:

```text
employee
schedule_type
applies_from
applies_to
applies_weekdays
custom_start_time
custom_on_time_until
custom_warning_until
custom_count_deduction_after
custom_end_time
minimum_work_hours
is_late_deduction_exempt
requires_work_hours_completion
created_by
created_at
updated_by
updated_at
approved_by
approved_at
reason
remarks
is_active
```

Schedule type examples:

```text
custom_fixed_timing
flexible_arrival_window
extended_grace
late_deduction_exempt
field_work
custom_shift
temporary_override
```

### HR/Admin Control

Both HR and admin should be able to configure employee-specific timing if permitted by role settings.

Admin should have full control.

HR should be able to create and manage these grants if the company allows HR-level control.

High-risk changes should be audited and may later support maker-checker approval.

High-risk examples:

```text
permanent late deduction exemption
past-dated exemption
bulk exemption for many employees
custom timing that affects already-generated deduction previews
exemption after deduction has already been applied
```

### Effective Date Rules

Employee-specific schedule grants must support:

```text
past effective dates
current date effective changes
future effective dates
```

Rules:

```text
Future grants apply automatically from their start date.
Current grants apply from today/current selected date.
Past grants show impacted attendance/deduction records before recalculation.
Already-applied deductions must not change silently.
If an old applied deduction is affected, use adjustment/reversal flow.
```

### Deduction Engine Rule

The deduction engine should count a late mark only after resolving the employee's applicable schedule for that date.

Classification flow should become:

```text
1. Find employee/date attendance record.
2. Resolve employee-specific schedule/exemption for that date.
3. If no employee-specific rule exists, resolve shift/department/location/global policy.
4. Classify attendance using resolved timing.
5. If employee is late-deduction exempt, mark covered/excluded and do not count.
6. Store the resolved schedule/policy reference or snapshot.
```

### UI Requirement

HR/admin Attendance Management page should include controls for employee-specific schedules.

Possible locations:

```text
Policy Settings tab -> Employee Overrides section
Records tab -> employee schedule indicator
Late Review tab -> show active employee grant
Employee detail drawer -> attendance schedule history
```

The employee-specific schedule UI should allow:

```text
select employee
choose schedule/grant type
set effective date or date range
set custom timings
set no-late-deduction exemption if needed
add reason/remarks
view history
edit future/current grants
end/disable grant
```

### Employee Visibility

Employee should be able to see active schedule/grant information on their attendance page when appropriate.

Employee-visible examples:

```text
Your attendance timing: 11:00 AM arrival allowed until 2026-07-31.
Late deduction exempt for official duty from 2026-07-10 to 2026-07-20.
Custom shift: 12:00 PM to 9:00 PM.
```

If HR/admin wants to keep some internal remarks private, public employee text and internal HR remarks should be separate fields.

### Reporting Requirement

HR attendance report should include employee-specific schedule/exemption data.

Report fields:

```text
employee
schedule/grant type
effective period
custom timing
late deduction exempt yes/no
created_by
approved_by
reason
attendance records affected
deductions prevented
```

### Audit Requirement

Every employee-specific grant change must be audited.

Audit details:

```text
employee
old schedule values
new schedule values
effective date/range
created_by/updated_by
approved_by if applicable
reason
changed_at
impacted records count if past/current change
```

### Version Placement

Version 1 should include the data model foundation and basic manual configuration for employee-specific timing/exemption if feasible.

If UI is too large for the first implementation slice, the model and service resolver should still be designed so this can be added without rewriting classification.

Enterprise target:

```text
Employee-specific timing/exemption is a first-class attendance rule, not a one-off exception note.
```
## Planned Implementation Phases

### Version 1

Version 1 should include:

- manual attendance entry for one employee and one date
- CSV/Excel attendance upload
- parsed import preview
- validation errors for bad rows
- unmatched employee reporting
- saved attendance records with source tracking
- HR/admin ability to edit or correct attendance records

### Version 2

Version 2 should include:

- automatic biometric sync
- biometric device/API configuration
- scheduled import
- sync logs and failures
- fallback to file upload or manual correction when biometric fails

## Important Design Principle

Attendance record creation and late-coming deduction should be separated.

First, attendance data is collected and corrected.

Then, the late-coming engine calculates late marks and proposed deductions.

This separation allows HR/admin to fix attendance before leave balances are affected.


## Professional Attendance System Review: Missing Or Pending Areas

This section records items found during a careful review against common professional attendance systems.

These items are accepted requirements. They should be implemented in controlled phases so the system remains stable and auditable.


### Accepted Requirement Summary

All professional review items are accepted into the implementation plan:

```text
missing punch handling
full-day absence handling
early leaving / short working hours
approved leave/WFH/holiday/weekend exclusion
payroll/attendance period lock
reversal and adjustment flow
permission matrix
import idempotency and duplicate file safety
decimal precision for 0.25/0.5 deductions
notification digest options
attachment security for correction requests
biometric future-ready fields
dashboard summary widgets
version 1 scope control
```

### Required Phasing

These requirements should be implemented in phases.

Version 1 must include the parts needed for safe manual operation:

```text
missing punch handling
approved leave/WFH/holiday/weekend exclusion
permission matrix
import idempotency and duplicate file safety
decimal precision
attachment security basics
biometric future-ready fields in data model
basic dashboard summary widgets
manual deduction review/apply
basic reversal/adjustment foundation
```

Version 2+ must complete the broader automation and advanced operations:

```text
full-day absence handling
early leaving / short working hours
payroll/attendance period lock
full reversal and adjustment workflow
notification digest options
automatic biometric sync
advanced dashboard widgets
payroll/export-oriented reports if needed
```

Even if a requirement is phased into Version 2, Version 1 data models should avoid blocking it later.
### 1. Missing Punch Handling

Professional attendance systems usually handle missing or incomplete punches separately from late coming.

Possible cases:

```text
missing check-in
missing check-out
both check-in and check-out missing
multiple punches in one day
invalid time sequence, such as check-out before check-in
```

Default behavior:

```text
Mark as Invalid / Needs correction.
Do not use for automatic late deduction until HR/admin resolves it.
```

### 2. Full-Day Absence Handling

The current plan focuses on late coming, but attendance systems often also track absence.

Possible cases:

```text
no attendance record for a working day
employee absent without approved leave
employee absent with approved leave
employee absent on WFH day
employee absent on weekend/holiday
```

Default behavior:

```text
Do not auto-deduct for absence in Version 1 unless explicitly configured.
Show absence as Needs Review for HR/admin.
```

### 3. Early Leaving / Short Working Hours

Professional systems often track early leaving or insufficient working hours separately from late coming.

Possible future rules:

```text
left before office end time
worked less than required daily hours
half-day by attendance shortage
shortfall minutes report
```

Default behavior:

```text
Keep out of Version 1 unless required now.
Design attendance records so this can be added later.
```

### 4. Approved Leave, WFH, Holiday, And Weekend Exclusion

The plan already mentions leave/WFH conflicts for clean records, but the implementation should make this explicit.

Late deduction should not count attendance records when the date is covered by:

```text
approved full-day leave
approved half-day/short leave where timing explains late arrival
approved WFH
company holiday
public holiday
weekend/non-working day
```

Required behavior:

```text
Mark as Covered / Excluded, not Counted for deduction.
Show reason in HR/admin review and employee page.
```

### 5. Payroll/Attendance Period Lock

Professional systems usually lock closed periods so old data does not change payroll or leave history accidentally.

Possible controls:

```text
lock attendance period
lock deduction run
unlock with admin permission only
require reason for unlock
log who unlocked and when
```

Default behavior:

```text
After deductions are applied for a period, mark the run as locked.
Corrections should use adjustment/reversal flow instead of silently editing old results.
```

### 6. Reversal And Adjustment Flow

The plan mentions separate adjustment/reversal for old applied deductions, but this needs to become a real workflow.

Possible actions:

```text
reverse applied deduction
restore leave balance
convert unpaid/LOP back to paid leave
apply additional deduction after correction
attach reason and approval
```

Default behavior:

```text
Do not edit applied deduction directly.
Create an audited adjustment record.
```

### 7. Permission Matrix

The plan needs exact permissions for each role.

Required permission areas:

```text
who can import attendance
who can manually edit attendance
who can approve exceptions
who can change policy settings
who can run deductions
who can enable automatic deduction
who can reverse applied deductions
who can view reports
who can export reports
```

Default behavior:

```text
Admin controls policy, automation, reversals, and global settings.
HR manages imports, manual corrections, exceptions, reviews, and reports.
Employee views own records and submits correction/exception requests.
```

### 8. Import Idempotency And Batch Safety

Professional import systems prevent the same file or same rows from being processed twice accidentally.

Required fields/behavior:

```text
import batch id
file name
file hash
uploaded_by
uploaded_at
row hash
row number
import status
```

Default behavior:

```text
Warn HR/admin if the same file appears to be uploaded again.
Do not duplicate already-finalized rows silently.
```

### 9. Rounding And Decimal Precision

Because deductions can be 0.25 or 0.5 day, the system should define precision clearly.

Default behavior:

```text
Store leave deduction values as Decimal, not float.
Use 2 decimal places for day values.
```

### 10. Notification Timing And Digest Options

The plan includes configurable email notifications, but professional systems often support immediate vs digest behavior.

Supported options:

```text
send immediately
send daily digest
send weekly digest
send only when deduction is applied
```

Default behavior:

```text
Immediate for deduction applied and request decision.
Optional digest for warning-only and counted late marks.
```

### 11. Data Retention And Attachment Handling

Correction/exception requests may include attachments.

Required controls:

```text
allowed file types
max file size
who can view attachments
retention period
secure storage path
```

Default behavior:

```text
Use the project's existing media/security pattern.
Restrict attachments to the employee, HR/admin, and reviewers.
```

### 12. Biometric Future Readiness

Biometric sync is planned for Version 2, but Version 1 should reserve enough structure.

Required future-ready fields:

```text
biometric_device_id
external_attendance_id
external_sync_batch
raw_payload/reference
sync_status
sync_error
```

Default behavior:

```text
Version 1 stores biometric_device_id and source fields.
Version 2 adds actual device/API sync.
```

### 13. Dashboard Summary Widgets

Professional systems usually show summary widgets for HR/admin and employees.

Required/optional widgets:

```text
late marks this month
warning-only count
pending exception requests
deduction pending approval
deduction applied this cycle
imports needing review
```

Default behavior:

```text
Include basic summary cards on attendance management and employee attendance pages.
Advanced analytics can wait.
```

### 14. Version 1 Scope Control

The plan is now broad. All listed areas are required, but they should be phased carefully so implementation remains stable.

Version 1 required core:

```text
policy model with effective dates
attendance record model
manual entry
CSV/Excel import with preview
duplicate handling
late classification
HR/admin tabbed management page
exception approval
manual deduction preview and apply
leave record entry in Approved section reason field
employee attendance page
basic in-app/email notification
basic dedicated HR attendance report
```

Version 2+ required expansion:

```text
auto apply clean records
fully automatic scheduled runs
biometric sync
period locking and reversal workflow if not needed immediately
advanced digests
advanced dashboards
payroll export
```

## Detailed Implementation Blueprint

This section converts the planning decisions into a practical build blueprint. It explains what will be built, why it is needed, how it should work, and what is still pending before implementation starts.

### Implementation Status Rule

Planning decisions can be marked as `Done` in the planning checklist.

Actual implementation items must stay `Not started` until code, database migrations, UI, and verification are complete.

Implementation statuses should mean:

```text
Not started: no code has been implemented yet
In progress: code or templates are actively being changed
Implemented: code is written, but not fully verified
Verified: tested manually or through automated tests
Done: implemented, verified, and documented
```

### Core Data Model Areas To Build

The implementation will likely need these model groups. Exact names can change after inspecting the existing Django app patterns.

```text
AttendancePolicy
AttendanceRecord
AttendanceImportBatch
AttendanceImportRow
AttendanceDuplicateDecision
LateDeductionRun
LateDeductionEmployeeSummary
LateDeductionLeaveSplit
AttendanceCorrectionRequest
AttendanceAuditLog
AttendanceEmailLog
AttendancePeriodLock
AttendanceAdjustment
```

#### AttendancePolicy

Stores effective-dated policy versions.

Purpose:

```text
Keeps admin-configurable rules historically accurate.
Allows past, present, and future policy changes.
Prevents old records from silently changing when policy changes.
```

Important fields:

```text
effective_from
effective_to
on_time_until
warning_until
count_deduction_after
late_marks_per_deduction
deduction_days
deduction_cycle
default_shortage_handling
deduction_mode
change_reason
created_by
updated_by
```

#### AttendanceRecord

Stores final attendance for employee/date.

Purpose:

```text
One common record source for manual entry, file upload, and future biometric sync.
Used by late classification, reports, employee page, and deduction engine.
```

Important fields:

```text
employee
date
check_in_time
check_out_time
source
system_status
final_status
policy_version
remarks
created_by
updated_by
external_attendance_id
biometric_device_id
```

Statuses should support:

```text
On time
Warning only
Counted for deduction
Allowed / Excused
Covered / Excluded
Invalid / Needs correction
Conflict / Needs review
```

#### AttendanceImportBatch And AttendanceImportRow

Stores upload metadata and row-level parsing/validation results.

Purpose:

```text
Allows import preview, error review, idempotency, duplicate detection, and audit.
Prevents accidental double import.
```

Important fields:

```text
file_name
file_hash
uploaded_by
uploaded_at
status
row_number
row_hash
raw_data
parsed_data
matched_employee
row_status
errors
warnings
```

#### LateDeductionRun

Stores a deduction calculation/apply run for a weekly, monthly, or custom period.

Purpose:

```text
Keeps calculation period, policy snapshot, approval/apply state, and audit.
Supports manual review, auto apply clean records, and fully automatic modes.
```

Important fields:

```text
period_start
period_end
cycle_type
policy_version
policy_snapshot
mode
status
calculated_by
calculated_at
applied_by
applied_at
locked_at
```

#### LateDeductionEmployeeSummary

Stores per-employee deduction result inside a run.

Purpose:

```text
Shows counted late marks, warning count, allowed count, deduction amount, and final action.
Feeds employee page, HR report, and leave record creation.
```

Important fields:

```text
employee
run
counted_late_marks
warning_count
allowed_count
deduction_days
earned_leave_deducted
sick_leave_deducted
unpaid_lop_amount
negative_balance_amount
shortage_handling
status
```

#### AttendanceCorrectionRequest

Stores employee-submitted correction/exception requests.

Purpose:

```text
Lets employee request correction or allowance from their portal.
Allows HR/admin approval or rejection with audit.
```

Important fields:

```text
attendance_record
employee
request_type
reason
remarks
attachment
status
submitted_at
reviewed_by
reviewed_at
review_remarks
```

#### AttendanceAdjustment

Stores reversals or later corrections after deduction is already applied.

Purpose:

```text
Prevents editing old applied deductions silently.
Creates auditable reversal or adjustment records.
```

Important fields:

```text
original_deduction_run
employee
adjustment_type
adjustment_days
leave_type
reason
created_by
approved_by
applied_at
```

### Core Services To Build

The implementation should keep business logic out of large views where possible.

Suggested services:

```text
attendance_policy_service.py
attendance_import_service.py
attendance_matching_service.py
attendance_classification_service.py
late_deduction_service.py
attendance_notification_service.py
attendance_report_service.py
attendance_adjustment_service.py
```

#### attendance_policy_service.py

Responsibilities:

```text
get policy for a date
create new effective-dated policy version
close previous policy ranges
show impacted records for past-dated changes
validate policy values
```

#### attendance_import_service.py

Responsibilities:

```text
parse CSV/Excel
validate rows
match employees
detect duplicates
create import preview
save finalized rows
store batch and row logs
```

#### attendance_classification_service.py

Responsibilities:

```text
classify attendance as on-time, warning, counted late, invalid, covered/excluded
apply policy based on attendance date
respect approved leave/WFH/holiday/weekend exclusions
```

#### late_deduction_service.py

Responsibilities:

```text
generate deduction preview
count eligible late marks
ignore allowed/excused and covered/excluded records
calculate earned/sick/unpaid split
apply approved deductions
create leave records using reason/detail field
create audit records
```

#### attendance_notification_service.py

Responsibilities:

```text
create in-app notifications
send email notifications if enabled
support immediate and digest behavior
log sent/failed emails
```

### Required Screens And Tabs

#### HR/Admin Attendance Management Page

One dedicated page with tabs:

```text
Import
Manual Entry
Records
Late Review
Deductions
Policy Settings
Requests
Logs
```

This page is for operations.

It should support query parameters like:

```text
?tab=late-review&status=pending&month=2026-07
```

#### Employee Attendance Page

Dedicated employee page for personal attendance, late marks, deductions, and requests.

It should show only the logged-in employee's records.

Required sections:

```text
summary cards
attendance list
warning-only records
counted late marks
allowed/excused records
pending deduction previews
applied deductions
correction/exception requests
```

#### HR Attendance Report Page

Separate from the leave report page.

Purpose:

```text
analysis
audit
export
management review
```

Should include filters and exports following the existing report style.

#### My Leave Approved Section

Late deductions should appear in `my_leave` Approved section using existing columns by default.

The reason/detail field should clearly explain:

```text
late deduction source
period
late mark count
policy used
deduction split
who/what applied it
```

### Required Permission Matrix

Exact permissions should be implemented before enabling the feature.

Suggested defaults:

| Action | Employee | HR | Admin |
|---|---:|---:|---:|
| View own attendance | Yes | Yes | Yes |
| Submit correction/exception request | Yes | Yes | Yes |
| View all attendance | No | Yes | Yes |
| Manual attendance entry | No | Yes | Yes |
| CSV/Excel import | No | Yes | Yes |
| Resolve duplicate/conflict | No | Yes | Yes |
| Mark allowed/excused | No | Yes | Yes |
| Approve/reject correction request | No | Yes | Yes |
| Generate deduction preview | No | Yes | Yes |
| Apply deductions | No | Yes | Yes |
| Change policy settings | No | No by default | Yes |
| Enable automation | No | No by default | Yes |
| Reverse applied deduction | No | No by default | Yes |
| View HR attendance reports | No | Yes | Yes |
| Export HR attendance reports | No | Yes | Yes |

### Required Exclusion Rules

Late deduction should not count dates covered by:

```text
approved full-day leave
approved short/half leave that explains the late time
approved WFH
company holiday
public holiday
weekend/non-working day
unresolved invalid attendance
unresolved duplicate conflict
allowed/excused late record
```

These records should be visible with a clear reason, such as:

```text
Covered / Excluded - Approved Leave
Covered / Excluded - WFH
Covered / Excluded - Holiday
Conflict / Needs Review
```

### Required Import Safety Rules

Imports must support:

```text
file hash duplicate detection
row hash duplicate detection
preview before save
row-level validation
row-level errors and warnings
unmatched employee handling
ambiguous employee handling
duplicate employee/date handling
per-row or bulk duplicate decision
audit for every overwrite/update/skip/conflict
```

### Required Precision Rules

Deductions must use Decimal values, not float.

Required precision:

```text
2 decimal places for leave day values
support 0.25, 0.50, 1.00 and similar values
```

### Required Missing Punch Behavior

Default handling:

```text
missing check-in -> Invalid / Needs correction
missing check-out -> Needs review, but late check-in can still be classified if check-in exists
both missing -> Invalid / Needs correction
check-out before check-in -> Invalid / Needs correction
multiple punches -> Needs review or use configured first-in/last-out rule later
```

Version 1 should be conservative:

```text
Invalid and conflict records do not participate in automatic deduction.
```

### Required Absence And Early Leaving Behavior

These are accepted requirements, but they can be implemented after the late-coming core.

Full-day absence should eventually handle:

```text
no attendance on working day
no approved leave
no approved WFH
not holiday/weekend
```

Early leaving / short working hours should eventually handle:

```text
left before office end
worked less than required hours
shortfall report
optional leave/LOP deduction policy
```

Version 1 should store attendance data in a way that does not block these future rules.

### Required Period Lock And Adjustment Behavior

After a deduction run is applied, the period/run should be lockable.

Locked records should not be silently edited.

Corrections after lock should use:

```text
reversal
adjustment
additional deduction
leave balance restore
unpaid/LOP correction
```

All adjustments need reason and audit.

### Required Notification Behavior

Notification system should support:

```text
in-app notification
email if enabled
immediate notification
daily digest
weekly digest
```

Default suggestion:

```text
immediate for deduction applied and request decision
digest optional for warning-only and counted late marks
```

### Required Attachment Security

Correction/exception attachments should define:

```text
allowed file types
max file size
secure media path
who can view
retention behavior
```

Default access:

```text
employee owner
HR/admin reviewers
admin
```

### Required Dashboard Widgets

Basic widgets should appear on attendance pages.

HR/Admin widgets:

```text
imports needing review
pending correction requests
counted late marks this cycle
deductions pending apply
applied deductions this cycle
records invalid/needs correction
```

Employee widgets:

```text
warning-only this month
counted late marks this month
allowed/excused this month
pending requests
pending deduction days
applied deduction days
```

### What Is Still Left Before Coding

Before implementation starts, these items should be finalized:

```text
1. Confirm final Version 1 scope.
2. Inspect existing Profile/User fields for employee_code, phone_number, biometric_device_id.
3. Inspect existing notification/email services for reuse.
4. Inspect existing report/export services for attendance report page reuse.
5. Decide whether Excel upload needs a new dependency or CSV-only first.
6. Decide exact permission mapping between HR/admin roles in this project.
7. Decide whether full-day absence and early leaving are Version 1 or Version 2.
8. Decide if period lock/reversal is full Version 1 or foundation only.
9. Decide exact attachment file limits.
10. Decide whether notification digest is Version 1 or Version 2.
```

### Recommended Build Order

Recommended implementation order:

```text
1. Inspect existing models, views, reports, notifications, and leave balance logic.
2. Add/adjust model fields needed for employee matching.
3. Build attendance policy models and default seed behavior.
4. Build attendance record/import/deduction/request models.
5. Build core services for policy lookup, classification, import preview, and deduction preview.
6. Build HR/admin Attendance Management page shell with tabs.
7. Build manual attendance entry.
8. Build CSV/Excel import preview and finalize flow.
9. Build late review and allowed/excused flow.
10. Build deduction preview and manual apply.
11. Create approved leave records with late deduction reason details.
12. Build employee attendance page and correction request flow.
13. Add configurable notifications and email logging.
14. Build dedicated HR attendance report page.
15. Add tests for policy, classification, import, deduction, exclusions, and leave record creation.
16. Update project docs and mark completed items in this plan.
```

## Complete Conversation Decision Checklist

This checklist captures every decision agreed in the planning conversation. It is the quick verification list before implementation starts.

### Attendance Input And Control

- Attendance will support manual single-employee entry.
- Attendance will support CSV/Excel upload.
- Attendance will be future-ready for automatic biometric sync.
- All sources will feed the same attendance record system.
- Each record will track source: manual, file upload, or biometric.
- HR/admin must retain full control when biometric fails or imported data is wrong.

### Employee Matching

- Attendance can match employee by Employee Code / Employee ID.
- Attendance can match employee by Email.
- Attendance can match employee by Employee Name.
- Attendance can match employee by Phone Number.
- Attendance can match employee by Biometric Device ID.
- Matching priority should be Employee Code, Biometric Device ID, Email, Phone Number, then Employee Name.
- Unmatched and ambiguous rows must go to HR/admin review, not silent guessing.

### Timing And Late Classification

- Default office start reference is 10:00 AM.
- On-time until 10:15 AM.
- 10:16 AM to 10:30 AM is warning-only.
- Warning-only records do not count for deduction.
- 10:31 AM or later is counted late for deduction.
- Timing values must be admin configurable.
- Timing policy changes must be effective-dated.

### Late Deduction Rule

- Every 3 deduction-counted late marks deduct 0.5 day.
- Deduction count repeats: 3 = 0.5, 6 = 1.0, 9 = 1.5.
- Warning-only records are excluded from this count.
- Allowed/excused records are excluded from this count.

### Leave Deduction Priority And Shortage

- Deduct Earned Leave first.
- If Earned Leave is not enough, deduct Sick Leave second.
- If Earned and Sick are not enough, remaining amount becomes Unpaid/LOP by default.
- HR/admin can override shortage handling to manual handling.
- HR/admin can override shortage handling to allow negative balance.
- Deduction amounts must use Decimal precision, not float.

### Deduction Cycle And Automation

- Deduction cycle must support Weekly.
- Deduction cycle must support Monthly.
- Deduction cycle must support Custom date range.
- Default deduction cycle is Monthly.
- Custom date range must be HR/admin triggered.
- Deduction mode must support Manual Review Only.
- Deduction mode must support Auto Apply Clean Records.
- Deduction mode must support Fully Automatic.
- Default deduction mode is Manual Review Only.
- Auto apply should only apply clean records and send risky records to review.
- Automatic runs must create audit logs.

### Admin Configurable Policy

- All late policy settings must be admin configurable.
- Default values must be set for first use.
- Policy must support effective dates in the past, present, or future.
- New policy changes should create policy versions, not overwrite history silently.
- Future-dated policies activate from their effective date.
- Past-dated policies show impacted records and must not silently change applied deductions.
- Applied deductions must keep policy snapshot/reference.
- Retroactive correction must use adjustment/reversal flow.

### HR/Admin Attendance Management UI

- HR/admin will have one dedicated Attendance Management page.
- The page will use grouped tabs like the existing leave status filtering style.
- Tabs: Import, Manual Entry, Records, Late Review, Deductions, Policy Settings, Requests, Logs.
- Tab/filter state should be kept in query parameters where useful.
- This page is for operations, not reports.

### Import Template And Duplicate Handling

- Upload columns: employee_code, email, employee_name, phone_number, biometric_device_id, date, check_in_time, check_out_time, remarks.
- Required fields: date, check_in_time, at least one employee identifier.
- check_out_time and remarks are optional.
- System should provide downloadable sample template.
- Import must show preview before saving.
- Bad rows must show row-level errors.
- Duplicate handling must support skip, overwrite, update empty fields, keep both as conflict, and ask HR/admin.
- Default duplicate behavior is ask HR/admin during import.
- Safe fallback is keep both as conflict for review.
- Unresolved conflicts must not be used for automatic deduction.
- Import idempotency and duplicate file safety are required.

### Exceptions, Corrections, And Attachments

- HR/admin can mark a counted late record as Allowed / Excused.
- Allowed/excused records do not count for deduction.
- Employee can request correction.
- Employee can request exception/allowance.
- Employee correction/exception requests can include optional attachment/proof.
- Attachment security, file types, size, access, and retention must be defined.
- HR/admin can approve or reject employee requests with remarks.

### Employee Visibility

- Employee gets a dedicated attendance/late-coming page.
- Employee gets a personal attendance report view.
- Employee can see warning-only late records.
- Employee can see counted late marks.
- Employee can see allowed/excused late records.
- Employee can see deduction previews before applied.
- Employee can see final applied deductions.
- Employee can see request status.
- Employee can only see their own records.

### Reports

- HR attendance report must be separate from leave report.
- Dedicated HR Attendance Report page should follow the style/pattern of the existing leave report page.
- HR report includes attendance records, warnings, counted late marks, allowed/excused records, requests, deduction previews, applied deductions, Unpaid/LOP, negative balances, deduction run history, and import errors.
- Employee personal report is per employee and separate from HR/admin reports.
- Attendance Management page is operational.
- Attendance Report page is for analysis, audit, export, and management review.

### Notifications And Email

- In-app notifications should be used where possible.
- Email notifications should be sent according to admin configuration.
- Admin can configure which attendance events send emails.
- Emails may go to employee, HR, admin, or custom configured recipients.
- Notification digest options are required: immediate, daily digest, weekly digest.
- Email sending must be logged.

### Leave Record And `my_leave` Display

- Late deductions must appear in leave records/history because leave balance changes.
- Do not change leave record structure unless needed.
- Use existing reason/detail field to explain late deduction.
- Late deduction entries should appear in My Leave -> Approved Leaves by default.
- Use existing Approved table columns: Type, Schedule, Days, Applied, Approved, Approved By, Reason.
- For late deductions, Schedule means deduction calculation period, not actual leave date.
- For split deduction across Earned and Sick, show separate approved rows by leave type.
- For Unpaid/LOP shortage, show Unpaid approved entry.
- This display is default and can be reviewed later during UI implementation.

### Professional Attendance Requirements Accepted

- Missing punch handling is required.
- Full-day absence handling is required.
- Early leaving / short working hours is required.
- Approved leave/WFH/holiday/weekend exclusion is required.
- Payroll/attendance period lock is required.
- Reversal and adjustment flow is required.
- Permission matrix is required.
- Import idempotency and duplicate file safety are required.
- Decimal precision is required.
- Notification digest options are required.
- Attachment security is required.
- Biometric future-ready fields are required.
- Dashboard summary widgets are required.
- Version 1 scope control is required.

### Version 1 And Version 2 Direction

- Version 1 should focus on safe manual operation and future-ready data structure.
- Version 1 should not block biometric, automation, absence, early leaving, period locks, or adjustments later.
- Version 2+ should complete biometric sync, broader automation, full period lock/reversal, advanced digest, advanced dashboard, absence, early leaving, and payroll/export-oriented workflows.

## Open Questions To Decide Next

The next discussion should decide implementation scope for Version 1.

Needed details:

- which parts must be built first
- which parts can wait for Version 2
- whether to start with database/models and admin UI
- testing and verification scope
- where dedicated HR attendance report page fits in Version 1




























## Developer Implementation Specification

This section is written for the implementation phase. It expands the plan into precise build requirements, expected fields, workflows, validations, UI behavior, test coverage, and acceptance criteria.

The purpose is simple: when implementation starts, the developer should not need to rediscover the business rules from chat history.

### Non-Negotiable Build Principles

The attendance feature must follow these principles:

```text
1. No silent balance changes.
2. No silent overwrite of attendance data.
3. No automatic deduction from invalid, ambiguous, duplicate-conflict, or pending-review records.
4. Every policy change must be effective-dated.
5. Every deduction run must store the policy snapshot used.
6. Every applied deduction must be traceable from attendance records to leave record/history.
7. Employee-visible data must be limited to the logged-in employee.
8. HR/admin reports must be separate from leave reports.
9. The system must work manually first, then support automation safely.
10. Future biometric sync must feed the same attendance records, not a separate system.
```

### Suggested Module/File Layout

Exact file names can change if the existing codebase has stronger local conventions, but the implementation should keep large business logic out of giant views where possible.

Suggested Python files:

```text
App/models.py
App/forms.py
App/urls.py
App/views.py
App/admin.py
App/services/attendance_policy_service.py
App/services/attendance_import_service.py
App/services/attendance_matching_service.py
App/services/attendance_classification_service.py
App/services/late_deduction_service.py
App/services/attendance_notification_service.py
App/services/attendance_report_service.py
App/services/attendance_adjustment_service.py
App/utils/attendance_dates.py
App/utils/attendance_csv.py
```

Suggested tests:

```text
App/tests/test_attendance_policy.py
App/tests/test_attendance_import.py
App/tests/test_attendance_classification.py
App/tests/test_late_deduction.py
App/tests/test_attendance_permissions.py
App/tests/test_attendance_views.py
```

Suggested templates and static files:

```text
templates/attendance_management.html
templates/attendance_employee.html
templates/attendance_report.html
templates/includes/attendance_import_preview_rows.html
templates/includes/attendance_record_rows.html
templates/includes/attendance_late_review_rows.html
templates/includes/attendance_deduction_rows.html
templates/includes/attendance_request_rows.html
static/css/attendance_management.css
static/css/attendance_employee.css
static/css/attendance_report.css
static/js/attendance_management.js
static/js/attendance_employee.js
static/js/attendance_report.js
```

If the project already has reusable styles/components, reuse them instead of inventing a separate design language.

### Model Specification

This is the expected model-level shape. During implementation, inspect existing `CustomUser`, `Profile`, `Leave`, `LeaveBalance`, notification, report, WFH, holiday, and audit models before finalizing exact field names.

#### Employee Matching Fields

Add only missing fields after inspecting existing `Profile` and user models.

Likely fields:

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| employee_code | CharField unique/nullable | No | Primary HR/manual matching key if available. |
| biometric_device_id | CharField unique/nullable | No | Future biometric matching key. |
| phone_number | CharField nullable | No | Use existing phone field if already present. |

Rules:

```text
Do not duplicate fields if existing Profile already has them.
If employee_code or biometric_device_id is added, make it indexed.
If uniqueness cannot be guaranteed immediately, start nullable and validate conflicts in matching service.
```

#### AttendancePolicy

Purpose: effective-dated policy versions.

| Field | Suggested Type | Required | Default | Notes |
|---|---|---:|---|---|
| name | CharField | Yes | Standard Policy | Human-readable policy name. |
| effective_from | DateField | Yes | Current date | Can be past, present, or future. |
| effective_to | DateField nullable | No | null | Auto-closed when a newer policy overlaps. |
| on_time_until | TimeField | Yes | 10:15 | On-time boundary. |
| warning_until | TimeField | Yes | 10:30 | Warning-only boundary. |
| count_deduction_after | TimeField | Yes | 10:30 | Check-in after this is counted late. |
| late_marks_per_deduction | PositiveIntegerField | Yes | 3 | Every X counted late marks. |
| deduction_days | DecimalField | Yes | 0.50 | Leave days per group. |
| deduction_cycle | CharField choices | Yes | monthly | weekly/monthly/custom. |
| weekly_run_day | CharField/Integer nullable | No | null | Needed for weekly automation. |
| monthly_run_day | PositiveInteger/null | No | null | Selected date or last day flag. |
| monthly_run_on_last_day | BooleanField | Yes | true | Useful for month-end. |
| default_shortage_handling | CharField choices | Yes | unpaid_lop | unpaid_lop/manual/negative_balance. |
| deduction_mode | CharField choices | Yes | manual_review | manual_review/auto_clean/fully_auto. |
| auto_run_enabled | BooleanField | Yes | false | Controls scheduled automation. |
| auto_run_time | TimeField nullable | No | null | Used if auto_run_enabled. |
| email_notifications_enabled | BooleanField | Yes | true | Master email toggle. |
| change_reason | TextField | Yes | none | Required for admin changes. |
| created_by | FK User nullable | No | null | Audit. |
| updated_by | FK User nullable | No | null | Audit. |
| created_at | DateTimeField | Yes | auto | Audit. |
| updated_at | DateTimeField | Yes | auto | Audit. |
| is_active | BooleanField | Yes | true | Current timeline row, not necessarily current date. |

Validation:

```text
on_time_until must be <= warning_until.
warning_until must be <= count_deduction_after or equal to it.
late_marks_per_deduction must be > 0.
deduction_days must be > 0.
effective_from is required.
change_reason is required for admin-created/edited policy versions.
Overlapping policy ranges should be resolved by service logic, not silent random selection.
```

Policy lookup:

```text
For an attendance date, choose policy where effective_from <= date and (effective_to is null or effective_to >= date).
If no policy exists, use/create default policy before classification.
If multiple policies match, treat as configuration error and require admin fix.
```

#### AttendanceRecord

Purpose: one final attendance record per employee/date after source-specific import/manual/biometric handling.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| employee | FK User | Yes | Employee this attendance belongs to. |
| date | DateField | Yes | Attendance date. |
| check_in_time | TimeField nullable | No | Missing means invalid/needs correction. |
| check_out_time | TimeField nullable | No | Missing checkout can still classify late if check-in exists. |
| source | CharField choices | Yes | manual/file_upload/biometric/system. |
| system_status | CharField choices | Yes | Auto classification before HR override. |
| final_status | CharField choices | Yes | Final status used by deduction engine. |
| policy_version | FK AttendancePolicy nullable | No | Policy used for classification. |
| policy_snapshot | JSONField/TextField nullable | No | Optional snapshot for historical display. |
| is_locked | BooleanField | Yes | True after period lock/applied run if needed. |
| is_duplicate_conflict | BooleanField | Yes | Conflict rows are excluded. |
| conflict_group_id | CharField nullable | No | Groups conflicting imports. |
| remarks | TextField blank | No | HR/admin/manual remarks. |
| exception_reason | TextField blank | No | Reason if allowed/excused. |
| exception_by | FK User nullable | No | HR/admin who allowed/excused. |
| exception_at | DateTimeField nullable | No | When allowed/excused. |
| created_by | FK User nullable | No | Audit. |
| updated_by | FK User nullable | No | Audit. |
| created_at | DateTimeField | Yes | Audit. |
| updated_at | DateTimeField | Yes | Audit. |
| external_attendance_id | CharField nullable | No | Future biometric/source id. |
| biometric_device_id | CharField nullable | No | Snapshot from import/source. |
| raw_source_reference | TextField/JSON nullable | No | Future raw import/biometric reference. |

Recommended unique rule:

```text
Unique final record per employee/date when is_duplicate_conflict = false.
```

If database conditional unique constraints are not convenient, enforce this in service logic.

Status choices:

```text
on_time
warning_only
counted_late
allowed_excused
covered_excluded
invalid_needs_correction
conflict_needs_review
pending_review
absence_needs_review
early_leave_needs_review
short_hours_needs_review
```

Important rule:

```text
Only final_status = counted_late participates in late deduction count.
```

#### AttendanceImportBatch

Purpose: upload/session-level tracking.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| source | CharField | Yes | file_upload/manual_bulk/biometric. |
| file | FileField nullable | No | Store uploaded file if project policy allows. |
| file_name | CharField | No | Original file name. |
| file_hash | CharField indexed | No | Detect duplicate upload. |
| status | CharField choices | Yes | uploaded/previewed/finalized/failed/cancelled. |
| uploaded_by | FK User | Yes | HR/admin. |
| uploaded_at | DateTimeField | Yes | Audit. |
| finalized_by | FK User nullable | No | HR/admin. |
| finalized_at | DateTimeField nullable | No | Audit. |
| total_rows | Integer | Yes | Count. |
| valid_rows | Integer | Yes | Count. |
| error_rows | Integer | Yes | Count. |
| warning_rows | Integer | Yes | Count. |
| duplicate_rows | Integer | Yes | Count. |
| unmatched_rows | Integer | Yes | Count. |
| notes | TextField blank | No | Import remarks. |

Batch statuses:

```text
uploaded
previewed
finalized
partially_finalized
failed
cancelled
```

#### AttendanceImportRow

Purpose: row-level preview and audit.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| batch | FK AttendanceImportBatch | Yes | Parent. |
| row_number | Integer | Yes | Original spreadsheet row. |
| row_hash | CharField indexed | No | Duplicate row safety. |
| raw_data | JSONField/TextField | Yes | Original row values. |
| parsed_data | JSONField/TextField | No | Parsed normalized values. |
| matched_employee | FK User nullable | No | If matched. |
| match_method | CharField nullable | No | employee_code/email/etc. |
| match_confidence | CharField | No | exact/ambiguous/unmatched. |
| row_status | CharField choices | Yes | valid/error/warning/duplicate/conflict. |
| errors | JSONField/TextField | No | Row errors. |
| warnings | JSONField/TextField | No | Row warnings. |
| duplicate_action | CharField nullable | No | skip/overwrite/update_empty/conflict. |
| created_attendance | FK AttendanceRecord nullable | No | Final record if saved. |

#### AttendanceDuplicateDecision

Purpose: audit each duplicate/conflict choice.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| employee | FK User | Yes | Employee. |
| date | DateField | Yes | Attendance date. |
| existing_record | FK AttendanceRecord nullable | No | Old record. |
| import_row | FK AttendanceImportRow nullable | No | New row. |
| action | CharField | Yes | skip/overwrite/update_empty/conflict. |
| old_values | JSONField/TextField | Yes | Before. |
| new_values | JSONField/TextField | Yes | Incoming. |
| reason | TextField blank | No | HR/admin remarks. |
| selected_by | FK User | Yes | HR/admin. |
| selected_at | DateTimeField | Yes | Audit. |

#### AttendanceCorrectionRequest

Purpose: employee correction/exception requests.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| employee | FK User | Yes | Request owner. |
| attendance_record | FK AttendanceRecord nullable | No | Related record. |
| request_type | CharField | Yes | correction/exception. |
| requested_check_in_time | TimeField nullable | No | For correction. |
| requested_check_out_time | TimeField nullable | No | For correction. |
| reason | TextField | Yes | Employee reason. |
| remarks | TextField blank | No | Extra details. |
| attachment | FileField nullable | No | Optional proof. |
| status | CharField | Yes | pending/approved/rejected/cancelled. |
| submitted_at | DateTimeField | Yes | Audit. |
| reviewed_by | FK User nullable | No | HR/admin. |
| reviewed_at | DateTimeField nullable | No | Audit. |
| review_remarks | TextField blank | No | HR/admin decision note. |

Validation:

```text
Employee can submit only for own attendance record.
Employee cannot edit approved/rejected request; they can cancel pending request if allowed.
HR/admin approval must update attendance record through service logic, not direct template code.
```

#### LateDeductionRun

Purpose: one deduction calculation/apply run.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| cycle_type | CharField | Yes | weekly/monthly/custom. |
| period_start | DateField | Yes | Start. |
| period_end | DateField | Yes | End. |
| policy_version | FK AttendancePolicy | Yes | Policy reference. |
| policy_snapshot | JSONField/TextField | Yes | Historical snapshot. |
| mode | CharField | Yes | manual_review/auto_clean/fully_auto. |
| status | CharField | Yes | draft/preview/generated/applied/locked/cancelled/failed. |
| generated_by | FK User nullable | No | HR/admin/system. |
| generated_at | DateTimeField | Yes | Audit. |
| applied_by | FK User nullable | No | HR/admin/system. |
| applied_at | DateTimeField nullable | No | Audit. |
| locked_by | FK User nullable | No | Admin/system. |
| locked_at | DateTimeField nullable | No | Period lock. |
| run_reference | CharField unique | Yes | Human-friendly id. |
| notes | TextField blank | No | Remarks. |

Run statuses:

```text
draft
preview_generated
partially_applied
applied
locked
cancelled
failed
```

#### LateDeductionEmployeeSummary

Purpose: per-employee result in a deduction run.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| run | FK LateDeductionRun | Yes | Parent. |
| employee | FK User | Yes | Employee. |
| counted_late_marks | Integer | Yes | Deduction-eligible count. |
| warning_count | Integer | Yes | Warning-only count. |
| allowed_excused_count | Integer | Yes | Excluded count. |
| invalid_count | Integer | Yes | Needs correction count. |
| deduction_days | DecimalField | Yes | Total calculated. |
| earned_leave_deducted | DecimalField | Yes | Split. |
| sick_leave_deducted | DecimalField | Yes | Split. |
| unpaid_lop_amount | DecimalField | Yes | Shortage default. |
| negative_balance_amount | DecimalField | Yes | If selected. |
| shortage_handling | CharField | Yes | unpaid_lop/manual/negative_balance. |
| status | CharField | Yes | pending_review/ready/applied/skipped/blocked. |
| block_reason | TextField blank | No | Why not apply. |

#### LateDeductionLeaveSplit

Purpose: link applied deduction summary to created leave records.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| summary | FK LateDeductionEmployeeSummary | Yes | Parent. |
| leave_type | CharField | Yes | Earned/Sick/Unpaid. |
| days | DecimalField | Yes | Amount. |
| leave_record | FK Leave nullable | No | Existing Leave model row if created. |
| reason_text | TextField | Yes | Reason copied into Leave.reason. |
| created_at | DateTimeField | Yes | Audit. |

#### AttendancePeriodLock

Purpose: lock closed periods.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| period_start | DateField | Yes | Start. |
| period_end | DateField | Yes | End. |
| cycle_type | CharField | Yes | weekly/monthly/custom. |
| locked_by | FK User | Yes | Admin/system. |
| locked_at | DateTimeField | Yes | Audit. |
| unlock_reason | TextField blank | No | If unlocked. |
| unlocked_by | FK User nullable | No | Admin. |
| unlocked_at | DateTimeField nullable | No | Audit. |
| is_locked | BooleanField | Yes | Current state. |

#### AttendanceAdjustment

Purpose: reverse/correct already-applied deductions.

| Field | Suggested Type | Required | Notes |
|---|---|---:|---|
| original_run | FK LateDeductionRun | Yes | Source run. |
| original_summary | FK LateDeductionEmployeeSummary | Yes | Source employee result. |
| employee | FK User | Yes | Employee. |
| adjustment_type | CharField | Yes | reverse/restore/additional_deduction/convert_lop. |
| leave_type | CharField nullable | No | Earned/Sick/Unpaid. |
| days | DecimalField | Yes | Amount. |
| reason | TextField | Yes | Required. |
| status | CharField | Yes | pending/applied/cancelled. |
| created_by | FK User | Yes | Admin. |
| approved_by | FK User nullable | No | Optional second approval. |
| applied_at | DateTimeField nullable | No | Audit. |

### Enum Definitions

Use code constants for these choices so strings do not spread randomly.

Attendance source:

```text
manual
file_upload
biometric
system
```

Attendance final status:

```text
on_time
warning_only
counted_late
allowed_excused
covered_excluded
invalid_needs_correction
conflict_needs_review
pending_review
absence_needs_review
early_leave_needs_review
short_hours_needs_review
```

Policy cycle:

```text
weekly
monthly
custom
```

Deduction mode:

```text
manual_review
auto_apply_clean
fully_automatic
```

Shortage handling:

```text
unpaid_lop
manual_handling
negative_balance
```

Correction request type:

```text
correction
exception
```

Correction request status:

```text
pending
approved
rejected
cancelled
```

Deduction summary status:

```text
pending_review
ready_to_apply
auto_applied
applied_manually
skipped
blocked
```

### State Transition Rules

#### AttendanceRecord Status Transitions

Allowed transitions:

```text
pending_review -> on_time
pending_review -> warning_only
pending_review -> counted_late
pending_review -> invalid_needs_correction
pending_review -> conflict_needs_review
counted_late -> allowed_excused
counted_late -> invalid_needs_correction
warning_only -> allowed_excused
invalid_needs_correction -> on_time/warning_only/counted_late after correction
conflict_needs_review -> resolved final status after HR/admin decision
```

Disallowed without adjustment flow:

```text
Changing a record used in an applied/locked deduction run.
Deleting a record used in an applied/locked deduction run.
Changing counted_late to allowed_excused after deduction is applied without reversal/adjustment.
```

#### DeductionRun State Transitions

Allowed transitions:

```text
draft -> preview_generated
preview_generated -> applied
preview_generated -> cancelled
applied -> locked
applied -> adjustment_required
failed -> preview_generated after retry
```

Rules:

```text
A run cannot be applied twice.
A run cannot include unresolved conflicts.
A locked run cannot be edited directly.
Corrections after lock must create adjustment records.
```

#### CorrectionRequest State Transitions

Allowed transitions:

```text
pending -> approved
pending -> rejected
pending -> cancelled
```

Rules:

```text
Only employee owner can cancel their own pending request.
Only HR/admin can approve/reject.
Approved request must apply through attendance service.
Rejected request should not alter attendance record.
```

### End-To-End Workflow Specifications

#### Workflow 1: First-Time Setup

```text
1. System checks if any AttendancePolicy exists.
2. If none exists, create default policy.
3. Default policy effective_from should be current date unless admin provides another date.
4. Default policy values:
   on_time_until = 10:15 AM
   warning_until = 10:30 AM
   count_deduction_after = 10:30 AM
   late_marks_per_deduction = 3
   deduction_days = 0.50
   deduction_cycle = monthly
   default_shortage_handling = unpaid_lop
   deduction_mode = manual_review
5. Default policy creation must be logged.
```

#### Workflow 2: Admin Changes Policy

```text
1. Admin opens Policy Settings tab.
2. Admin enters new values, effective_from date, and change reason.
3. System validates values.
4. System shows impact preview if effective_from is in the past.
5. Admin confirms.
6. System creates new policy version.
7. System closes or adjusts affected policy timeline records.
8. System does not modify applied deductions automatically.
9. System logs policy change.
```

Past effective date behavior:

```text
Show impacted attendance records.
Show impacted pending deduction previews.
Do not recalculate applied runs silently.
Offer separate recalculation only for pending/unapplied previews.
Require adjustment/reversal flow for applied deductions.
```

Future effective date behavior:

```text
Save future policy.
Current policy remains active for current dates.
Policy lookup uses future policy only for dates on/after effective_from.
```

#### Workflow 3: Manual Attendance Entry

```text
1. HR/admin opens Attendance Management -> Manual Entry.
2. HR/admin selects employee and date.
3. HR/admin enters check-in, optional check-out, remarks.
4. System checks employee/date existing record.
5. If duplicate exists, show duplicate handling options.
6. System applies policy for that attendance date.
7. System classifies status.
8. HR/admin saves.
9. System writes AttendanceRecord and audit log.
10. If configured, notification is sent.
```

Manual entry validation:

```text
Employee required.
Date required.
Check-in required unless explicitly marking invalid/missing punch.
Check-out optional.
Check-out cannot be before check-in.
Locked periods cannot be edited without unlock/adjustment permission.
```

#### Workflow 4: CSV/Excel Upload Preview

```text
1. HR/admin opens Attendance Management -> Import.
2. HR/admin downloads template if needed.
3. HR/admin uploads CSV/Excel.
4. System stores batch metadata and file hash.
5. System warns if file hash was already uploaded.
6. System parses rows.
7. System validates required columns.
8. System matches employees by priority.
9. System classifies valid rows using attendance date policy.
10. System detects duplicate employee/date rows.
11. System shows preview table with valid, warning, error, duplicate, unmatched, ambiguous rows.
12. HR/admin resolves duplicates or chooses bulk action.
13. HR/admin finalizes import.
14. System creates/updates AttendanceRecord rows according to selected actions.
15. System stores row-level audit.
```

Rows that must not finalize:

```text
missing date
missing check_in_time unless intentionally invalid/missing punch
no employee identifier
unmatched employee
ambiguous employee
invalid time format
invalid date format
unresolved duplicate conflict
locked period without admin override
```

#### Workflow 5: Duplicate Resolution

```text
1. System finds employee/date already exists.
2. Preview shows old values and new values side-by-side.
3. HR/admin chooses one action:
   skip duplicate
   overwrite existing
   update only empty fields
   keep both as conflict for review
4. System requires reason for overwrite and conflict actions.
5. System records AttendanceDuplicateDecision.
6. Conflict records are excluded from deduction until resolved.
```

#### Workflow 6: Attendance Classification

```text
1. Get attendance policy for AttendanceRecord.date.
2. Check if date is weekend/holiday/company holiday/non-working day.
3. Check if employee has approved full-day leave.
4. Check if employee has approved WFH.
5. Check if approved short/half leave explains the late time.
6. If covered, mark covered_excluded with reason.
7. If check-in missing, mark invalid_needs_correction.
8. If check-in <= on_time_until, mark on_time.
9. If check-in > on_time_until and check-in <= warning_until, mark warning_only.
10. If check-in > count_deduction_after, mark counted_late.
11. If any conflict or ambiguous state exists, mark pending_review/conflict_needs_review.
```

Important boundary examples:

```text
10:15 AM -> on_time
10:16 AM -> warning_only
10:30 AM -> warning_only
10:31 AM -> counted_late
```

#### Workflow 7: HR/Admin Allows Or Excuses A Late Record

```text
1. HR/admin opens Late Review tab.
2. HR/admin filters counted late records.
3. HR/admin selects a record.
4. HR/admin clicks Allow/Excuse.
5. HR/admin enters reason and remarks.
6. System changes final_status to allowed_excused.
7. System records previous_status, new_status, approved_by, approved_at, reason.
8. System removes record from future deduction count.
9. Employee notification/email is sent if configured.
```

If deduction was already applied:

```text
Do not simply change old deduction.
Require reversal/adjustment flow.
```

#### Workflow 8: Employee Correction Or Exception Request

```text
1. Employee opens personal attendance page.
2. Employee selects an attendance row.
3. Employee chooses correction or exception.
4. Employee enters reason and optional attachment.
5. System validates ownership.
6. System creates request with Pending status.
7. HR/admin sees it in Requests tab.
8. HR/admin approves or rejects with remarks.
9. If approved, system updates attendance through service.
10. If rejected, attendance remains unchanged.
11. Employee is notified.
```

#### Workflow 9: Deduction Preview Generation

```text
1. HR/admin opens Deductions tab.
2. HR/admin chooses weekly, monthly, or custom period.
3. System finds eligible AttendanceRecord rows in date range.
4. System excludes warning_only, allowed_excused, covered_excluded, invalid, conflict, pending_review.
5. System groups counted_late by employee.
6. System calculates deduction_days = floor(counted_late / policy.late_marks_per_deduction) * policy.deduction_days.
7. System calculates Earned/Sick/Unpaid split.
8. System shows per-employee preview.
9. HR/admin can override shortage handling where allowed.
10. Preview is saved as LateDeductionRun and summaries.
```

Preview must show:

```text
employee
period
counted late marks
warning-only count
allowed/excused count
invalid/conflict count
deduction days
earned leave deduction
sick leave deduction
unpaid/LOP amount
negative balance amount
status
block reason
```

#### Workflow 10: Apply Deduction

```text
1. HR/admin reviews deduction preview.
2. System checks run is not already applied.
3. System checks period is not locked unless allowed.
4. System locks affected leave balances using transaction/select_for_update.
5. System applies Earned first, Sick second.
6. System applies shortage handling.
7. System creates Leave records for my_leave Approved section using existing reason/detail field.
8. System creates LateDeductionLeaveSplit links.
9. System updates LeaveBalance.
10. System marks summaries applied/skipped/blocked.
11. System marks run applied.
12. System sends notifications/emails if configured.
13. System writes audit logs.
```

Transaction rule:

```text
Applying deductions must be atomic per employee or per run.
If per-run atomicity is too risky, apply per employee and record partial failures clearly.
Do not leave balance changes without summary/run audit.
```

#### Workflow 11: Auto Apply Clean Records

```text
1. Scheduler or admin trigger starts run.
2. System identifies cycle date range from policy.
3. System generates preview.
4. System applies only summaries marked ready_to_apply and clean.
5. System skips risky summaries to Needs Review.
6. System sends HR/admin run summary.
7. System logs applied, skipped, failed, and needs-review counts.
```

Clean summary requirements:

```text
employee confidently matched
attendance records valid
no unresolved duplicate conflict
no pending correction request
no approved leave/WFH/holiday conflict
shortage handling can use configured default
period not locked
policy unambiguous
```

#### Workflow 12: Fully Automatic

```text
1. System generates run by schedule.
2. System applies all eligible records using configured defaults.
3. Invalid, unmatched, ambiguous, locked, or conflict records are still skipped.
4. HR/admin receives summary of applied and skipped records.
```

Fully automatic must still not apply unsafe records.

#### Workflow 13: My Leave Approved Display

For applied deductions, create leave-history-visible entries using existing structure.

Default mapping:

```text
leave_type = Earned/Sick/Unpaid based on split
status = Approved
from_date = deduction period start
to_date = deduction period end
from_datetime = period_start at working day start if required by model
to_datetime = period_end at working day end if required by model
reason = detailed late deduction explanation
reviewed_by = HR/admin or null for system
approved_at = deduction applied time
created_at = deduction generated/created time
```

Reason template:

```text
Late Coming Deduction - {counted_late_marks} counted late marks for {period_start} to {period_end}. Deducted {days} day(s) from {leave_type}. Policy: every {late_marks_per_deduction} late marks = {deduction_days} day(s). Run: {run_reference}.
```

Split example:

```text
Earned row reason: Late Coming Deduction - 3 counted late marks for Jul 2026. Deducted 0.25 day from Earned Leave. Split deduction. Run: LCD-2026-07-001.
Sick row reason: Late Coming Deduction - 3 counted late marks for Jul 2026. Deducted 0.25 day from Sick Leave. Split deduction. Run: LCD-2026-07-001.
```

#### Workflow 14: Reversal Or Adjustment

```text
1. Admin opens applied deduction run or employee summary.
2. Admin chooses reversal/adjustment action.
3. Admin enters reason.
4. System shows current leave balance impact.
5. Admin confirms.
6. System creates AttendanceAdjustment.
7. System restores or adjusts LeaveBalance.
8. System creates leave record/history reason detail if needed.
9. System logs audit and notifies employee if configured.
```

Rules:

```text
Do not delete old deduction record.
Do not edit old applied Leave row silently.
Create additional reversal/adjustment evidence.
```

### UI Detail Specification

#### Attendance Management Page General Layout

Header should include:

```text
page title: Attendance Management
month/date range filter
employee search/filter
source filter
status filter
quick summary cards
primary actions by active tab
```

Summary cards should include:

```text
Total records in selected period
Warnings
Counted late
Allowed/excused
Needs review
Deductions pending
Applied deductions
Import errors
```

Tab behavior:

```text
Active tab persists in query string.
Filters persist in query string.
Refresh keeps current tab and filters.
Bulk actions require confirmation.
Dangerous actions require remarks.
```

#### Import Tab

Controls:

```text
Download template
Upload file
Preview import
Finalize import
Cancel batch
```

Preview table columns:

```text
row number
employee match
match method
date
check-in
check-out
source
system status
warnings
errors
duplicate status
action
```

Row actions:

```text
skip
overwrite
update empty fields
keep conflict
edit matched employee
```

#### Manual Entry Tab

Fields:

```text
employee
date
check-in time
check-out time
source/manual reason
remarks
final status override if permitted
```

Actions:

```text
Save
Save and add another
Reset
```

#### Records Tab

Columns:

```text
employee
date
check-in
check-out
source
system status
final status
policy
remarks
updated by
updated at
actions
```

Actions:

```text
view details
edit
mark allowed/excused
mark needs correction
view audit
```

#### Late Review Tab

Filters:

```text
counted late
warning-only
allowed/excused
pending review
invalid/needs correction
employee
month/date range
```

Actions:

```text
allow/excuse
bulk allow/excuse
send correction reminder
open employee request
view policy snapshot
```

#### Deductions Tab

Controls:

```text
cycle type
period selector
generate preview
apply selected
apply all ready
export preview
```

Preview columns:

```text
employee
counted late marks
warnings
allowed/excused
invalid/conflict count
deduction days
earned split
sick split
unpaid/LOP
negative balance
status
actions
```

Actions:

```text
apply
skip
change shortage handling
view late records
```

#### Policy Settings Tab

Fields:

```text
effective_from
on_time_until
warning_until
count_deduction_after
late_marks_per_deduction
deduction_days
deduction_cycle
weekly run day
monthly run day / last day
shortage handling
deduction mode
auto-run enabled
auto-run time
change reason
```

Panels:

```text
current active policy
future policies
policy history
past-date impact preview
```

#### Requests Tab

Columns:

```text
employee
attendance date
request type
current status
requested correction
reason
attachment
submitted at
status
actions
```

Actions:

```text
approve
reject
view attachment
view attendance record
```

#### Logs Tab

Sections:

```text
import batches
deduction runs
automatic run logs
email logs
audit logs
period locks
adjustments
```

#### Employee Attendance Page

Header summary:

```text
warnings this month
counted late marks this month
allowed/excused this month
pending requests
pending deduction days
applied deduction days
```

Sections:

```text
Attendance records
Late marks
Deduction previews
Applied deductions
Correction/exception requests
Notifications
```

Employee actions:

```text
request correction
request exception
view details
cancel pending request if allowed
```

#### Dedicated HR Attendance Report Page

Filters:

```text
employee
department
month
custom date range
source
late status
deduction status
policy version
```

Reports:

```text
attendance detail
late summary by employee
exception summary
correction request summary
deduction summary
Unpaid/LOP summary
negative balance summary
import error summary
audit/run history
```

Exports:

```text
CSV
Excel if available
PDF if existing report system supports it
```

### Validation And Edge Case Matrix

| Case | Required Behavior |
|---|---|
| Check-in at 10:15 | On time. |
| Check-in at 10:16 | Warning only. |
| Check-in at 10:30 | Warning only. |
| Check-in at 10:31 | Counted late. |
| Missing check-in | Invalid / Needs correction. |
| Missing check-out | Needs review if required, but check-in can classify late. |
| Check-out before check-in | Invalid / Needs correction. |
| Duplicate employee/date | Ask HR/admin, safe fallback conflict. |
| Same file uploaded twice | Warn using file hash. |
| Row uploaded twice | Warn using row hash/employee/date. |
| Employee name matches multiple users | Ambiguous, needs review. |
| Employee not found | Unmatched, needs review. |
| Approved full-day leave exists | Covered/excluded. |
| Approved WFH exists | Covered/excluded. |
| Holiday/weekend | Covered/excluded. |
| Pending correction request exists | Do not auto-apply. |
| Employee-specific schedule/exemption is active | Classify using employee-specific rule before global policy. |
| Allowed/excused late | Excluded from count. |
| Locked period | Block direct edits. |
| Policy missing | Create/use default policy or block with clear error. |
| Multiple policies match same date | Block and require admin fix. |
| Earned enough | Deduct Earned. |
| Earned partial, Sick enough | Split Earned then Sick. |
| Earned/Sick shortage | Default remaining to Unpaid/LOP. |
| Admin selects negative balance | Apply negative balance path and audit. |
| Admin selects manual shortage | Block/hold shortage and audit. |

### Notification Event Matrix

| Event | In-App | Email | Digest Eligible | Recipients |
|---|---:|---:|---:|---|
| Warning-only late created | Yes | Configurable | Yes | Employee |
| Counted late created | Yes | Configurable | Yes | Employee |
| Late allowed/excused | Yes | Configurable | No | Employee |
| Deduction preview generated | Yes | Configurable | No | Employee, HR/Admin |
| Deduction applied | Yes | Configurable | No | Employee, HR/Admin |
| Correction request submitted | Yes | Configurable | Yes | HR/Admin |
| Correction request approved | Yes | Configurable | No | Employee |
| Correction request rejected | Yes | Configurable | No | Employee |
| Import completed | Yes | Configurable | Yes | HR/Admin |
| Import errors found | Yes | Configurable | No | HR/Admin |
| Auto run completed | Yes | Configurable | Yes | HR/Admin |
| Auto run needs review | Yes | Configurable | No | HR/Admin |
| Adjustment/reversal applied | Yes | Configurable | No | Employee, HR/Admin |

### Test Plan Detail

#### Unit Tests

Policy tests:

```text
creates default policy
looks up policy by date
handles future policy
handles past-dated policy timeline
rejects invalid time boundaries
rejects invalid deduction values
```

Classification tests:

```text
10:15 on time
10:16 warning
10:30 warning
10:31 counted late
missing check-in invalid
approved leave excluded
WFH excluded
holiday/weekend excluded
allowed/excused excluded
```

Matching tests:

```text
matches employee_code first
matches biometric_device_id second
matches email third
matches phone fourth
matches name last
unmatched row flagged
ambiguous name flagged
```

Deduction tests:

```text
0/1/2 late marks no deduction
3 late marks 0.5 deduction
6 late marks 1.0 deduction
Earned first
Earned then Sick split
Unpaid/LOP shortage default
negative balance override
manual shortage override
allowed/excused ignored
warning-only ignored
```

Import tests:

```text
valid CSV row preview
missing date error
missing check-in error
bad date format error
bad time format error
duplicate employee/date preview
file hash duplicate warning
row hash duplicate warning
skip duplicate action
overwrite duplicate action
update empty fields action
conflict action blocks deduction
```

Permission tests:

```text
employee cannot view other employee records
employee cannot import attendance
employee cannot apply deduction
HR can import if role allows
HR cannot change policy if admin-only
admin can change policy
admin can reverse/adjust
```

#### Integration Tests

```text
manual entry -> classification -> employee page visible
CSV upload -> preview -> finalize -> records visible
late records -> deduction preview -> apply -> Leave record appears in Approved section
deduction split -> multiple Leave records created
correction request -> HR approve -> attendance excluded -> deduction recalculated
applied deduction -> adjustment -> balance restored
```

#### View/UI Tests

```text
Attendance Management page loads for HR/admin
Employee attendance page loads for employee
Employee attendance page hides other employees
HR attendance report page loads
my_leave Approved section shows late deduction row
query tab/status filters preserve state
```

#### Regression Tests

```text
normal leave apply/edit/delete still works
existing my_leave pending/approved/rejected filters still work
existing leave report page remains separate
existing LeaveBalance calculations not broken
existing WFH/holiday leave logic not broken
```

### Acceptance Criteria Before Marking Done

Implementation can be marked Done only when all applicable Version 1 criteria are satisfied.

Data/model acceptance:

```text
Attendance policies are effective-dated.
Attendance records store source and final status.
Import batches and rows are audited.
Deduction runs store policy snapshot.
Applied deductions link to leave records/history.
Decimal fields are used for day amounts.
```

Business logic acceptance:

```text
10:15/10:30 boundaries work exactly.
3 counted late marks deduct 0.5 day.
Earned is used before Sick.
Shortage defaults to Unpaid/LOP.
Allowed/excused records do not count.
Warning-only records do not count.
Invalid/conflict records do not auto-deduct.
Approved leave/WFH/holiday/weekend records are excluded.
```

UI acceptance:

```text
HR/admin Attendance Management page has required tabs.
Employee attendance page shows personal records only.
Dedicated HR attendance report page is separate from leave report.
my_leave Approved section shows applied late deductions.
Import preview shows errors/warnings before save.
Deduction preview shows split before apply.
```

Audit/security acceptance:

```text
Policy changes require effective date and reason.
Duplicate decisions are audited.
Exception approvals are audited.
Deduction applications are audited.
Email sends are logged.
Employee cannot access other employee records.
Locked/applied records are not silently changed.
```

Testing acceptance:

```text
Core service tests pass.
View permission tests pass.
Deduction integration tests pass.
Existing leave workflow tests still pass or are manually verified if tests are not available.
```

Documentation acceptance:

```text
This plan is updated with implemented/verified status.
Project docs are updated if routes, commands, env values, or production steps change.
Any new dependency is documented in requirements and deployment notes.
```

### Implementation Risk Notes

High-risk areas:

```text
LeaveBalance updates can affect production balances.
my_leave display depends on existing Leave model assumptions.
Policy backdating can create confusing historical recalculation if not controlled.
Automatic deduction can apply incorrect balance changes if invalid records are not skipped.
CSV/Excel parsing can introduce dependency or format issues.
```

Risk controls:

```text
Start with manual review mode.
Keep automatic deduction disabled by default.
Use transactions for balance changes.
Store policy snapshots.
Never modify applied deductions silently.
Add focused tests before enabling automatic mode.
```

### Final Pre-Implementation Checklist

Before writing feature code, confirm these in the existing project:

```text
Profile fields available for employee_code, phone_number, biometric_device_id.
Exact LeaveBalance fields and update patterns.
How Unpaid leave currently affects balances.
How approved leave records are created and displayed.
Existing notification/email service functions.
Existing HR/admin role checks.
Existing report/export service patterns.
Existing WFH/holiday models and helper services.
Whether openpyxl or any Excel parser is already installed.
Where attachments should be stored securely.
How migrations are currently named and tested.
```

If any item conflicts with existing code patterns, implementation should follow the codebase pattern and update this plan with the final decision.


## Enterprise Readiness Expansion

This section adds enterprise-grade requirements beyond the core late-coming feature. These requirements make the attendance system scalable, auditable, configurable, integration-ready, and safe for long-term production use.

The core late-coming system should still be implemented in controlled phases, but the data model and architecture should not block these enterprise capabilities later.

### Enterprise Requirement Summary

Accepted enterprise-level capabilities:

```text
multi-shift and roster support
location/site/department-specific attendance policies
work calendar support
biometric device registry and sync governance
mobile/web/manual/file source governance
break, overtime, early leaving, and working-hours foundation
absence management foundation
payroll export and payroll close workflow
period lock, unlock, reversal, and adjustment lifecycle
approval workflow, escalation, delegation, and maker-checker controls
bulk operations with audit
attendance reconciliation and anomaly detection
enterprise reporting, exports, and BI-ready summaries
API/webhook readiness
observability, health checks, metrics, and failure alerts
performance and scalability rules
security, privacy, data retention, and attachment governance
feature flags and phased rollout controls
migration/backfill strategy
accessibility and usability standards
disaster recovery and operational runbooks
```

### Enterprise Phasing Principle

Not every enterprise feature must be built in the first release, but every data model and service should be designed so these features can be added without rewriting the core system.

Recommended phasing:

```text
Version 1:
Safe manual operation, import, late classification, manual review/apply, employee transparency, audit foundation.

Version 2:
Automation, biometric sync, period locking, adjustment workflow, absence/early leaving/overtime foundation.

Version 3:
Payroll exports, advanced workflow approvals, anomaly detection, APIs/webhooks, BI dashboards, multi-site/shift expansion.
```

### Multi-Shift And Roster Support

Enterprise attendance systems usually support different working schedules.

Required future-ready concepts:

```text
Shift
RosterAssignment
WorkCalendar
EmployeeScheduleOverride
```

Shift should support:

```text
name
start_time
on_time_until
warning_until
count_deduction_after
end_time
minimum_work_hours
break_rules
grace_rules
is_night_shift
cross_midnight_support
```

RosterAssignment should support:

```text
employee
shift
from_date
to_date
assigned_by
assigned_at
remarks
```

Rules:

```text
Default Version 1 can use one standard shift/policy.
AttendanceRecord should still allow future shift/policy reference.
Late classification should be service-based so shift logic can replace fixed timing later.
Employee-specific timing/exemption must be resolved before global policy classification.
Night shifts and cross-midnight attendance should be planned, even if not implemented first.
```

### Location, Site, Department, And Calendar Policies

Enterprise systems often have different attendance rules by office location, department, or employee group.

Future-ready policy scopes:

```text
global policy
location/site policy
department policy
employee-specific policy override
shift policy
```

Policy priority should be deterministic:

```text
1. Employee-specific override
2. Shift/roster policy
3. Department policy
4. Location/site policy
5. Global policy
```

Work calendars should support:

```text
weekend rules
public holidays
company holidays
special working Saturdays
company-declared non-working days
half-working days
emergency closure days
```

Rules:

```text
Version 1 can use existing holidays/weekend logic.
Design policy lookup so scoped policies can be added later.
Reports should record which policy/calendar excluded a date.
```

### Device And Source Governance

Attendance can come from manual entry, file upload, biometric, and later possibly mobile/web check-in.

Enterprise source governance should track:

```text
source type
source reliability
source owner
source priority
whether source can overwrite another source
whether source requires HR review
whether source is allowed for auto deduction
```

Future BiometricDevice model should support:

```text
device_name
device_identifier
location/site
vendor/model
sync_method: file/api/manual
last_sync_at
last_successful_sync_at
sync_status
is_active
created_by
remarks
```

Source priority examples:

```text
manual HR correction can override file upload
approved correction can override biometric
biometric can create initial records
file upload can fill gaps
untrusted source must go to review
```

Rules:

```text
Every attendance record must keep its source.
Every overwrite between sources must be audited.
Automatic deduction should use only trusted/final records.
```

### Working Hours, Breaks, Overtime, Early Leaving, And Absence Foundation

Even if Version 1 focuses on late coming, enterprise attendance needs a foundation for broader time rules.

AttendanceRecord or related detail records should eventually support:

```text
first_check_in
last_check_out
total_work_duration
break_duration
net_work_duration
early_leave_minutes
late_minutes
overtime_minutes
shortfall_minutes
absence_status
```

Possible future classification statuses:

```text
present
late
warning_late
early_left
short_hours
absent
half_day_absent
overtime
manual_review_required
```

Rules:

```text
Version 1 should not auto-deduct early leaving/absence unless explicitly implemented.
But records should store enough time data so these rules can be added later.
Missing check-out should not prevent late check-in classification, but should mark working-hours completeness as needs review.
```

### Payroll Export And Payroll Close Workflow

Late-coming deduction may create Unpaid/LOP, so enterprise systems need payroll handoff.

Payroll workflow should support:

```text
attendance period close
payroll export preview
payroll export approval
export file generation
export history
export reversal/adjustment reference
```

Payroll export data should include:

```text
employee code
employee name
period start
period end
counted late marks
leave deducted
unpaid/LOP amount
negative balance amount
adjustments
final payroll-impact days
exported_by
exported_at
```

Payroll status lifecycle:

```text
not_ready
ready_for_review
approved_for_payroll
exported
locked
adjustment_required
```

Rules:

```text
Payroll export should not happen from unresolved attendance records.
Payroll export should use locked/applied deduction data.
Corrections after payroll export should become adjustments, not silent edits.
Version 1 can skip actual payroll export, but data should be payroll-ready.
```

### Approval Workflow, Escalation, Delegation, And Maker-Checker

Enterprise systems often require configurable approval controls.

Workflow capabilities to support:

```text
single HR approval
admin approval for policy changes
admin approval for reversal/adjustment
maker-checker for high-risk actions
escalation when request is pending too long
delegation when HR/admin is unavailable
bulk approval with audit
```

High-risk actions should support stricter controls:

```text
policy backdating
bulk overwrite of attendance
fully automatic deduction enablement
period unlock
deduction reversal
negative balance approval
manual shortage handling
```

Rules:

```text
Version 1 can keep approval simple.
But service methods should record actor, action, reason, and timestamp so maker-checker can be added later.
Admin-only actions must be separated from HR actions.
```

### Attendance Reconciliation And Anomaly Detection

Enterprise attendance requires reconciliation tools to catch bad data before deduction.

Reconciliation checks should identify:

```text
missing attendance for working day
missing check-in
missing check-out
check-out before check-in
multiple records for same employee/date
duplicate file upload
same biometric id mapped to multiple employees
same employee code mapped to multiple users
late record with approved leave/WFH conflict
attendance on holiday/weekend
unusually high late count
sudden source changes
manual overrides without remarks
```

Reconciliation output should show:

```text
severity: info/warning/error/blocker
employee
date
issue type
description
recommended action
resolved_by
resolved_at
```

Rules:

```text
Block automatic deduction for blocker issues.
Warn HR/admin for warning issues.
Allow HR/admin to mark reconciliation issue resolved with remarks.
```

### Enterprise Reporting And BI-Ready Data

Reports should support operational, audit, and management views.

Additional enterprise reports:

```text
monthly late trend by department
late trend by employee
warnings vs counted late comparison
exception approval trend
manual correction trend
biometric failure trend
import error trend
policy change history report
payroll impact report
LOP report
negative balance report
period lock/unlock report
adjustment/reversal report
```

BI-ready summaries should be possible later:

```text
employee-month attendance summary
department-month attendance summary
policy-period summary
source-quality summary
payroll-impact summary
```

Rules:

```text
Reports should be generated from final/audited records.
Report exports should include generated_at and generated_by.
Management reports should not change operational data.
```

### API, Webhook, And Integration Readiness

Future integrations should not require rewriting the attendance engine.

Potential APIs:

```text
create attendance record
bulk upload attendance rows
get employee attendance summary
get deduction preview
get deduction run status
submit correction request
approve/reject correction request
get attendance report data
```

Potential webhooks/events:

```text
attendance_record_created
attendance_record_corrected
late_mark_counted
late_mark_excused
deduction_preview_generated
deduction_applied
correction_request_submitted
correction_request_decided
payroll_export_ready
```

Rules:

```text
Version 1 does not need public APIs.
Service functions should be reusable by views, scheduled jobs, and future APIs.
External integrations must be authenticated and audited.
Webhook delivery should be retryable and logged when implemented.
```

### Security, Privacy, And Compliance

Attendance data is sensitive employee data.

Security requirements:

```text
role-based access control
employee self-scope enforcement
audit logs for create/update/delete/apply/reverse/export
secure attachment access
file upload validation
permission checks on every view/action
CSRF protection for forms
safe handling of uploaded files
no sensitive raw files in public static directories
```

Privacy requirements:

```text
employees see only their own records
HR/admin access should follow project roles
exports should be permission controlled
attachments should be restricted to owner and reviewers
logs should avoid exposing secrets/passwords
old data retention should follow company policy
```

Enterprise audit requirements:

```text
who changed it
what changed
old value
new value
when changed
why changed
source of change
related import batch/deduction run/request
```

Rules:

```text
High-risk operations should require remarks.
Bulk actions should record one parent audit plus per-row audit.
Applied financial/payroll-impact data should never be silently overwritten.
```

### Data Retention, Archival, And Legal Hold

Long-running attendance systems need retention rules.

Retention controls should eventually cover:

```text
attendance records
uploaded files
import row raw data
email logs
audit logs
attachments
biometric raw payload references
deduction runs
payroll exports
```

Retention options:

```text
keep forever
keep for N months/years
archive after N months
delete attachments after N months
legal hold prevents deletion
```

Rules:

```text
Version 1 can keep data indefinitely.
Do not build destructive retention deletion without explicit admin controls and confirmation.
Retention design should be documented before production automation.
```

### Observability, Health Checks, And Operational Alerts

Enterprise systems need operational visibility.

Metrics to track:

```text
imports completed
imports failed
rows processed
rows failed
unmatched rows
duplicate conflicts
pending correction requests
pending deduction previews
automatic run success/failure
email send success/failure
biometric sync success/failure
```

Alerts to support later:

```text
automatic run failed
biometric sync failed
high unmatched employee count
high invalid attendance count
email failure spike
deduction apply failure
policy configuration conflict
multiple active policies for date
```

Rules:

```text
Every scheduled/automatic job must log start, end, result, and errors.
Failures should be visible in Attendance Management -> Logs.
Production runbooks should explain how to recover failed runs.
```

### Performance And Scalability Rules

Attendance data grows quickly.

Indexes likely needed:

```text
AttendanceRecord(employee, date)
AttendanceRecord(date, final_status)
AttendanceRecord(source, date)
AttendanceImportBatch(file_hash)
AttendanceImportRow(batch, row_status)
LateDeductionRun(period_start, period_end, status)
LateDeductionEmployeeSummary(run, employee)
AttendanceCorrectionRequest(employee, status)
AttendanceCorrectionRequest(status, submitted_at)
```

UI scalability rules:

```text
paginate large tables
server-side filter for large datasets
avoid rendering thousands of rows at once
support export through background job if dataset is large
show progress/status for long imports
```

Processing rules:

```text
bulk import should process rows in controlled batches
large deduction runs should avoid long request timeouts
background tasks should be used where existing project pattern supports them
balance updates should use transactions and row locks
```

### Feature Flags And Rollout Controls

Enterprise rollout should be controlled.

Feature toggles to consider:

```text
attendance_module_enabled
attendance_import_enabled
manual_attendance_entry_enabled
employee_attendance_page_enabled
late_deduction_preview_enabled
late_deduction_apply_enabled
auto_deduction_enabled
biometric_sync_enabled
attendance_email_enabled
attendance_reports_enabled
```

Rollout strategy:

```text
1. Enable policy and records for admin testing.
2. Enable manual entry and import preview.
3. Enable finalizing imports.
4. Enable deduction preview only.
5. Enable manual apply for selected HR/admin users.
6. Enable employee page visibility.
7. Enable notifications.
8. Enable auto apply clean records only after production confidence.
```

Rules:

```text
Dangerous features should default disabled.
Automatic deduction should default disabled.
Feature flag state should be visible to admin.
```

### Migration, Backfill, And Data Quality Strategy

Implementation may need migration from old/manual attendance files later.

Migration strategy should include:

```text
schema migrations
default policy migration
employee identifier cleanup
backfill employee_code/biometric ids
import historical attendance as batches
validate historical rows before applying deductions
avoid retroactive deductions unless explicitly approved
```

Rules:

```text
Historical import should not auto-deduct by default.
Historical rows should be marked imported/backfilled source.
Backfill scripts should be repeatable and logged.
```

### Accessibility, Usability, And Human Review Quality

Enterprise systems should be usable under real HR workload.

Usability requirements:

```text
clear status labels
consistent filters
bulk actions with confirmation
side-by-side duplicate comparison
clear reason display
empty states
loading states
error states
success confirmations
export buttons where useful
copyable run/reference IDs
```

Accessibility requirements:

```text
keyboard reachable tabs and actions
visible focus states
labels for form controls
status not communicated only by color
readable table layouts
mobile/tablet awareness for employee page
```

Human-review requirements:

```text
show why a record is counted or excluded
show policy used
show source of attendance
show previous and new values on overrides
require remarks for high-impact decisions
```

### Disaster Recovery And Operational Runbooks

Attendance and deduction data must be recoverable.

Runbooks should eventually cover:

```text
failed import recovery
wrong file uploaded
wrong duplicate action selected
policy configured incorrectly
late deduction applied incorrectly
employee request approved by mistake
biometric sync failure
email notification failure
payroll export generated incorrectly
```

Recovery actions should include:

```text
cancel import batch before finalization
mark import batch failed/cancelled
create adjustment/reversal
re-run deduction preview
restore from backup only as last resort
export audit evidence
```

Rules:

```text
Every recovery action should be auditable.
Production documentation should include common attendance recovery procedures.
```

### Enterprise Acceptance Criteria

The attendance system can be called enterprise-ready only when these broader criteria are satisfied or intentionally phased with no blocking design issues.

Architecture acceptance:

```text
Core logic is service-based, not trapped inside templates/views.
Attendance sources feed a common record model.
Policy lookup is effective-dated and deterministic.
Deduction application is transactional and audited.
Automation uses the same service path as manual apply.
```

Governance acceptance:

```text
Permissions are explicit.
High-risk actions require reason.
Applied deductions cannot be silently changed.
Imports and duplicate decisions are auditable.
Policy changes are auditable.
```

Integration acceptance:

```text
Data model supports future biometric sync.
Data model supports payroll/export reporting.
Service layer can support future APIs/webhooks.
Import batches prevent accidental duplicate processing.
```

Operations acceptance:

```text
Logs show failed imports and deduction runs.
Admin/HR can identify records needing review.
Large tables are paginated/filterable.
Background/long-running tasks have visible status where needed.
```

Employee trust acceptance:

```text
Employee can see warnings, counted late marks, excused records, previews, and applied deductions.
Employee can request correction/exception.
Employee can see decision status.
Late deduction reason appears in my_leave Approved section.
```

### Enterprise-Level Items Still To Confirm During Implementation

These are not missing planning decisions; they are implementation-discovery items that must be confirmed by reading existing code and production constraints.

```text
1. Exact existing employee identifier fields.
2. Exact existing HR/admin permission model.
3. Whether the project already has an Excel parser dependency.
4. Existing email queue/background task pattern.
5. Existing report export formats and helpers.
6. Existing WFH and holiday helper APIs.
7. Whether Leave can safely represent late deduction entries without adding an adjustment model.
8. Exact LeaveBalance update semantics for Earned, Sick, and Unpaid.
9. Whether negative balance is already supported or needs a new field/logic.
10. Whether attachments require new storage/security settings.
11. Production database indexes and migration impact.
12. Whether automated jobs should use existing qcluster/scheduler patterns.
13. Whether attendance report export should be synchronous or background-generated.
14. How to expose feature flags in admin settings.
15. Whether payroll export is needed in Version 1, Version 2, or Version 3.
16. Exact employee-specific schedule/grant permission rules.
```

### Enterprise Build Recommendation

Recommended implementation should happen in milestones:

```text
Milestone 1: Data foundation
Policy, attendance records, imports, requests, deduction runs, audit fields, identifiers.

Milestone 2: Manual operations
Manual entry, CSV/Excel preview/finalize, duplicate resolution, classification, HR/admin tabs.

Milestone 3: Deduction operations
Late review, allowed/excused flow, deduction preview, manual apply, my_leave approved entries.

Milestone 4: Employee transparency
Employee attendance page, request correction/exception, notifications, email settings.

Milestone 5: Reports and governance
Dedicated HR attendance report, exports, logs, permission hardening, import/deduction audit.

Milestone 6: Enterprise controls
Period lock, adjustment/reversal, reconciliation dashboard, feature flags, runbooks.

Milestone 7: Automation and integrations
Auto apply clean records, fully automatic mode, biometric sync, payroll export, APIs/webhooks.
```

### Final Enterprise Planning Status

After this expansion, no major enterprise attendance capability is intentionally omitted from the plan.

Remaining work is implementation discovery and phased build execution:

```text
read existing code
finalize exact field names
implement models/migrations
implement services
implement pages
implement tests
verify with real workflows
update this plan as items become implemented/verified/done
```



## Total Control Final Guardrails

This section captures final control-layer requirements so HR/admin can fully control attendance behavior without unsafe silent changes.

These items are accepted as enterprise control requirements.

### 1. Dry Run / Simulation Mode

Before applying deductions, HR/admin should be able to run a simulation.

Simulation should show:

```text
which employees will be affected
which attendance records are counted
which records are excluded
which policy was used
leave split: Earned/Sick/Unpaid/negative/manual
warnings and blockers
estimated leave balance after deduction
```

Rules:

```text
Simulation must not change attendance, leave balance, leave records, or payroll-impact data.
Simulation results can be saved as preview, exported, or discarded.
```

### 2. Draft, Publish, And Disable Controls For Policy Changes

Admin should be able to prepare policy changes without immediately activating them.

Policy lifecycle should support:

```text
draft
published
scheduled
active
expired
disabled
cancelled
```

Rules:

```text
Draft policies do not affect attendance.
Scheduled policies apply only from effective_from.
Disabled policies stop applying from their disabled/ended date.
Cancelled future policies never apply.
Policy history remains visible.
```

### 3. Configurable Reason Codes

HR/admin should be able to configure reason codes for consistency.

Reason-code areas:

```text
late allowed/excused reasons
manual attendance correction reasons
duplicate overwrite reasons
policy change reasons
negative balance approval reasons
manual shortage handling reasons
period unlock reasons
reversal/adjustment reasons
```

Rules:

```text
High-risk actions should require selecting a reason code plus optional remarks.
Reason codes should be active/inactive instead of deleted when no longer used.
```

### 4. Import Mapping Profiles

Different CSV/Excel/biometric exports may have different column names.

Admin should eventually be able to create import mapping profiles.

Examples:

```text
MST Standard Template
Biometric Vendor A Export
Biometric Vendor B Export
Manual HR Sheet
```

Each mapping profile should define:

```text
source type
employee identifier column
date column
check-in column
check-out column
remarks column
date format
time format
header row number
whether file has multiple punches
```

Rules:

```text
Default template should work first.
Mapping profiles prevent code changes for future file formats.
```

### 5. Source Trust And Override Priority

Admin should control which attendance sources are trusted and what can override what.

Source controls:

```text
manual source trusted yes/no
file upload trusted yes/no
biometric trusted yes/no
which source can overwrite another source
which source always requires review
which source can be used for auto deduction
```

Example priority:

```text
approved HR correction > manual HR entry > biometric > file upload > untrusted import
```

Rules:

```text
Any source override must be audited.
Untrusted source records must not auto-deduct.
```

### 6. Per-Record Final Override And Lock

HR/admin should be able to manually finalize a specific attendance record.

Controls:

```text
finalize as on time
finalize as warning only
finalize as counted late
finalize as allowed/excused
finalize as covered/excluded
lock record from recalculation
unlock record with reason
```

Rules:

```text
Locked final records should not be recalculated automatically by later imports or policy changes.
Unlock requires permission and reason.
Applied deduction records require adjustment/reversal instead of direct edit.
```

### 7. Employee-Level Deduction Hold

HR/admin should be able to temporarily hold deductions for a specific employee.

Use cases:

```text
employee under HR review
pending medical approval
management hold
attendance dispute
payroll hold
```

Controls:

```text
hold employee deduction from date/to date
hold reason
created_by
approved_by if needed
release hold
```

Rules:

```text
Held employees can still have attendance recorded.
Deduction preview should show them as blocked/held, not silently ignore them.
```

### 8. Bulk Action Preview And Confirmation

Bulk actions must be controlled.

Bulk actions include:

```text
bulk import finalize
bulk duplicate skip/overwrite/update
bulk allow/excuse
bulk deduction apply
bulk policy assignment
bulk employee schedule grant
bulk notification send
```

Rules:

```text
Bulk actions must show affected count before applying.
Bulk high-risk actions require confirmation and remarks.
Bulk actions should create parent audit plus per-record audit.
```

### 9. No Hard Delete For Critical Attendance Data

Enterprise attendance records should not be hard-deleted through normal UI.

Preferred actions:

```text
cancel
void
archive
mark inactive
reverse
adjust
```

Rules:

```text
Hard delete should be admin-only or unavailable after records affect deduction/payroll.
Deleted/voided records should remain auditable where legally and operationally appropriate.
```

### 10. Configuration Export And Change History

Admin should be able to review and export configuration history.

Configuration history should include:

```text
policy changes
employee-specific schedule grants
source trust settings
email notification settings
reason code changes
feature flag changes
permission-impacting changes
```

Rules:

```text
Every config change should show old value, new value, changed_by, changed_at, and reason.
```

### 11. Notification Template Control

Admin should eventually control notification/email wording.

Template controls:

```text
warning late email template
counted late email template
allowed/excused email template
deduction preview email template
deduction applied email template
correction request decision template
HR/admin import summary template
```

Rules:

```text
Templates should have safe placeholders.
Template edits should be audited.
Broken templates should fall back to safe default wording.
```

### 12. Time Zone And Time Normalization

Attendance times must be interpreted consistently.

Controls:

```text
system attendance timezone
import timezone if file/device differs
biometric device timezone
employee/location timezone future-ready field
```

Rules:

```text
Version 1 can use the project/company timezone.
Imported times should be normalized before classification.
Reports should show local/company time clearly.
```

### 13. Overlapping Rule Conflict Resolver

Because the system supports global, location, department, shift, and employee-specific rules, conflicts must be deterministic.

Conflict resolver should handle:

```text
multiple active employee-specific schedules
employee-specific schedule overlapping shift schedule
past-dated policy overlap
future policy overlap
multiple active exemptions
```

Rules:

```text
Use documented priority order.
If two same-priority rules overlap, block classification and send to admin review.
Never choose randomly.
```

### 14. Configuration Checklist Before Enabling Auto Deduction

Before automatic deduction can be enabled, the system should check readiness.

Readiness checks:

```text
active policy exists
no overlapping policy conflict
source trust configured
employee identifiers are clean enough
no unresolved high-severity reconciliation issues for target period
email/notification settings reviewed
deduction mode confirmed
period not locked incorrectly
```

Rules:

```text
If readiness fails, auto deduction cannot be enabled or run.
Admin should see exact blockers.
```

### 15. Total Control Acceptance Criteria

The system can be considered total-control ready when HR/admin can:

```text
configure global policy
configure employee-specific timing/exemption
choose source trust and override rules
preview every import before saving
resolve every duplicate explicitly
manually finalize any attendance record with audit
run dry-run deduction simulations
apply deductions manually
enable automation only after readiness checks
hold deductions for employee review
reverse/adjust applied deductions
lock/unlock periods with reason
see all reports and audit trails
control notifications and email behavior
export reports and configuration history
```

Final rule:

```text
No attendance data should affect leave balance, payroll impact, or employee record history without a traceable policy, source, actor, timestamp, and reason/audit path.
```

## Secure Preview And Connector Architecture

This section defines how the attendance system should be connected to the existing project safely.

The goal is to build attendance as a feature-rich enterprise module without making the existing leave system fragile. Attendance should connect to leave, notification, report, WFH, holiday, and audit systems through controlled hooks/adapters instead of scattered direct edits.

### Core Architecture Decision

Attendance should be implemented as an isolated connector-style module.

Preferred structure if safe for the current Django project:

```text
attendance/
```

Alternative structure if keeping everything inside the existing `App` is safer:

```text
App/attendance/
App/attendance/adapters/
App/attendance/services/
App/attendance/views/
App/attendance/tests/
```

Decision rule:

```text
Choose the structure that best fits the existing project with the least risk.
Even if implemented inside App, attendance logic must remain isolated by folder/service boundaries.
```

### Why Connector Architecture Is Needed

The attendance module will touch sensitive existing areas:

```text
employees
leave balances
leave records
WFH rules
holidays
notifications
emails
reports
audit logs
scheduler/background jobs
```

If attendance logic directly edits all these systems from random views or templates, future maintenance becomes risky.

Connector architecture gives control:

```text
attendance can be enabled or disabled safely
leave system can continue working without attendance
biometric sync can be added later without rewriting leave logic
preview mode can run without balance impact
adapters can be tested independently
future removal is possible without breaking core leave workflows
```

### Secure Preview Mode

The first implementation must start in secure preview mode.

Preview mode allows:

```text
manual attendance entry
CSV/Excel import preview
attendance record validation
late classification
warning/count/exclusion display
deduction preview generation
employee attendance page preview
HR/admin reports preview
logs and audit preview
```

Preview mode must block:

```text
real LeaveBalance changes
creation of approved late-deduction Leave records
Unpaid/LOP payroll-impact changes
automatic deduction application
biometric auto-sync changes
automatic payroll export
```

Preview mode is the safety layer for production testing.

Rules:

```text
No leave balance changes while ATTENDANCE_PREVIEW_ONLY=True.
No my_leave approved deduction rows while apply deductions are disabled.
No automatic deduction while auto deduction flag is disabled.
Every preview should clearly show that it is preview-only.
HR/admin must see why Apply is disabled when preview mode is active.
```

### Feature Flags

Attendance should be controlled by explicit feature flags.

Suggested settings:

```text
ATTENDANCE_MODULE_ENABLED=True
ATTENDANCE_PREVIEW_ONLY=True
ATTENDANCE_ALLOW_APPLY_DEDUCTIONS=False
ATTENDANCE_ALLOW_AUTO_DEDUCTION=False
ATTENDANCE_ALLOW_BIOMETRIC_SYNC=False
ATTENDANCE_ALLOW_PAYROLL_EXPORT=False
ATTENDANCE_ALLOW_EMPLOYEE_PORTAL=True
ATTENDANCE_ALLOW_HR_REPORTS=True
ATTENDANCE_ALLOW_EMAIL_NOTIFICATIONS=False
```

Default safe production introduction:

```text
ATTENDANCE_MODULE_ENABLED=True
ATTENDANCE_PREVIEW_ONLY=True
ATTENDANCE_ALLOW_APPLY_DEDUCTIONS=False
ATTENDANCE_ALLOW_AUTO_DEDUCTION=False
ATTENDANCE_ALLOW_BIOMETRIC_SYNC=False
```

Safe disabled state:

```text
ATTENDANCE_MODULE_ENABLED=False
```

When disabled:

```text
attendance URLs should not be accessible except maybe admin archive/history if explicitly allowed
attendance nav links should be hidden
attendance scheduled jobs should not run
attendance should not affect leave balances or records
existing leave workflows must continue normally
```

### Connector / Adapter Layer

Attendance must interact with existing systems through adapters.

Required adapters:

```text
EmployeeResolver
LeaveBalanceAdapter
LeaveRecordAdapter
HolidayWfhAdapter
NotificationAdapter
PermissionAdapter
ReportAdapter
AuditAdapter
SchedulerAdapter
AttachmentStorageAdapter
```

Optional future adapters:

```text
PayrollExportAdapter
BiometricDeviceAdapter
WebhookAdapter
FeatureFlagAdapter
```

### Adapter Responsibilities

#### EmployeeResolver

Purpose:

```text
Find and validate employees from attendance identifiers.
```

Responsibilities:

```text
match by employee_code
match by biometric_device_id
match by email
match by phone_number
match by employee_name
return exact/unmatched/ambiguous result
never silently choose between ambiguous employees
```

#### LeaveBalanceAdapter

Purpose:

```text
Apply or preview leave balance deductions safely.
```

Responsibilities:

```text
read Earned/Sick balances
calculate Earned first, Sick second, Unpaid/LOP shortage
support preview calculation without saving
apply deduction only when feature flags allow
use transactions and row locks during real apply
return before/after balance details
```

Hard rule:

```text
Attendance services must not directly mutate LeaveBalance except through LeaveBalanceAdapter.
```

#### LeaveRecordAdapter

Purpose:

```text
Create my_leave Approved history entries for applied late deductions.
```

Responsibilities:

```text
create approved Leave records only when apply is enabled
use existing reason/detail field for explanation
create separate rows for Earned/Sick/Unpaid split
link created records back to deduction summary
support preview-only explanation without saving records
```

Hard rule:

```text
No approved late-deduction Leave record should be created in preview-only mode.
```

#### HolidayWfhAdapter

Purpose:

```text
Tell attendance classification whether a date should be excluded.
```

Responsibilities:

```text
check approved leave
check short/half leave timing conflicts
check WFH
check company holiday
check public holiday
check weekend/non-working day
return exclusion reason
```

#### NotificationAdapter

Purpose:

```text
Create in-app and email notifications using existing project systems.
```

Responsibilities:

```text
respect admin notification configuration
send employee notifications
send HR/admin summaries
log email delivery success/failure
support digest later
```

#### PermissionAdapter

Purpose:

```text
Keep role checks centralized.
```

Responsibilities:

```text
employee self-access only
HR/admin attendance access
admin-only policy/automation/reversal controls
future maker-checker support
feature flag enforcement
```

#### ReportAdapter

Purpose:

```text
Reuse existing report/export patterns without mixing attendance into leave reports.
```

Responsibilities:

```text
build attendance reports
export attendance data
keep HR attendance reports separate from leave reports
use existing report styling/helpers where appropriate
```

#### AuditAdapter

Purpose:

```text
Create consistent audit entries for every high-impact attendance action.
```

Responsibilities:

```text
policy changes
manual attendance edits
imports
duplicate decisions
exceptions
correction requests
deduction preview/apply
period locks/unlocks
adjustments/reversals
feature flag changes if stored in DB
```

#### SchedulerAdapter

Purpose:

```text
Connect future automatic runs to the existing scheduler/background worker system.
```

Responsibilities:

```text
skip jobs when module disabled
skip apply jobs when preview-only
log job start/end/errors
support auto apply clean records later
```

### Dependency Direction Rule

Dependency direction must be one-way:

```text
attendance module -> adapters -> existing project systems
existing leave workflow -> should not depend on attendance module
```

The leave system should not require attendance to be enabled.

If attendance is disabled, these must still work:

```text
apply leave
my_leave page
HR dashboard
leave approval/rejection
leave reports
WFH/holiday logic
notifications unrelated to attendance
```

### Secure Preview Apply Flow

Deduction apply should follow this safety gate:

```text
1. Generate preview.
2. Show affected employee records.
3. Show policy snapshot.
4. Show Earned/Sick/Unpaid split.
5. Check ATTENDANCE_MODULE_ENABLED.
6. Check ATTENDANCE_PREVIEW_ONLY is False.
7. Check ATTENDANCE_ALLOW_APPLY_DEDUCTIONS is True.
8. Check user has permission.
9. Check run is not already applied.
10. Check period is not locked incorrectly.
11. Apply through LeaveBalanceAdapter and LeaveRecordAdapter.
12. Audit everything.
```

If any gate fails:

```text
show clear blocked reason
make no balance changes
make no leave record changes
log blocked attempt if high-risk
```

### Safe Removal / Disable Plan

If attendance needs to be removed or disabled later:

```text
1. Set ATTENDANCE_MODULE_ENABLED=False.
2. Hide attendance navigation links.
3. Disable attendance URLs or show module-disabled page.
4. Stop attendance scheduler jobs.
5. Keep historical attendance tables for audit/archive.
6. Do not delete historical Leave records already created by applied deductions.
7. Existing leave system remains functional.
```

Optional archive-only mode:

```text
ATTENDANCE_MODULE_ENABLED=False
ATTENDANCE_ARCHIVE_VIEW_ENABLED=True
```

Archive mode can allow admin to view old attendance/deduction history without allowing new imports or deductions.

### Connector Testing Requirements

Tests should prove the connector boundaries work.

Required tests:

```text
preview mode does not change LeaveBalance
preview mode does not create Leave records
apply blocked when ATTENDANCE_ALLOW_APPLY_DEDUCTIONS=False
module disabled hides/blocks attendance routes
leave workflows still work when attendance disabled
LeaveBalanceAdapter applies Earned first, Sick second
LeaveRecordAdapter creates approved rows only when allowed
HolidayWfhAdapter excludes approved leave/WFH/holiday/weekend
PermissionAdapter blocks employee access to other employees
AuditAdapter logs high-risk actions
```

### Connector Acceptance Criteria

The connector architecture is accepted only when:

```text
attendance has a clear module boundary
feature flags can disable risky behavior
preview-only mode is the default first release state
real apply uses adapters, not scattered direct writes
existing leave system works with attendance disabled
all attendance-to-leave writes are auditable
future biometric sync can plug into the same attendance record/service path
```

### Implementation Order Update

Before building real deduction apply, implement in this order:

```text
1. Add feature flags/default settings.
2. Add module boundary and adapter interfaces.
3. Build preview-only attendance models/services.
4. Build classification and deduction preview without leave writes.
5. Build HR/admin preview UI.
6. Build tests proving no balance/leave writes in preview mode.
7. Build LeaveBalanceAdapter and LeaveRecordAdapter behind apply flags.
8. Enable manual apply only after preview workflows are verified.
9. Keep auto deduction disabled until later milestone.
```

### Final Connector Rule

Attendance can connect to leave, but leave must not become dependent on attendance.

Attendance is a controlled connector module:

```text
safe to preview
safe to disable
safe to audit
safe to extend
safe to remove from active navigation
```

## Attendance Notification Orchestration Specification

Notifications for attendance must be handled as a first-class part of the system.

The system should notify employees, HR, and admins for important attendance lifecycle events through in-app notifications and optionally email, based on admin configuration.

### Notification Principles

```text
1. Important attendance changes should be visible in-app.
2. Email should be configurable and not hard-coded for every event.
3. Employees must be notified when something affects their attendance status, request status, or leave balance.
4. HR/admin must be notified when something needs review or action.
5. Admin must be notified for high-risk configuration, automation, and failure events.
6. Notifications should not be duplicated unnecessarily.
7. Notification delivery should be audited.
8. Failed email delivery should not roll back attendance/deduction transactions unless explicitly required.
```

### Notification Channels

Supported channels:

```text
in_app
email
future_push
future_webhook
```

Version 1 should support:

```text
in_app
email if existing project email system can be reused safely
```

Future channels can reuse the same notification event model/service.

### Recipient Groups

Recipient groups:

```text
employee
HR users
admin users
reviewer/actor
custom configured emails
attendance managers
payroll recipients future
```

Rules:

```text
Employee notifications must go only to the affected employee.
HR/admin review notifications should go to configured attendance reviewers.
Admin-only alerts should not be sent to ordinary employees.
Custom email recipients should be configured, not hard-coded.
```

### Employee Notification Events

Employees should receive notifications for:

```text
attendance record created for them
attendance record corrected
warning-only late recorded
counted late mark recorded
late mark allowed/excused
deduction preview generated for them
deduction applied to their leave balance
Unpaid/LOP shortage applied
negative balance applied
correction/exception request submitted
correction/exception request approved
correction/exception request rejected
correction/exception request cancelled
attendance period locked with their applied deduction
reversal/adjustment applied for their record
employee-specific schedule/grant created
employee-specific schedule/grant changed
employee-specific schedule/grant ended
```

High-priority employee events:

```text
deduction applied
Unpaid/LOP applied
negative balance applied
request approved/rejected
reversal/adjustment applied
```

Default recommendation:

```text
High-priority employee events -> in-app + email if enabled.
Warning-only and counted late -> in-app immediately, email configurable or digest.
```

### HR Notification Events

HR users should receive notifications for:

```text
attendance import completed
attendance import failed
attendance import has unmatched rows
attendance import has duplicate conflicts
attendance import has invalid rows
manual attendance entry created by another actor
employee correction/exception request submitted
employee request awaiting review beyond SLA
late records needing review
deduction preview generated
deduction run ready to apply
deduction apply completed
deduction apply partially failed
records blocked from auto deduction
employee deduction hold created/released
period lock/unlock requested
reversal/adjustment requested or applied
```

Default recommendation:

```text
Action-required HR events -> in-app + email if enabled.
Bulk summary events -> email summary/digest if enabled.
```

### Admin Notification Events

Admins should receive notifications for high-risk and system-level events:

```text
policy created/changed/backdated
policy overlap/conflict detected
automation enabled/disabled
auto deduction run completed
auto deduction run failed
auto deduction readiness check failed
biometric sync failed future
period locked/unlocked
reversal/adjustment applied
large bulk overwrite performed
source trust setting changed
feature flag changed if DB-backed
email delivery failures above threshold
scheduler/background job failure
```

Default recommendation:

```text
System/high-risk admin events -> in-app + email if enabled.
Failures and policy conflicts should be high priority.
```

### Notification Configuration

Admin should be able to configure attendance notifications.

Suggested settings:

```text
enable attendance notifications: yes/no
enable attendance emails: yes/no
employee warning late notification: immediate/digest/off
employee counted late notification: immediate/digest/off
employee deduction preview notification: immediate/off
employee deduction applied notification: immediate/off
employee request decision notification: immediate/off
HR import summary notification: immediate/digest/off
HR unmatched/invalid row notification: immediate/off
HR correction request notification: immediate/off
HR deduction ready notification: immediate/off
admin policy change notification: immediate/off
admin automation failure notification: immediate/off
admin high-risk action notification: immediate/off
```

Digest frequencies:

```text
daily
weekly
monthly future
```

Digest should support:

```text
employee late summary digest
HR import/review summary digest
admin system/failure summary digest
```

### Notification Templates

Templates should be configurable later, with safe defaults first.

Template types:

```text
employee_warning_late
employee_counted_late
employee_late_excused
employee_deduction_preview
employee_deduction_applied
employee_lop_applied
employee_request_approved
employee_request_rejected
employee_schedule_grant_changed
hr_import_completed
hr_import_errors
hr_request_submitted
hr_deduction_ready
admin_policy_changed
admin_auto_run_failed
admin_high_risk_action
```

Template placeholders should be controlled:

```text
employee_name
date
check_in_time
late_status
period_start
period_end
counted_late_marks
deduction_days
earned_deducted
sick_deducted
unpaid_lop_amount
request_status
reviewer_name
run_reference
policy_name
```

Rules:

```text
Broken/custom template should fall back to a safe default.
Template edits should be audited.
Do not allow unsafe HTML/script injection in templates.
```

### Notification Payload Requirements

Each notification should store enough context to open the right page.

Common payload fields:

```text
notification_type
recipient
actor
employee
attendance_record
deduction_run
correction_request
policy_version
severity
title
message
target_url
created_at
read_at
email_status
```

Target URLs examples:

```text
employee attendance page with highlighted record
employee my_leave approved section with highlighted deduction
HR attendance management requests tab
HR attendance management import batch preview
HR attendance management deduction run detail
admin policy settings history
```

### Notification Severity

Severity levels:

```text
info
success
warning
error
critical
action_required
```

Examples:

```text
warning-only late -> warning
counted late -> warning
deduction applied -> action_required or warning
request approved -> success
request rejected -> warning
import failed -> error
auto run failed -> critical
policy conflict -> critical
```

### Deduplication Rules

Avoid notification spam.

Deduplication keys should include:

```text
notification_type
recipient
attendance_record or deduction_run or request id
status/event version
```

Rules:

```text
Do not send duplicate notification for the same unchanged event.
If event changes meaningfully, send a new notification.
Bulk events can send one summary instead of hundreds of separate HR/admin emails.
Employee-impact events may still be per employee.
```

### Notification Audit And Logs

Every sent/attempted notification should be logged.

Log fields:

```text
notification event
recipient
channel
status: pending/sent/failed/skipped
attempt_count
last_attempt_at
error_message
related record/run/request
created_by system/actor
```

Rules:

```text
Email failure should be visible in Logs tab.
Failed email can be retried by admin if supported.
In-app notification creation failure should be logged as application error.
```

### Notification And Transaction Safety

Rules:

```text
Create important in-app notification after transaction commit where possible.
Do not send email before database transaction commits.
If email fails, do not roll back already-applied deduction.
Record email failure and allow retry.
```

### Notification Adapter Requirement

Attendance notification logic must go through NotificationAdapter.

Hard rule:

```text
Views and deduction services should not directly send emails from random places.
They should emit notification events through NotificationAdapter.
```

NotificationAdapter should:

```text
check module/notification flags
check event configuration
create in-app notification
queue email using existing email system if enabled
log status
return delivery summary
```

### Example Employee Notifications

Warning-only late:

```text
Title: Attendance Warning Recorded
Message: Your check-in on 2026-07-10 at 10:22 AM is within the warning window and will not count for deduction.
Target: Employee attendance page, highlighted date.
```

Counted late:

```text
Title: Late Mark Recorded
Message: Your check-in on 2026-07-10 at 10:45 AM is counted as a late mark under the active attendance policy.
Target: Employee attendance page.
```

Deduction applied:

```text
Title: Late Coming Deduction Applied
Message: 0.5 day has been deducted for 3 counted late marks from 2026-07-01 to 2026-07-31. See My Leave approved records for details.
Target: my_leave Approved section or employee attendance deduction detail.
```

Request approved:

```text
Title: Late Exception Approved
Message: Your exception request for 2026-07-10 was approved. This late mark will not count for deduction.
Target: Employee attendance request detail.
```

Request rejected:

```text
Title: Late Exception Rejected
Message: Your exception request for 2026-07-10 was rejected. The record remains counted according to policy.
Target: Employee attendance request detail.
```

### Example HR/Admin Notifications

Import errors:

```text
Title: Attendance Import Needs Review
Message: Import batch IMP-2026-07-001 has 12 unmatched rows and 4 duplicate conflicts.
Target: Attendance Management -> Import tab.
```

Deduction ready:

```text
Title: Late Deduction Preview Ready
Message: Monthly deduction preview for July 2026 is ready with 18 employees affected and 3 blocked records.
Target: Attendance Management -> Deductions tab.
```

Auto run failed:

```text
Title: Attendance Auto Deduction Failed
Message: Auto deduction for July 2026 failed because policy overlap was detected. No deductions were applied.
Target: Attendance Management -> Logs tab.
```

### Notification Testing Requirements

Required tests:

```text
employee receives in-app notification for counted late
employee receives notification when deduction applied
employee receives request approved/rejected notification
HR receives notification for import errors
HR receives correction request notification
admin receives policy conflict/auto-run failure notification
email disabled means no email queued
email enabled queues expected email
preview mode does not send deduction-applied notification
duplicate events do not create duplicate notifications
email failure is logged without rolling back deduction
```

### Notification Acceptance Criteria

The notification system is accepted when:

```text
all major employee-impacting events create in-app notification
email behavior is admin configurable
HR/admin action-required events are visible
notification target URLs open the correct page/tab/detail
email send attempts are logged
notification spam is controlled by deduplication/digest settings
all notification sending goes through NotificationAdapter
```


## Final Deep Scan Enterprise Additions

This section captures the final gaps found after another deep review for total-control enterprise readiness.

These additions do not replace earlier decisions. They strengthen the implementation blueprint so edge cases do not get discovered too late.

### 1. Organization Hierarchy And Manager Visibility

Attendance decisions may involve reporting managers, HR, admins, and payroll teams.

The system should be future-ready for organization hierarchy.

Possible hierarchy fields/sources:

```text
reporting_manager
department_head
hr_partner
location_admin
payroll_owner
```

Manager visibility rules:

```text
Employee sees only own attendance.
Manager can optionally see direct report attendance summaries if enabled.
HR can see employees assigned to HR scope or all employees depending on project roles.
Admin can see all.
Payroll can see payroll-impact reports if payroll role is added later.
```

Approval routing can later use hierarchy:

```text
employee request -> reporting manager optional -> HR -> admin for high-risk cases
```

Version 1 rule:

```text
Do not block implementation on manager workflow unless the existing project already has manager roles.
But data/services should not prevent manager-based approval later.
```

### 2. Employee Lifecycle And Eligibility Rules

Attendance policy may differ by employee lifecycle state.

Employee states to consider:

```text
new joiner
probation
confirmed employee
contractor/intern
notice period
inactive employee
terminated/resigned employee
on long leave
```

Rules:

```text
Inactive employees should not receive new attendance imports unless explicitly allowed.
Attendance imports for unknown/inactive employees should be flagged.
Employee joining date should prevent attendance before joining date unless backfill is approved.
Exit date should prevent attendance after exit date unless correction/backfill is approved.
Policy assignment should be valid for employee lifecycle state.
```

Reports should be able to filter:

```text
active employees only
inactive employees included
employees with lifecycle exceptions
```

### 3. Attendance Regularization Request Types

Correction/exception requests should be more specific than a generic request.

Supported employee request types should include:

```text
missed check-in
missed check-out
wrong check-in time
wrong check-out time
late exception / allow late
official duty / client visit
field work
travel delay approved by HR
medical reason
biometric issue
work from home correction
holiday/weekend correction
other
```

Each request type may need different fields.

Examples:

```text
Missed check-in -> requested check-in time required.
Missed check-out -> requested check-out time required.
Late exception -> reason required, time change optional.
Official duty -> location/client/project details optional.
Medical reason -> attachment optional/required by config.
```

Rules:

```text
Admin should be able to configure which request types are enabled.
Request type should be shown in HR/admin review, reports, and notification templates.
```

### 4. Cutoff Dates, SLA, And Payroll Freeze Rules

Enterprise control needs deadlines.

Configurable cutoffs should include:

```text
employee correction request cutoff after attendance date
HR/admin review cutoff before payroll close
deduction preview generation cutoff
payroll freeze date
period lock date
auto deduction run date/time
```

Examples:

```text
Employee can request correction within 3 days of attendance date.
HR must review pending requests before monthly deduction apply.
After payroll freeze, corrections require admin adjustment.
```

SLA tracking should show:

```text
request pending age
requests nearing cutoff
requests overdue
HR/admin reviewer assigned
escalation status
```

Rules:

```text
Cutoff violations should not silently disappear.
They should show as blocked or require admin override with reason.
```

### 5. Location, Device, IP, And Geo Trust Foundation

Future attendance may come from mobile/web/biometric sources where location or device matters.

Future-ready fields:

```text
location_name
site_id
device_id
device_trust_level
ip_address
geo_latitude
geo_longitude
geo_accuracy
network_source
```

Possible controls:

```text
allowed office locations
allowed IP ranges
trusted biometric devices
trusted upload sources
mobile location required yes/no
geo fence radius future
```

Rules:

```text
Version 1 does not need geofencing.
But source/location/device metadata should be possible without redesign.
Untrusted source/location should require review and should not auto-deduct.
```

### 6. Attendance Source Conflict Policy

The plan already has source trust and duplicate handling, but final conflict policy should be explicit.

Conflict examples:

```text
manual entry says 10:10, biometric says 10:45
CSV says present, biometric says absent
employee correction says 10:05, existing record says 11:00
file upload changes already-reviewed record
```

Conflict resolution should show:

```text
current final value
incoming value
source priority
who created each value
when each value was created
related request/import batch
recommended action
```

Rules:

```text
Conflicts must not auto-apply deduction.
HR/admin must resolve conflict or keep it blocked.
Chosen final value must be audited.
```

### 7. Import Cancel, Rollback, And Quarantine

Import safety should include more than duplicate detection.

Import states should include:

```text
uploaded
previewed
quarantined
finalized
partially_finalized
cancelled
rolled_back
failed
```

Quarantine should be used when:

```text
file has too many invalid rows
file appears duplicated
file has suspicious format
file has unexpected columns
file includes inactive/unknown employees
file conflicts with locked period
```

Rollback rules:

```text
Before finalization: batch can be cancelled safely.
After finalization but before deduction: rollback can void created attendance records if no downstream impact exists.
After deduction: rollback must use adjustment/reversal flow, not delete records silently.
```

Audit must record:

```text
cancelled_by
cancelled_at
rollback_by
rollback_at
rollback_reason
records affected
downstream impact check
```

### 8. Service Console And Management Command Hooks

The project already has management/operational command patterns. Attendance should provide safe service-console hooks for production operations.

Possible management commands:

```text
attendance_health_check
attendance_seed_default_policy
attendance_import_file --preview-only
attendance_recalculate_preview --period
attendance_reconcile_period --period
attendance_find_conflicts --period
attendance_export_report --period
attendance_send_digest --date
attendance_unlock_period --period --reason
attendance_apply_scheduled_runs --dry-run
```

Rules:

```text
Commands that can change data must support --dry-run where practical.
Dangerous commands must require explicit confirmation arguments.
Commands must log output and errors.
Commands must respect feature flags.
Commands must never bypass adapter safety gates.
```

Service console should show:

```text
attendance module enabled/disabled
preview-only state
pending import batches
failed imports
pending requests
pending deduction previews
last auto run
policy conflicts
scheduler readiness
```

### 9. Data Quality Score And Readiness Dashboard

Enterprise systems benefit from a readiness score before deduction or payroll close.

Data quality metrics:

```text
matched row percentage
unmatched row count
invalid row count
duplicate conflict count
missing check-in count
missing check-out count
pending correction request count
late records needing review
policy conflict count
source trust warnings
```

Readiness levels:

```text
Ready
Ready with warnings
Needs review
Blocked
```

Rules:

```text
Auto deduction requires Ready status.
Manual apply can allow Ready with warnings if HR/admin confirms.
Blocked status prevents apply until resolved or admin override is recorded.
```

### 10. Support And Investigation Tools

HR/admin needs tools to answer “why did this happen?” quickly.

Every attendance/deduction detail page should support investigation trail:

```text
raw import row
matched employee method
policy used
employee-specific schedule used
classification reason
source conflict history
exception/correction request history
notification history
leave deduction split
leave record links
audit trail
```

Suggested “Why?” panel:

```text
Why was this counted late?
Why was this excluded?
Why was this deduction amount calculated?
Why was this record blocked from auto apply?
```

Rules:

```text
A reviewer should not need database access to explain a deduction.
The UI should expose enough traceability for HR/admin support.
```

### 11. Large Organization Bulk Controls

For large teams, HR/admin needs safe bulk controls.

Bulk filters:

```text
department
location
shift
manager
employee group
source
status
period
policy version
```

Bulk operations:

```text
bulk mark allowed/excused
bulk assign employee schedule
bulk put deductions on hold
bulk release deduction hold
bulk export selected records
bulk send reminders
bulk resolve duplicate action when safe
```

Rules:

```text
Bulk operations must show affected count and sample rows.
Bulk operations must require confirmation.
High-risk bulk operations must require reason.
Bulk operations must create parent audit plus per-record audit.
```

### 12. Employee Communication And Self-Service Clarity

Employee pages should explain records clearly without exposing internal-only remarks.

Employee-facing fields:

```text
status
check-in/check-out
policy timing used
whether it counts for deduction
request button if allowed
request deadline
request status
public HR/admin remarks
```

Internal-only fields:

```text
admin risk notes
source trust score
internal investigation notes
payroll processing comments
private HR remarks
```

Rules:

```text
Keep internal HR/admin remarks separate from employee-visible text.
Employee should see enough to understand what happened and how to request correction.
```

### 13. Report Certification And Sign-Off

Before payroll or final monthly close, HR/admin may need to certify attendance reports.

Certification fields:

```text
period
certified_by
certified_at
certification_remarks
report_snapshot
exception_count at certification
pending_count at certification
```

Rules:

```text
Certification should snapshot report totals.
Changes after certification should require unlock/adjustment or recertification.
```

### 14. Final Deep Scan Status

After this final scan, the plan covers:

```text
policy control
employee-specific control
manual/file/biometric source control
preview safety
adapter connector architecture
notifications
reports
audit
permissions
enterprise governance
operations/service console
rollback and quarantine
data quality readiness
support investigation tools
bulk controls
employee communication clarity
report certification
```

Remaining before coding is not more planning detail. It is implementation discovery:

```text
inspect existing user/profile fields
inspect existing role/permission model
inspect existing notification/email system
inspect existing leave balance update logic
inspect existing report/export helpers
inspect existing service_console/management command patterns
inspect existing WFH/holiday helpers
choose module structure
choose Version 1 implementation slice
```

If new requirements appear during implementation discovery, this plan should be updated before code is changed.
