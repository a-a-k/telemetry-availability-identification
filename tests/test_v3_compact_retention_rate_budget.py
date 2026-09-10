"""Artificial provider-budget controls; no experiment or real API request."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[1]/'scripts/retain_v3_comparison_compact_v4.py'
spec=importlib.util.spec_from_file_location('compact_transport_v4',path)
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)


def budget(remaining,reset=1100):
    return json.dumps({'resources':{'core':{'remaining':remaining,'reset':reset}}}).encode()


class BudgetControls(unittest.TestCase):
    def setUp(self):
        transport._rate_budget=0;transport._rate_checked_at=0

    def test_archive_bytes_are_returned_unchanged_without_extra_reads(self):
        payload=b'PK\x03\x04\x00\xff\x00'
        with patch.object(transport.subprocess,'check_output',side_effect=[budget(500),payload,payload]) as request, \
             patch.object(transport.time,'monotonic',return_value=1000),patch.object(transport.time,'sleep') as sleep:
            self.assertEqual(transport.api('actions/artifacts/123/zip'),payload)
            self.assertEqual(transport.api('actions/artifacts/124/zip'),payload)
            self.assertEqual(request.call_count,3)
            self.assertEqual(request.call_args_list[1].args[0],['gh','api','repos/'+transport.REPO+'/actions/artifacts/123/zip'])
            sleep.assert_not_called()

    def test_low_budget_waits_until_reset_before_any_archive_request(self):
        clock=[1000.0];times=[];responses=iter([budget(0),budget(1000,4702),b'archive'])
        def request(args):times.append((list(args),clock[0]));return next(responses)
        def sleep(seconds):self.assertLessEqual(seconds,50);clock[0]+=seconds
        with patch.object(transport.subprocess,'check_output',side_effect=request), \
             patch.object(transport.time,'time',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'sleep',side_effect=sleep):
            self.assertEqual(transport.api('actions/artifacts/123/zip'),b'archive')
        self.assertEqual([x[0][-1] for x in times],['rate_limit','rate_limit','repos/'+transport.REPO+'/actions/artifacts/123/zip'])
        self.assertGreaterEqual(times[-1][1],1102)

    def test_invalid_budget_fails_before_content_read(self):
        with patch.object(transport.subprocess,'check_output',return_value=budget('1000')) as request:
            with self.assertRaises(ValueError):transport.api('actions/artifacts/123/zip')
            self.assertEqual(request.call_count,1)

    def test_failed_content_request_is_not_blindly_retried(self):
        error=subprocess.CalledProcessError(1,['gh','api'])
        with patch.object(transport.subprocess,'check_output',side_effect=[budget(500),error]) as request:
            with self.assertRaises(subprocess.CalledProcessError):transport.api('actions/artifacts/123/zip')
            self.assertEqual(request.call_count,2)


if __name__=='__main__':unittest.main()
