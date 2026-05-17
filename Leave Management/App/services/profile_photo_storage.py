import os
import re

from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class ProfilePhotoStorage(FileSystemStorage):
    def get_valid_name(self, name):
        basename = os.path.basename(name)
        sanitized = re.sub(r"[^A-Za-z0-9._()-]+", "_", basename).strip("._")
        return sanitized or "profile-photo"
