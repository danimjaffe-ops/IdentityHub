from datetime import datetime, timezone

from ..extensions import db


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    key_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    key_prefix = db.Column(db.String(12), nullable=False)
    label = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="api_keys")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key_prefix": self.key_prefix,
            "label": self.label,
            "is_active": self.is_active,
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at
            else None,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<ApiKey {self.key_prefix}...>"
