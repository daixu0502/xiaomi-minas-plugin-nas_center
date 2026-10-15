import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SYSTEM=Path(__file__).resolve().parents[1]/'payload/system'
sys.path.insert(0,str(SYSTEM))
spec=importlib.util.spec_from_file_location('cache_metrics',SYSTEM/'process_metrics.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class CacheTests(unittest.TestCase):
    def test_cache_uses_validated_user_and_plugin_var(self):
        m.configure_cache('u123')
        with patch.object(m,'read_state',return_value={'device':7,'bytes':123,'checkedAt':100,'private':'must not return','error':'untrusted text'}) as read,patch.object(m.os,'stat',return_value=SimpleNamespace(st_dev=7)):
            result=m.read_disk_cache()
        read.assert_called_once_with('u123','nascenter','space-cache.json')
        self.assertEqual(result['bytes'],123);self.assertNotIn('private',result);self.assertNotIn('untrusted',result['error'])

    def test_invalid_cache_fields_are_not_returned_as_root_results(self):
        with patch.object(m,'read_state',return_value={'device':7,'bytes':-1,'checkedAt':'not a timestamp','sampledAt':float('inf')}),patch.object(m.os,'stat',return_value=SimpleNamespace(st_dev=7)):
            self.assertEqual(m.read_disk_cache(),{'device':7})

    def test_refresh_process_receives_validated_account(self):
        m.configure_cache('u123')
        with patch.object(m,'read_disk_cache',return_value={}),patch.object(m.subprocess,'Popen') as launch:
            m.docker_directory_usage()
        self.assertEqual(launch.call_args.args[0][-2:],['--refresh-docker-usage','u123'])

    def test_arbitrary_account_is_rejected(self):
        for name in ('root','u1/../../root','u123;id',''):
            with self.assertRaises(ValueError):m.configure_cache(name)


if __name__=='__main__':unittest.main()
