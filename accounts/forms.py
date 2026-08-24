from django import forms


class EmailForm(forms.Form):
    email = forms.EmailField(max_length=255)


class AccountForm(forms.Form):
    # Deliberately NOT the candidate's stage_name. This is account metadata
    # that appears nowhere public -- it exists so a moderator sees a human
    # name next to an email in the admin. The public audition name lives on
    # Candidate.stage_name and only changes through pre-moderation (B.1).
    display_name = forms.CharField(
        max_length=100,
        required=False,
        label="Your name",
        help_text="Private. Only site moderators see this — it never appears on your public profile.",
    )
