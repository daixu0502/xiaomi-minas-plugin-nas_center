import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SYSTEM = Path(__file__).resolve().parents[1] / 'payload/system'
sys.path.insert(0,str(SYSTEM))
import telemetry_cache as cache
import process_metrics as metrics


class PerformanceTests(unittest.TestCase):
    @unittest.skipUnless(os.geteuid()==0,'root-owned cache test')
    def test_ttl_force_and_invalid_cache(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cache,'ROOT',Path(tmp)):
            loader=Mock(return_value={'value':1})
            self.assertEqual(cache.cached('test',20,loader),{'value':1})
            cache.cached('test',20,loader);self.assertEqual(loader.call_count,1)
            cache.cached('test',20,loader,True);self.assertEqual(loader.call_count,2)
            cache.invalidate('test');cache.cached('test',20,loader)
            self.assertEqual(loader.call_count,3)

    @unittest.skipUnless(os.geteuid()==0,'root-owned cache test')
    def test_links_are_never_followed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cache,'ROOT',Path(tmp)):
            outside=Path(tmp)/'outside';outside.write_text('untouched')
            (Path(tmp)/'test.lock').symlink_to(outside)
            with self.assertRaises(OSError):cache.cached('test',20,lambda:1)
            self.assertEqual(outside.read_text(),'untouched')

    def test_memory_does_not_wait_for_cpu_sampling(self):
        with patch.object(metrics,'processes',return_value={}) as scan, patch.object(metrics.time,'sleep') as sleep:
            result=metrics.process_details('memory')
        self.assertEqual(result['rows'],[]);self.assertEqual(scan.call_count,1);sleep.assert_not_called()


if __name__=='__main__':unittest.main()
