import os

from my_ecomm_dashboard.settings.base import *

SITE_CODE = 1

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'becon_new',
        'USER': 'postgres',
        'PASSWORD': 'iamA9***',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

# settings for media files
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

