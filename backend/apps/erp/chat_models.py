from django.conf import settings
from django.db import models
from django.db.models import Q
from .models import TenantModel, private_path


class Conversation(TenantModel):
    kind = models.CharField(max_length=12, choices=[('direct', 'Privée'), ('group', 'Groupe'), ('mission', 'Mission')])
    title = models.CharField(max_length=150, blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mission = models.ForeignKey('Mission', null=True, blank=True, on_delete=models.PROTECT)
    direct_key = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)
    last_sequence = models.PositiveBigIntegerField(default=0)
    last_message_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-last_message_at', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'direct_key'], condition=Q(kind='direct'), name='erp_direct_pair_unique'),
            models.UniqueConstraint(fields=['organization', 'mission'], condition=Q(kind='mission'), name='erp_mission_chat_unique'),
        ]
        indexes = [models.Index(fields=['organization', '-last_message_at'])]


class ConversationParticipant(TenantModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    membership = models.ForeignKey('Membership', on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    last_read_sequence = models.PositiveBigIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation', 'membership'], name='erp_chat_participant_unique')]
        indexes = [models.Index(fields=['organization', 'membership', 'active'])]


class Message(TenantModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('Membership', on_delete=models.PROTECT)
    sequence = models.PositiveBigIntegerField()
    body = models.TextField(blank=True)
    client_id = models.UUIDField()
    class Meta:
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['conversation', 'sequence'], name='erp_chat_sequence_unique'),
            models.UniqueConstraint(fields=['conversation', 'sender', 'client_id'], name='erp_chat_retry_unique'),
        ]


class MessageAttachment(TenantModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=private_path)
    name = models.CharField(max_length=180)
    mime = models.CharField(max_length=40)
    size = models.PositiveIntegerField()


class GlobalNotification(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=128)
    category = models.CharField(max_length=20)
    title = models.CharField(max_length=180)
    body = models.CharField(max_length=500, blank=True)
    context = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    push_pending = models.BooleanField(default=False)
    push_attempts = models.PositiveSmallIntegerField(default=0)
    push_after = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'user', 'key'], name='erp_notification_event_unique')]
        indexes = [models.Index(fields=['organization', 'user', 'read_at', '-created_at']), models.Index(fields=['push_pending', 'push_after'])]


class NotificationPreference(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    messages = models.BooleanField(default=True)
    missions = models.BooleanField(default=True)
    operations = models.BooleanField(default=True)
    push = models.BooleanField(default=False)
    preview = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'user'], name='erp_notification_pref_unique')]


class PushSubscription(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    endpoint_hash = models.CharField(max_length=64)
    subscription = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['endpoint_hash'], name='erp_push_endpoint_unique')]
