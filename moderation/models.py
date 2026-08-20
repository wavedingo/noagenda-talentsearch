from django.db import models

from accounts.models import User


class Report(models.Model):
    class Reason(models.TextChoices):
        IMPERSONATION = "impersonation", "Impersonation"
        OFFENSIVE = "offensive", "Offensive content"
        SPAM = "spam", "Spam"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_filed")
    target_type = models.CharField(max_length=20)
    target_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)


class AdminAuditLog(models.Model):
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_actions")
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on {self.target_type}:{self.target_id}"
