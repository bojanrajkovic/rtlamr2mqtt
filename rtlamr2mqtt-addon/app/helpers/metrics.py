"""
Prometheus metrics and a liveness endpoint.

GET /metrics  Prometheus exposition format.
GET /healthz  200 while some meter was read within MAX_SILENCE seconds, else 503.
              Startup counts as a reading, so a fresh process gets a full window.
"""

import os
import threading
import time
from http.server import ThreadingHTTPServer

from prometheus_client import Counter, Gauge, Histogram
from prometheus_client.exposition import MetricsHandler

MAX_SILENCE = int(os.getenv('HEALTHZ_MAX_SILENCE_SECONDS', '1800'))

MESSAGES_DECODED = Counter(
    'rtlamr_messages_decoded', 'Messages rtlamr decoded for a configured meter.', ['meter_id', 'protocol'])
METER_LAST_SEEN = Gauge(
    'rtlamr_meter_last_seen_timestamp_seconds', 'Unix time of the last message from a meter.', ['meter_id'])
MQTT_PUBLISHES = Counter(
    'rtlamr_mqtt_publish', 'Meter readings published to MQTT, by result.', ['result'])
MQTT_PUBLISH_SECONDS = Histogram(
    'rtlamr_mqtt_publish_duration_seconds', 'Time to publish one reading (status, state, attributes).')
PROCESS_STARTS = Counter(
    'rtlamr_process_starts', 'Launches of a child process, including the first.', ['process'])
USB_RESETS = Counter(
    'rtlamr_usb_resets', 'USB resets of the RTL-SDR device, by result.', ['result'])

_last_reading = time.time()


def is_healthy(last_reading: float, now: float, max_silence: int) -> bool:
    """True while the last reading is less than max_silence seconds old."""
    return now - last_reading < max_silence


def record_reading(meter_id, protocol: str, now: float | None = None):
    """Count a decoded message and mark its meter as seen."""
    global _last_reading  # pylint: disable=global-statement
    now = time.time() if now is None else now
    MESSAGES_DECODED.labels(meter_id=str(meter_id), protocol=protocol).inc()
    METER_LAST_SEEN.labels(meter_id=str(meter_id)).set(now)
    _last_reading = now


def last_reading_time() -> float:
    return _last_reading


class _Handler(MetricsHandler):
    def do_GET(self):
        if self.path != '/healthz':
            super().do_GET()
            return
        if is_healthy(_last_reading, time.time(), MAX_SILENCE):
            status, body = 200, b'ok\n'
        else:
            status, body = 503, f'no meter reading in {MAX_SILENCE}s\n'.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        """Silence per-request access logs; probes and scrapes would flood stdout."""


def start_server(port: int) -> ThreadingHTTPServer:
    """Serve /metrics and /healthz on a daemon thread. Returns the server."""
    server = ThreadingHTTPServer(('', port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
