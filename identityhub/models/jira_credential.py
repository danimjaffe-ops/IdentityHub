from datetime import datetime, timezone

from ..extensions import db


class JiraCredential(db.Model):
    __tablename__ = "jira_credentials"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )
    site_url = db.Column(db.String(500), nullable=False)
    email_encrypted = db.Column(db.LargeBinary, nullable=False)
    api_token_encrypted = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="jira_credential")

    def __repr__(self):
        return f"<JiraCredential user_id={self.user_id}>"
