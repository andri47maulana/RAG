import os

class Config:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'docs')
    ALLOWED_EXTENSIONS = {'pdf', 'txt'}
