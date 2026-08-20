from django import forms


class EmailForm(forms.Form):
    email = forms.EmailField(max_length=255)


class AccountForm(forms.Form):
    display_name = forms.CharField(max_length=100, required=False)
