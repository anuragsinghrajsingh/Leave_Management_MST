from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from App.models import (
    AdminAuditLog,
    Communication,
    Leave,
    LeaveBalance,
    LeaveBalanceAudit,
    LeaveNotificationRead,
    LeaveNotificationSeen,
)
from App.services.email_delivery_log import record_email_delivery
from App.services.leave_breakdown import calculate_leave_breakdown_for_leave


BALANCE_FIELDS = (
    "total_leave_balance",
    "total_leave_remaining",
    "sick_total",
    "sick_used",
    "earned_total",
    "earned_used",
    "unpaid",
)


def get_leave_admin_preview(leaves, workflow_action="sync"):
    leaves = list(leaves)
    expected_by_user = _expected_balances_for_leaves(leaves, workflow_action)
    preview = []
    for leave in leaves:
        balance = getattr(leave.user, "leavebalance", None)
        expected = expected_by_user.get(leave.user_id, {})
        preview.append({
            "id": leave.id,
            "employee": leave.user.get_full_name().strip() or leave.user.username,
            "leave_type": leave.leave_type,
            "status": leave.status,
            "date_range": _format_leave_range(leave),
            "deducted_from": leave.deducted_from,
            "value": _get_leave_value(leave),
            "current_balance": _balance_snapshot(balance) if balance else {},
            "expected_balance": expected,
        })
    return preview


def approve_selected_leaves(leave_ids, actor, reason, options):
    results = []
    affected_user_ids = set()
    with transaction.atomic():
        leaves = _locked_leaves(leave_ids)
        for leave in leaves:
            old = _leave_snapshot(leave)
            if leave.status != "Pending":
                results.append(f"Skipped leave #{leave.id}: only pending leave can be approved.")
                continue

            leave.status = "Approved"
            leave.approved_at = timezone.now()
            leave.rejected_at = None
            leave.reviewed_by = actor
            leave.save(
                update_fields=["status", "approved_at", "rejected_at", "reviewed_by"],
                skip_validation=True,
            )
            affected_user_ids.add(leave.user_id)
            _create_leave_admin_audit(actor, leave, "ADMIN_APPROVE", reason, old, _leave_snapshot(leave))
            _apply_notification_options(leave, actor, options, "approved", reason)
            results.append(f"Approved leave #{leave.id}.")

        _recalculate_many(affected_user_ids, actor, reason, "Admin approve workflow")

    results.extend(_send_leave_workflow_emails(leaves, actor, "approved", options))
    results.append(_summarize_options(options, len(leaves)))
    return results


def reject_selected_leaves(leave_ids, actor, reason, rejection_reason, options):
    results = []
    affected_user_ids = set()
    with transaction.atomic():
        leaves = _locked_leaves(leave_ids)
        for leave in leaves:
            old = _leave_snapshot(leave)
            if leave.status != "Pending":
                results.append(f"Skipped leave #{leave.id}: only pending leave can be rejected.")
                continue

            leave.status = "Rejected"
            leave.rejection_reason = rejection_reason
            leave.rejected_at = timezone.now()
            leave.approved_at = None
            leave.reviewed_by = actor
            leave.save(
                update_fields=[
                    "status",
                    "rejection_reason",
                    "rejected_at",
                    "approved_at",
                    "reviewed_by",
                ],
                skip_validation=True,
            )
            affected_user_ids.add(leave.user_id)
            _create_leave_admin_audit(actor, leave, "ADMIN_REJECT", reason, old, _leave_snapshot(leave))
            _apply_notification_options(leave, actor, options, "rejected", reason)
            results.append(f"Rejected leave #{leave.id}.")

        _recalculate_many(affected_user_ids, actor, reason, "Admin reject workflow")

    results.extend(_send_leave_workflow_emails(leaves, actor, "rejected", options))
    results.append(_summarize_options(options, len(leaves)))
    return results


def sync_selected_leaves(leave_ids, actor, reason, options):
    results = []
    with transaction.atomic():
        leaves = _locked_leaves(leave_ids)
        affected_user_ids = {leave.user_id for leave in leaves}
        for leave in leaves:
            _create_leave_admin_audit(
                actor,
                leave,
                "ADMIN_SYNC",
                reason,
                None,
                {"synced_leave": _leave_snapshot(leave), "options": options},
            )
            _apply_notification_options(leave, actor, options, "updated", reason)
            results.append(f"Synced leave #{leave.id}.")

        _recalculate_many(affected_user_ids, actor, reason, "Admin sync workflow")

    results.extend(_send_leave_workflow_emails(leaves, actor, "updated", options))
    results.append(_summarize_options(options, len(leaves)))
    return results


def delete_selected_leaves_with_workflow(leave_ids, actor, reason, options):
    results = []
    email_snapshots = []
    with transaction.atomic():
        leaves = _locked_leaves(leave_ids)
        affected_user_ids = {leave.user_id for leave in leaves}
        for leave in leaves:
            snapshot = _leave_snapshot(leave)
            email_snapshots.append((leave.user.email, snapshot))
            _create_leave_admin_audit(actor, leave, "ADMIN_DELETE_WF", reason, snapshot, None)
            results.append(f"Deleted leave #{leave.id}.")
        for leave in leaves:
            leave.delete()
        _recalculate_many(affected_user_ids, actor, reason, "Admin delete workflow")

    results.extend(_send_delete_emails(email_snapshots, actor, options))
    _create_delete_communications(email_snapshots, actor, options)
    results.append(_summarize_options(options, len(email_snapshots)))
    return results


def recalculate_balances_for_selected_leaves(leave_ids, actor, reason):
    with transaction.atomic():
        user_ids = set(
            Leave.objects.filter(id__in=leave_ids).values_list("user_id", flat=True)
        )
        return _recalculate_many(user_ids, actor, reason, "Admin balance recalculation")


def recalculate_employee_balance(user, actor, reason, source):
    balance, _ = LeaveBalance.objects.select_for_update().get_or_create(user=user)
    old = _balance_snapshot(balance)

    active_leaves = Leave.objects.filter(user=user, status__in=["Pending", "Approved"])
    sick_used = 0.0
    earned_used = 0.0
    unpaid = 0.0

    for leave in active_leaves:
        value = _get_leave_value(leave)
        if leave.leave_type == "Sick":
            sick_used += value
        elif leave.leave_type == "Earned":
            earned_used += value
        elif leave.leave_type == "Unpaid":
            unpaid += value
        elif leave.leave_type in ["Short", "Half"]:
            if leave.deducted_from == "Sick":
                sick_used += value
            elif leave.deducted_from == "Earned":
                earned_used += value
            elif leave.deducted_from == "Unpaid":
                unpaid += value

    balance.sick_used = round(sick_used, 2)
    balance.earned_used = round(earned_used, 2)
    balance.unpaid = round(unpaid, 2)
    balance.total_leave_remaining = max(
        float(balance.total_leave_balance or 0) - balance.sick_used - balance.earned_used,
        0,
    )
    balance.save()

    new = _balance_snapshot(balance)
    changes = {
        field: {"old": old[field], "new": new[field]}
        for field in BALANCE_FIELDS
        if old[field] != new[field]
    }
    if changes:
        LeaveBalanceAudit.objects.create(
            balance=balance,
            employee=user,
            updated_by=actor,
            reason=f"{source}: {reason}",
            changes=changes,
        )
    return f"Recalculated balance for {user.username}."


def _expected_balances_for_leaves(leaves, workflow_action):
    expected = {}
    selected_ids = {leave.id for leave in leaves}
    user_ids = {leave.user_id for leave in leaves}
    users = {
        user.id: user
        for user in get_user_model().objects.filter(id__in=user_ids).select_related("leavebalance")
    }
    for user_id, user in users.items():
        expected[user_id] = _calculate_expected_balance(user, selected_ids, workflow_action)
    return expected


def _calculate_expected_balance(user, selected_ids, workflow_action):
    balance = getattr(user, "leavebalance", None)
    total_leave_balance = float(getattr(balance, "total_leave_balance", 27) or 0)
    active_statuses = {"Pending", "Approved"}
    sick_used = 0.0
    earned_used = 0.0
    unpaid = 0.0

    for leave in Leave.objects.filter(user=user).order_by("id"):
        effective_status = leave.status
        if leave.id in selected_ids:
            if workflow_action == "approve":
                effective_status = "Approved"
            elif workflow_action in {"reject", "delete"}:
                effective_status = "Rejected"

        if effective_status not in active_statuses:
            continue

        value = _get_leave_value(leave)
        if leave.leave_type == "Sick":
            sick_used += value
        elif leave.leave_type == "Earned":
            earned_used += value
        elif leave.leave_type == "Unpaid":
            unpaid += value
        elif leave.leave_type in ["Short", "Half"]:
            if leave.deducted_from == "Sick":
                sick_used += value
            elif leave.deducted_from == "Earned":
                earned_used += value
            elif leave.deducted_from == "Unpaid":
                unpaid += value

    return {
        "total_leave_remaining": round(max(total_leave_balance - sick_used - earned_used, 0), 2),
        "sick_used": round(sick_used, 2),
        "earned_used": round(earned_used, 2),
        "unpaid": round(unpaid, 2),
    }


def _recalculate_many(user_ids, actor, reason, source):
    User = get_user_model()
    results = []
    for user in User.objects.select_for_update().filter(id__in=user_ids):
        results.append(recalculate_employee_balance(user, actor, reason, source))
    return results


def _locked_leaves(leave_ids):
    return list(
        Leave.objects.select_for_update()
        .select_related("user")
        .filter(id__in=leave_ids)
        .order_by("id")
    )


def _get_leave_value(leave):
    if leave.leave_type == "Short":
        return 0.25
    if leave.leave_type == "Half":
        return 0.5
    return float(calculate_leave_breakdown_for_leave(leave)["working_days"] or 0)


def _balance_snapshot(balance):
    return {field: getattr(balance, field) for field in BALANCE_FIELDS}


def _leave_snapshot(leave):
    return {
        "id": leave.id,
        "user_id": leave.user_id,
        "employee": leave.user.username,
        "leave_type": leave.leave_type,
        "status": leave.status,
        "from_date": leave.from_date.isoformat() if leave.from_date else None,
        "to_date": leave.to_date.isoformat() if leave.to_date else None,
        "deducted_from": leave.deducted_from,
        "rejection_reason": leave.rejection_reason,
    }


def _create_leave_admin_audit(actor, leave, action, reason, old, new):
    AdminAuditLog.objects.create(
        model_label=leave._meta.label,
        object_id=str(leave.pk),
        object_repr=str(leave),
        action=action,
        updated_by=actor,
        reason=reason,
        changes={"admin_leave_workflow": {"old": old, "new": new}},
    )


def log_workflow_skipped(leave_ids, actor, workflow_action, reason="Admin skipped workflow confirmation."):
    leaves = Leave.objects.select_related("user").filter(id__in=leave_ids).order_by("id")
    count = 0
    for leave in leaves:
        AdminAuditLog.objects.create(
            model_label=leave._meta.label,
            object_id=str(leave.pk),
            object_repr=str(leave),
            action="ADMIN_WORKFLOW_SKIPPED",
            updated_by=actor,
            reason=reason,
            changes={
                "admin_leave_workflow_skipped": {
                    "old": None,
                    "new": {
                        "workflow_action": workflow_action,
                        "leave": _leave_snapshot(leave),
                    },
                }
            },
        )
        count += 1
    return f"Skipped admin workflow actions for {count} leave(s). Audit recorded."


def _apply_notification_options(leave, actor, options, action_label, admin_reason):
    if options.get("employee_notification"):
        LeaveNotificationRead.objects.filter(user=leave.user, leave=leave).delete()
        LeaveNotificationSeen.objects.filter(user=leave.user, leave=leave).delete()

    if options.get("employee_message"):
        _create_employee_communication(actor, leave, action_label, admin_reason)

    if options.get("hr_notification"):
        hr_ids = get_user_model().objects.filter(role="HR", is_active=True).values_list("id", flat=True)
        LeaveNotificationRead.objects.filter(user_id__in=hr_ids, leave=leave).delete()
        LeaveNotificationSeen.objects.filter(user_id__in=hr_ids, leave=leave).delete()
        _create_hr_communication(actor, leave, action_label, admin_reason)


def _create_employee_communication(actor, leave, action_label, admin_reason):
    leave_value = _get_leave_value(leave)
    requested_range = _format_requested_leave_range(leave)
    effective_range = _format_leave_range(leave)
    lines = [
        f"Admin {actor.username} {action_label} leave #{leave.id}.",
        "",
        f"Leave type: {leave.leave_type}",
        f"Status: {leave.status}",
        f"Requested date: {requested_range}",
        f"Effective date: {effective_range}",
        f"Deducted from: {leave.deducted_from or 'Not set'}",
        f"Leave value: {leave_value:g} day(s)",
        f"Employee reason: {leave.reason or 'Not provided'}",
    ]
    if leave.rejection_reason:
        lines.append(f"Rejection reason: {leave.rejection_reason}")
    lines.append(f"Admin reason: {admin_reason or 'Not provided'}")

    Communication.objects.create(
        sender=actor,
        recipient=leave.user,
        message_type="DIRECT",
        title=f"Admin leave {action_label}: {leave.leave_type} - {leave.status}",
        body="\n".join(lines),
    )


def _create_hr_communication(actor, leave, action_label, admin_reason):
    leave_value = _get_leave_value(leave)
    employee_name = leave.user.get_full_name().strip() or leave.user.username
    body = (
        f"Admin {actor.username} {action_label} leave #{leave.id} for {employee_name}.\n\n"
        f"Leave type: {leave.leave_type}\n"
        f"Status: {leave.status}\n"
        f"Date: {_format_leave_range(leave)}\n"
        f"Deducted from: {leave.deducted_from}\n"
        f"Leave value: {leave_value:g} day(s)\n"
        f"Admin reason: {admin_reason or 'Not provided'}"
    )
    title = f"Admin leave {action_label}: {employee_name} - {leave.leave_type} {leave.status}"
    hr_users = get_user_model().objects.filter(role="HR", is_active=True)
    for hr_user in hr_users:
        Communication.objects.create(
            sender=actor,
            recipient=hr_user,
            message_type="DIRECT",
            title=title,
            body=body,
        )


def _create_delete_communications(email_snapshots, actor, options):
    if not options.get("employee_message"):
        return
    User = get_user_model()
    usernames = [snapshot["employee"] for _, snapshot in email_snapshots]
    users_by_username = {user.username: user for user in User.objects.filter(username__in=usernames)}
    for _, snapshot in email_snapshots:
        user = users_by_username.get(snapshot["employee"])
        if not user:
            continue
        date_range = _format_snapshot_date_range(snapshot)
        body = (
            f"Admin {actor.username} deleted leave #{snapshot['id']}.\n\n"
            f"Leave type: {snapshot['leave_type']}\n"
            f"Previous status: {snapshot['status']}\n"
            f"Date: {date_range}\n"
            f"Deducted from: {snapshot['deducted_from'] or 'Not set'}\n"
            f"Rejection reason: {snapshot['rejection_reason'] or 'Not provided'}"
        )
        Communication.objects.create(
            sender=actor,
            recipient=user,
            message_type="DIRECT",
            title="Leave record deleted by admin",
            body=body,
        )


def _send_leave_workflow_emails(leaves, actor, action_label, options):
    results = []
    for leave in leaves:
        recipients = []
        if options.get("notify_employee") and leave.user.email:
            recipients.append(leave.user.email)
        if options.get("notify_hr"):
            recipients.extend(_hr_emails())
        if options.get("record_email") and settings.LEAVE_RECORD_EMAIL:
            recipients.append(settings.LEAVE_RECORD_EMAIL)
        recipients = list(dict.fromkeys([email for email in recipients if email]))
        if recipients:
            try:
                _send_admin_leave_email(
                    recipients,
                    f"Admin leave {action_label}: {leave.leave_type}",
                    {
                        "title": f"Leave {action_label.title()}",
                        "intro_text": f"Admin {actor.username} {action_label} a leave record.",
                        "employee_name": leave.user.get_full_name().strip() or leave.user.username,
                        "leave_type": leave.leave_type,
                        "date_range": _format_leave_range(leave),
                        "reviewed_by": actor.get_full_name().strip() or actor.username,
                        "status_label": leave.status,
                        "status_class": leave.status.lower(),
                        "reason": leave.rejection_reason or "",
                        "portal_link": f"{settings.PORTAL_BASE_URL}/" if settings.PORTAL_BASE_URL else "",
                    },
                )
            except Exception as exc:
                record_email_delivery(
                    subject=f"Admin leave {action_label}: {leave.leave_type}",
                    recipients=recipients,
                    status="failed",
                    email_type=f"admin_leave_{action_label}",
                    from_email=f"HR Portal <{settings.LEAVE_RECORD_EMAIL or settings.DEFAULT_FROM_EMAIL}>",
                    error_message=str(exc),
                    related_user=leave.user,
                    related_leave=leave,
                    triggered_by=actor,
                )
                AdminAuditLog.objects.create(
                    model_label=leave._meta.label,
                    object_id=str(leave.pk),
                    object_repr=str(leave),
                    action="ADMIN_EMAIL_FAIL",
                    updated_by=actor,
                    reason="Admin workflow email failed.",
                    changes={"recipients": recipients},
                )
                results.append(f"Email failed for leave #{leave.id}. Check Admin Audit.")
            else:
                record_email_delivery(
                    subject=f"Admin leave {action_label}: {leave.leave_type}",
                    recipients=recipients,
                    status="sent",
                    email_type=f"admin_leave_{action_label}",
                    from_email=f"HR Portal <{settings.LEAVE_RECORD_EMAIL or settings.DEFAULT_FROM_EMAIL}>",
                    related_user=leave.user,
                    related_leave=leave,
                    triggered_by=actor,
                )
                results.append(f"Email sent for leave #{leave.id} to {len(recipients)} recipient(s).")
    return results


def _send_delete_emails(email_snapshots, actor, options):
    results = []
    for employee_email, snapshot in email_snapshots:
        related_user = get_user_model().objects.filter(id=snapshot.get("user_id")).first()
        recipients = []
        if options.get("notify_employee") and employee_email:
            recipients.append(employee_email)
        if options.get("notify_hr"):
            recipients.extend(_hr_emails())
        if options.get("record_email") and settings.LEAVE_RECORD_EMAIL:
            recipients.append(settings.LEAVE_RECORD_EMAIL)
        recipients = list(dict.fromkeys([email for email in recipients if email]))
        if recipients:
            try:
                _send_admin_leave_email(
                    recipients,
                    f"Admin leave deleted: {snapshot['leave_type']}",
                    {
                        "title": "Leave Deleted",
                        "intro_text": f"Admin {actor.username} deleted a leave record.",
                        "employee_name": snapshot["employee"],
                        "leave_type": snapshot["leave_type"],
                        "date_range": f"{snapshot['from_date']} to {snapshot['to_date']}",
                        "reviewed_by": actor.get_full_name().strip() or actor.username,
                        "status_label": "Deleted",
                        "status_class": "rejected",
                        "reason": "",
                        "portal_link": f"{settings.PORTAL_BASE_URL}/" if settings.PORTAL_BASE_URL else "",
                    },
                )
            except Exception as exc:
                record_email_delivery(
                    subject=f"Admin leave deleted: {snapshot['leave_type']}",
                    recipients=recipients,
                    status="failed",
                    email_type="admin_leave_deleted",
                    from_email=f"HR Portal <{settings.LEAVE_RECORD_EMAIL or settings.DEFAULT_FROM_EMAIL}>",
                    error_message=str(exc),
                    related_user=related_user,
                    triggered_by=actor,
                    metadata={"leave_snapshot": snapshot},
                )
                AdminAuditLog.objects.create(
                    model_label="App.Leave",
                    object_id=str(snapshot["id"]),
                    object_repr=f"{snapshot['employee']} - {snapshot['leave_type']}",
                    action="ADMIN_EMAIL_FAIL",
                    updated_by=actor,
                    reason="Admin delete workflow email failed.",
                    changes={"recipients": recipients, "leave": snapshot},
                )
                results.append(f"Email failed for deleted leave #{snapshot['id']}. Check Admin Audit.")
            else:
                record_email_delivery(
                    subject=f"Admin leave deleted: {snapshot['leave_type']}",
                    recipients=recipients,
                    status="sent",
                    email_type="admin_leave_deleted",
                    from_email=f"HR Portal <{settings.LEAVE_RECORD_EMAIL or settings.DEFAULT_FROM_EMAIL}>",
                    related_user=related_user,
                    triggered_by=actor,
                    metadata={"leave_snapshot": snapshot},
                )
                results.append(f"Email sent for deleted leave #{snapshot['id']} to {len(recipients)} recipient(s).")
    return results


def _summarize_options(options, item_count):
    selected = [
        label
        for key, label in (
            ("notify_employee", "employee email"),
            ("notify_hr", "HR email"),
            ("record_email", "leave-record copy"),
            ("employee_message", "employee direct message"),
            ("employee_notification", "employee decision bell refresh"),
            ("hr_notification", "HR notification"),
        )
        if options.get(key)
    ]
    if not selected:
        return f"Workflow completed for {item_count} leave(s) with no email/notification options selected."
    return f"Workflow completed for {item_count} leave(s). Selected options: {', '.join(selected)}."


def _send_admin_leave_email(recipients, subject, context):
    html_content = render_to_string("emails/notification.html", context)
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=f"HR Portal <{settings.LEAVE_RECORD_EMAIL or settings.DEFAULT_FROM_EMAIL}>",
        to=recipients,
    )
    email.content_subtype = "html"
    email.send(fail_silently=False)


def _hr_emails():
    return list(
        get_user_model()
        .objects.filter(role="HR", is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _format_leave_range(leave):
    if leave.from_date == leave.to_date:
        return leave.from_date.strftime("%d %b %Y")
    return f"{leave.from_date.strftime('%d %b %Y')} to {leave.to_date.strftime('%d %b %Y')}"


def _format_requested_leave_range(leave):
    from_date = leave.requested_from_date or leave.from_date
    to_date = leave.requested_to_date or leave.to_date
    if from_date == to_date:
        return from_date.strftime("%d %b %Y")
    return f"{from_date.strftime('%d %b %Y')} to {to_date.strftime('%d %b %Y')}"


def _format_snapshot_date_range(snapshot):
    from_date = snapshot.get("from_date") or "-"
    to_date = snapshot.get("to_date") or "-"
    if from_date == to_date:
        return from_date
    return f"{from_date} to {to_date}"
