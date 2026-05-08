import os

class Config:
    INSTANCE_FOLDER_PATH = None
    SECRET_KEY = 'memgen-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///memgen.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    TEMPLATE_FOLDER = 'static/templates'
    GENERATED_FOLDER = 'static/generated'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    WTF_CSRF_ENABLED = True