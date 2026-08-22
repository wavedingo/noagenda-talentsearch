from django import forms

from candidates.models import Candidate

from .models import Rating


class RatingForm(forms.Form):
    rateable_type = forms.ChoiceField(choices=Rating.RateableType.choices)
    rateable_id = forms.IntegerField(min_value=1)
    stars = forms.IntegerField(min_value=1, max_value=5)
    next = forms.CharField(required=False)


class TagAppearanceForm(forms.Form):
    guest_name = forms.CharField(max_length=100, required=False)
    candidate = forms.ModelChoiceField(
        queryset=Candidate.objects.filter(status=Candidate.Status.LIVE).order_by("stage_name"),
        required=False,
    )
    admin_note = forms.CharField(max_length=500, required=False)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("candidate") and not (cleaned.get("guest_name") or "").strip():
            raise forms.ValidationError("Name a guest host or pick a candidate.")
        return cleaned
