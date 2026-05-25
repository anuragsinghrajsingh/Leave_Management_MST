from django import forms
from .models import Profile
from django.contrib.auth.forms import PasswordChangeForm
import re, os
from PIL import Image


class UserProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = ["phone", "address", "profile_photo"]

    # def clean_profile_photo(self):
    #     photo = self.cleaned_data.get("profile_photo")

    #     if photo and photo.size > 3 * 1024 * 1024:
    #         raise forms.ValidationError("Image must be under 3-MB.")
            
    #     return photo
    

    def clean_profile_photo(self):

        photo = self.cleaned_data.get("profile_photo")

        if not photo:
            return photo

        # ✅ SIZE VALIDATION
        if photo.size > 3 * 1024 * 1024:
            raise forms.ValidationError("Image must be under 3MB.")

        try:
            img = Image.open(photo)

            # ✅ FORMAT VALIDATION (REAL, NOT EXTENSION)
            if img.format not in ["JPEG", "PNG", "WEBP"]:
                raise forms.ValidationError("Only JPG, PNG or WEBP images allowed.")

            # ✅ VERIFY IMAGE (NOT CORRUPTED / FAKE)
            img.verify()

        except Exception:
            raise forms.ValidationError("Invalid image file.")

        # 🔥 VERY IMPORTANT (reset pointer after verify)
        photo.seek(0)

        return photo
    
    



class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password_fields = {
            "old_password": "current-password",
            "new_password1": "new-password",
            "new_password2": "new-password",
        }
        for field_name, autocomplete in password_fields.items():
            if field_name in self.fields:
                self.fields[field_name].widget = forms.PasswordInput(
                    attrs={
                        "autocomplete": autocomplete,
                        "class": self.fields[field_name].widget.attrs.get("class", ""),
                    },
                    render_value=False,
                )

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")

        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")

        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r"[0-9]", password):
            raise forms.ValidationError("Password must contain at least one number.")

        if not re.search(r"[^A-Za-z0-9]", password):
            raise forms.ValidationError("Password must contain at least one symbol.")

        return password


    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        return password2
