from __future__ import unicode_literals

import logging.config
import os

from edx_adapt.settings import LOGS_DIR

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

_log_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(levelname)s %(filename)s:%(lineno)d -- %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': os.path.join(LOGS_DIR, 'edx-adapt.log'),
            'mode': 'w',
            'encoding': 'utf8',
            'maxBytes': 1024 * 1024,
            'backupCount': 5
        },
        'null': {
            'level': 'CRITICAL',
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        # Log all to log file, but by default only warnings.
        '': {
            'handlers': ['file'],
            'level': 'WARNING',
        },
        'edx-adapt': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        },
        'dev': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True  # Test log too
        },
    }
}

logging.config.dictConfig(_log_config)
logger = logging.getLogger('edx-adapt')
