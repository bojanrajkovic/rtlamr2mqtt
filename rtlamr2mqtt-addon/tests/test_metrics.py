"""Tests for Prometheus metrics and the /healthz endpoint."""

import urllib.error
import urllib.request

import pytest
from prometheus_client import REGISTRY

from helpers import metrics


def sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.mark.parametrize('silence, healthy', [
    (0, True),
    (1799, True),
    (1800, False),
    (7200, False),
])
def test_is_healthy(silence, healthy):
    assert metrics.is_healthy(last_reading=1000.0, now=1000.0 + silence, max_silence=1800) is healthy


def test_record_reading_updates_metrics():
    before = sample('rtlamr_messages_decoded_total', meter_id='42', protocol='scm+')

    metrics.record_reading(42, 'scm+', now=12345.0)

    assert sample('rtlamr_messages_decoded_total', meter_id='42', protocol='scm+') == before + 1
    assert sample('rtlamr_meter_last_seen_timestamp_seconds', meter_id='42') == 12345.0
    assert metrics.last_reading_time() == 12345.0


@pytest.fixture
def server(monkeypatch):
    srv = metrics.start_server(port=0)
    yield f'http://127.0.0.1:{srv.server_port}'
    srv.shutdown()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_metrics_endpoint(server):
    status, body = get(f'{server}/metrics')
    assert status == 200
    assert 'rtlamr_messages_decoded_total' in body


def test_healthz_ok_after_recent_reading(server, monkeypatch):
    monkeypatch.setattr(metrics, 'MAX_SILENCE', 1800)
    metrics.record_reading(42, 'scm+')
    assert get(f'{server}/healthz')[0] == 200


def test_healthz_fails_after_silence(server, monkeypatch):
    monkeypatch.setattr(metrics, 'MAX_SILENCE', 0)
    status, body = get(f'{server}/healthz')
    assert status == 503
    assert 'no meter reading' in body
