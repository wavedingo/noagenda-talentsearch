from django import forms

from .models import RejectionReason

BIO_MAX_LENGTH = 1500

BIO_PROMPT = "Who are you, how long have you been listening, and why you?"


class ProfileForm(forms.Form):
    stage_name = forms.CharField(
        max_length=100,
        label="Stage name",
        help_text="How you'd like to be credited on the show.",
    )
    bio = forms.CharField(
        max_length=BIO_MAX_LENGTH,
        required=False,
        label="Bio",
        help_text=f"{BIO_PROMPT} Plain text, up to {BIO_MAX_LENGTH} characters.",
        widget=forms.Textarea(attrs={"rows": 8, "maxlength": BIO_MAX_LENGTH}),
    )
    photo = forms.FileField(
        required=False,
        label="Photo (optional)",
        help_text="JPG, PNG, or WebP, up to 5 MB. We resize it and strip its location data.",
    )
    clear_photo = forms.BooleanField(required=False, label="Remove my current photo")

    def clean_stage_name(self):
        return self.cleaned_data["stage_name"].strip()


class DemoForm(forms.Form):
    demo = forms.FileField(label="Demo tape (MP3)")


class ModerationDecisionForm(forms.Form):
    """Backs every approve/reject button in the moderation queue."""

    ACTIONS = [("approve", "Approve"), ("reject", "Reject")]

    target = forms.ChoiceField(
        choices=[("candidate", "Candidate"), ("profile_edit", "Profile edit"), ("demo", "Demo")]
    )
    target_id = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=ACTIONS)
    reason = forms.ChoiceField(choices=RejectionReason.choices, required=False)
    note = forms.CharField(max_length=1000, required=False)

    def clean(self):
        data = super().clean()
        if data.get("action") == "reject" and not data.get("reason"):
            raise forms.ValidationError("Pick a reason before rejecting.")
        return data
