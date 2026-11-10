"""
JSON log lines for log shippers.

Each record becomes one JSON object on one line:
  {"time": "...Z", "level": "info", "service": "rtlamr2mqtt", "module": "<logger name>",
   "msg": "...", <extra fields>, "err": {"type", "message", "stack"}}
"""

import logging
import sys
import traceback
from datetime import datetime, timezone

from pythonjsonlogger.json import JsonFormatter

# Shippers expect debug/info/warn/error/fatal; Python calls two of those WARNING and CRITICAL.
LEVEL_NAMES = {
    logging.DEBUG: 'debug',
    logging.INFO: 'info',
    logging.WARNING: 'warn',
    logging.ERROR: 'error',
    logging.CRITICAL: 'fatal',
}


class JsonLineFormatter(JsonFormatter):
    """Formats records with the field names above. Extra fields pass through unchanged."""

    def __init__(self):
        super().__init__(fmt='%(message)s', rename_fields={'message': 'msg'})

    def add_fields(self, log_data, record, message_dict):
        log_data['time'] = (
            datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec='milliseconds')
            .replace('+00:00', 'Z')
        )
        log_data['level'] = LEVEL_NAMES.get(record.levelno, record.levelname.lower())
        log_data['service'] = 'rtlamr2mqtt'
        log_data['module'] = record.name
        message_dict.pop('exc_info', None)
        super().add_fields(log_data, record, message_dict)
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            log_data['err'] = {
                'type': type(exc).__name__,
                'message': str(exc),
                'stack': ''.join(traceback.format_exception(exc)),
            }


def setup_logging(level: int):
    """Send every record to stdout as a JSON line, replacing any existing handlers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLineFormatter())
    logging.basicConfig(handlers=[handler], level=level, force=True)
