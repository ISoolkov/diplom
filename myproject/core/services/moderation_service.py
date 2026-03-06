from .exceptions import ServiceValidationError


def _validate_choice(value, choices, message):
    valid_values = {choice[0] for choice in choices}
    if value not in valid_values:
        raise ServiceValidationError(message)


def update_feedback_status(feedback, new_status, moderation_comment):
    _validate_choice(new_status, feedback.STATUS_CHOICES, "Передан некорректный статус обращения.")
    feedback.status = new_status
    feedback.moderation_comment = moderation_comment.strip()
    feedback.save(update_fields=["status", "moderation_comment", "updated_at"])


def update_join_request_status(join_request, new_status, moderation_comment):
    _validate_choice(new_status, join_request.STATUS_CHOICES, "Передан некорректный статус заявки.")
    join_request.status = new_status
    join_request.moderation_comment = moderation_comment.strip()
    join_request.save(update_fields=["status", "moderation_comment", "updated_at"])


def update_user_role(profile, new_role):
    _validate_choice(new_role, profile.ROLE_CHOICES, "Передано недопустимое значение роли.")
    profile.role = new_role
    profile.save(update_fields=["role"])
