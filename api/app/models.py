from django.db import models
import json

class LogFile(models.Model):
    name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class LogEntry(models.Model):
    LEVEL_CHOICES = [
        ('error', 'Error'),
        ('warn', 'Warning'),
        ('info', 'Info'),
        ('debug', 'Debug'),
        ('trace', 'Trace'),
    ]
    
    OPERATION_CHOICES = [
        ('plan', 'Plan'),
        ('apply', 'Apply'),
        ('validate', 'Validate'),
        ('init', 'Init'),
        ('destroy', 'Destroy'),
        ('refresh', 'Refresh'),
        ('general', 'General'),
    ]
    
    COMPONENT_CHOICES = [
        ('core', 'Core'),
        ('backend', 'Backend'),
        ('provider', 'Provider'),
        ('provisioner', 'Provisioner'),
        ('http', 'HTTP'),
        ('grpc', 'gRPC'),
        ('unknown', 'Unknown'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('debug', 'Debug'),
        ('trace', 'Trace'),
        ('info', 'Info'),
        ('RAW', 'Raw'),
    ]

    log_file = models.ForeignKey(LogFile, on_delete=models.CASCADE, related_name='logs')
    original_id = models.CharField(max_length=50)
    timestamp = models.CharField(max_length=20)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)
    component = models.CharField(max_length=15, choices=COMPONENT_CHOICES)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    message = models.TextField()
    raw_data = models.JSONField()
    line_number = models.IntegerField()
    tf_req_id = models.CharField(max_length=100, blank=True)
    tf_resource_type = models.CharField(max_length=100, blank=True)
    tf_rpc = models.CharField(max_length=100, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['level']),
            models.Index(fields=['operation']),
            models.Index(fields=['component']),
            models.Index(fields=['tf_req_id']),
        ]
        ordering = ['line_number']

class JsonBody(models.Model):
    log_entry = models.ForeignKey(LogEntry, on_delete=models.CASCADE, related_name='json_bodies')
    field_name = models.CharField(max_length=50)
    json_data = models.JSONField()
    
    def __str__(self):
        return f"{self.field_name} for {self.log_entry.original_id}"