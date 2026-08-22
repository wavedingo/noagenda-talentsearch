from django import forms

from .models import Report


class ReportForm(forms.Form):
    reason = forms.ChoiceField(choices=Report.Reason.choices)
    details = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional. A sentence is enough — we don't need a brief.",
    )
