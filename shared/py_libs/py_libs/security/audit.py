"""
Audit logging utilities.

Provides structured audit logging for:
- Authentication events (login, logout, failed attempts)
- Authorization events (access granted/denied)
- Data access events (read, write, delete)
- Security events (password change, 2FA, etc.)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

# Configure audit logger
audit_logger = logging.getLogger("audit")


class AuditEventType(Enum):
    """Types of audit events."""

    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_ISSUED = "auth.token.issued"
    TOKEN_REVOKED = "auth.token.revoked"
    TOKEN_EXPIRED = "auth.token.expired"
    PASSWORD_CHANGED = "auth.password.changed"
    PASSWORD_RESET_REQUESTED = "auth.password.reset.requested"
    PASSWORD_RESET_COMPLETED = "auth.password.reset.completed"
    MFA_ENABLED = "auth.mfa.enabled"
    MFA_DISABLED = "auth.mfa.disabled"
    MFA_CHALLENGE_SUCCESS = "auth.mfa.challenge.success"
    MFA_CHALLENGE_FAILURE = "auth.mfa.challenge.failure"

    # Authorization events
    ACCESS_GRANTED = "authz.access.granted"
    ACCESS_DENIED = "authz.access.denied"
    PERMISSION_GRANTED = "authz.permission.granted"
    PERMISSION_REVOKED = "authz.permission.revoked"
    ROLE_ASSIGNED = "authz.role.assigned"
    ROLE_REMOVED = "authz.role.removed"

    # Data events
    DATA_READ = "data.read"
    DATA_CREATED = "data.created"
    DATA_UPDATED = "data.updated"
    DATA_DELETED = "data.deleted"
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"

    # User management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_ACTIVATED = "user.activated"
    USER_DEACTIVATED = "user.deactivated"

    # Security events
    SECURITY_ALERT = "security.alert"
    RATE_LIMIT_EXCEEDED = "security.ratelimit.exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious"
    BRUTE_FORCE_DETECTED = "security.bruteforce"
    IP_BLOCKED = "security.ip.blocked"
    IP_UNBLOCKED = "security.ip.unblocked"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "system.config.changed"


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(slots=True)
class AuditEvent:
    """
    Structured audit event.

    Attributes:
        event_type: Type of audit event
        severity: Event severity level
        actor: User or system that performed the action
        resource: Resource that was accessed/modified
        action: Specific action performed
        outcome: Success or failure
        details: Additional event details
        ip_address: Client IP address
        user_agent: Client user agent
        request_id: Request/correlation ID
        timestamp: Event timestamp
        event_id: Unique event identifier
    """

    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    actor: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    outcome: str = "success"
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        data["timestamp_iso"] = datetime.fromtimestamp(self.timestamp).isoformat()
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """
    Audit logger for recording security-relevant events.

    Example:
        audit = AuditLogger()
        audit.log_login_success(user_id="user123", ip_address="192.168.1.1")
        audit.log_access_denied(user_id="user123", resource="/admin/users")
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        handlers: Optional[List[Callable[[AuditEvent], None]]] = None,
    ) -> None:
        """
        Initialize audit logger.

        Args:
            logger: Python logger to use
            handlers: Additional handlers to call for each event
        """
        self._logger = logger or audit_logger
        self._handlers = handlers or []

    def add_handler(self, handler: Callable[[AuditEvent], None]) -> None:
        """Add an event handler."""
        self._handlers.append(handler)

    def log(self, event: AuditEvent) -> None:
        """
        Log an audit event.

        Args:
            event: Audit event to log
        """
        # Log to Python logger
        log_level = self._get_log_level(event.severity)
        self._logger.log(log_level, event.to_json())

        # Call additional handlers
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.error(f"Audit handler error: {e}")

    def _get_log_level(self, severity: AuditSeverity) -> int:
        """Map audit severity to logging level."""
        mapping = {
            AuditSeverity.DEBUG: logging.DEBUG,
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(severity, logging.INFO)

    # Authentication events
    def log_login_success(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log successful login."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.LOGIN_SUCCESS,
                actor=user_id,
                outcome="success",
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
            )
        )

    def log_login_failure(
        self,
        username: str,
        reason: str = "invalid_credentials",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log failed login attempt."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.LOGIN_FAILURE,
                severity=AuditSeverity.WARNING,
                actor=username,
                outcome="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                details={"reason": reason, **details},
            )
        )

    def log_logout(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log user logout."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.LOGOUT,
                actor=user_id,
                ip_address=ip_address,
                details=details,
            )
        )

    def log_password_changed(
        self,
        user_id: str,
        changed_by: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log password change."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.PASSWORD_CHANGED,
                actor=changed_by or user_id,
                resource=f"user:{user_id}",
                action="password_change",
                details=details,
            )
        )

    # Authorization events
    def log_access_denied(
        self,
        user_id: str,
        resource: str,
        reason: str = "insufficient_permissions",
        ip_address: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log access denied event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.ACCESS_DENIED,
                severity=AuditSeverity.WARNING,
                actor=user_id,
                resource=resource,
                outcome="denied",
                ip_address=ip_address,
                details={"reason": reason, **details},
            )
        )

    def log_access_granted(
        self,
        user_id: str,
        resource: str,
        action: str = "access",
        **details: Any,
    ) -> None:
        """Log access granted event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.ACCESS_GRANTED,
                actor=user_id,
                resource=resource,
                action=action,
                outcome="granted",
                details=details,
            )
        )

    # Data events
    def log_data_read(
        self,
        user_id: str,
        resource: str,
        **details: Any,
    ) -> None:
        """Log data read event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.DATA_READ,
                actor=user_id,
                resource=resource,
                action="read",
                details=details,
            )
        )

    def log_data_created(
        self,
        user_id: str,
        resource: str,
        resource_id: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log data creation event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.DATA_CREATED,
                actor=user_id,
                resource=resource,
                action="create",
                details={"resource_id": resource_id, **details},
            )
        )

    def log_data_updated(
        self,
        user_id: str,
        resource: str,
        resource_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        **details: Any,
    ) -> None:
        """Log data update event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.DATA_UPDATED,
                actor=user_id,
                resource=resource,
                action="update",
                details={"resource_id": resource_id, "changes": changes, **details},
            )
        )

    def log_data_deleted(
        self,
        user_id: str,
        resource: str,
        resource_id: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log data deletion event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.DATA_DELETED,
                severity=AuditSeverity.WARNING,
                actor=user_id,
                resource=resource,
                action="delete",
                details={"resource_id": resource_id, **details},
            )
        )

    # Security events
    def log_security_alert(
        self,
        message: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        ip_address: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log security alert."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.SECURITY_ALERT,
                severity=severity,
                ip_address=ip_address,
                details={"message": message, **details},
            )
        )

    def log_rate_limit_exceeded(
        self,
        identifier: str,
        limit: int,
        window: int,
        ip_address: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log rate limit exceeded event."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
                severity=AuditSeverity.WARNING,
                actor=identifier,
                ip_address=ip_address,
                details={"limit": limit, "window_seconds": window, **details},
            )
        )

    def log_suspicious_activity(
        self,
        description: str,
        actor: Optional[str] = None,
        ip_address: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log suspicious activity."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
                severity=AuditSeverity.WARNING,
                actor=actor,
                ip_address=ip_address,
                details={"description": description, **details},
            )
        )

    # User management events
    def log_user_created(
        self,
        user_id: str,
        created_by: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log user creation."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.USER_CREATED,
                actor=created_by or "system",
                resource=f"user:{user_id}",
                action="create",
                details=details,
            )
        )

    def log_user_updated(
        self,
        user_id: str,
        updated_by: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        **details: Any,
    ) -> None:
        """Log user update."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.USER_UPDATED,
                actor=updated_by or user_id,
                resource=f"user:{user_id}",
                action="update",
                details={"changes": changes, **details},
            )
        )

    def log_user_deleted(
        self,
        user_id: str,
        deleted_by: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Log user deletion."""
        self.log(
            AuditEvent(
                event_type=AuditEventType.USER_DELETED,
                severity=AuditSeverity.WARNING,
                actor=deleted_by or "system",
                resource=f"user:{user_id}",
                action="delete",
                details=details,
            )
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def configure_audit_logger(
    logger: Optional[logging.Logger] = None,
    handlers: Optional[List[Callable[[AuditEvent], None]]] = None,
) -> AuditLogger:
    """Configure the global audit logger."""
    global _audit_logger
    _audit_logger = AuditLogger(logger=logger, handlers=handlers)
    return _audit_logger


# Convenience functions
def audit_log(event: AuditEvent) -> None:
    """Log an audit event using the global logger."""
    get_audit_logger().log(event)


def audit_login_success(user_id: str, **kwargs: Any) -> None:
    """Log successful login."""
    get_audit_logger().log_login_success(user_id, **kwargs)


def audit_login_failure(username: str, **kwargs: Any) -> None:
    """Log failed login."""
    get_audit_logger().log_login_failure(username, **kwargs)


def audit_access_denied(user_id: str, resource: str, **kwargs: Any) -> None:
    """Log access denied."""
    get_audit_logger().log_access_denied(user_id, resource, **kwargs)


def audit_data_access(
    user_id: str,
    resource: str,
    action: str,
    **kwargs: Any,
) -> None:
    """Log data access event."""
    logger = get_audit_logger()
    if action == "read":
        logger.log_data_read(user_id, resource, **kwargs)
    elif action == "create":
        logger.log_data_created(user_id, resource, **kwargs)
    elif action == "update":
        logger.log_data_updated(user_id, resource, **kwargs)
    elif action == "delete":
        logger.log_data_deleted(user_id, resource, **kwargs)
