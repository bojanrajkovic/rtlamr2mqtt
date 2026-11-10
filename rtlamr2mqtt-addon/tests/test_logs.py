"""Tests for the JSON log formatter."""

import json
import logging

import pytest

from helpers.logs import JsonLineFormatter


def format_record(level, msg='hello', name='rtlamr2mqtt', exc_info=None, **extra):
    record = logging.LogRecord(name, level, __file__, 1, msg, None, exc_info)
    record.__dict__.update(extra)
    return JsonLineFormatter().format(record)


@pytest.mark.parametrize('level, expected', [
    (logging.DEBUG, 'debug'),
    (logging.INFO, 'info'),
    (logging.WARNING, 'warn'),
    (logging.ERROR, 'error'),
    (logging.CRITICAL, 'fatal'),
])
def test_level_names(level, expected):
    assert json.loads(format_record(level))['level'] == expected


def test_contract_fields():
    line = json.loads(format_record(logging.INFO, name='rtlamr2mqtt.rtlamr'))
    assert line['msg'] == 'hello'
    assert line['service'] == 'rtlamr2mqtt'
    assert line['module'] == 'rtlamr2mqtt.rtlamr'
    assert line['time'].endswith('Z')
    assert 'message' not in line


def test_extra_fields_are_kept():
    line = json.loads(format_record(logging.INFO, meter_id=1550633820))
    assert line['meter_id'] == 1550633820


def test_exception_stays_on_one_line():
    try:
        raise ValueError('bad reading')
    except ValueError:
        import sys
        out = format_record(logging.ERROR, exc_info=sys.exc_info())

    assert '\n' not in out
    err = json.loads(out)['err']
    assert err['type'] == 'ValueError'
    assert err['message'] == 'bad reading'
    assert 'raise ValueError' in err['stack']
    assert 'exc_info' not in json.loads(out)
