import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'payload/system'))
import process_metrics as m


class MetricsTests(unittest.TestCase):
    def test_actual_space_includes_reserved_free(self):
        stats=SimpleNamespace(f_blocks=1000,f_bfree=53,f_bavail=0,f_frsize=4096)
        with patch.object(m.os, 'statvfs', return_value=stats): result=m.physical_space('/data')
        self.assertEqual(result['percent'],94.7)
        self.assertEqual(result['available'],53*4096)
        self.assertEqual(result['ordinaryAvailable'],0)
        self.assertEqual(result['restrictedFree'],53*4096)
        self.assertEqual(result['total'],result['used']+result['available'])

    def test_directory_cache_does_not_scan_every_poll(self):
        with patch.object(m,'disk_cache_dir'),patch.object(m,'read_disk_cache',return_value={'checkedAt':100}),patch.object(m.time,'time',return_value=110),patch.object(m.subprocess,'Popen') as spawn:
            m.docker_directory_usage();spawn.assert_not_called()
        with patch.object(m,'disk_cache_dir'),patch.object(m,'read_disk_cache',return_value={}),patch.object(m.subprocess,'Popen') as spawn:
            self.assertEqual(m.docker_directory_usage(),{})
            self.assertEqual(spawn.call_args.args[0][-1],'--refresh-docker-usage')

    def test_scopes(self):
        for host, expected in [('8.8.8.8', '广域网/公网'), ('192.168.1.1', '局域网/私网'),
                               ('172.17.0.2', '局域网/私网'), ('::1', '本机回环'),
                               ('::ffff:127.0.0.1', '本机回环'), ('100.64.0.1', '运营商共享地址'),
                               ('*', '未指定目标'), ('ff02::1', '组播')]:
            self.assertEqual(m.address_scope(host), expected)

    def test_parse_and_shared_socket(self):
        text = 'ESTAB 0 0 [::1]:5000 [2001:4860:4860::8888]:443 users:(("test",pid=20,fd=2),("test",pid=21,fd=2)) ino:33 sk:ab\n\t cubic rto:204 bytes_sent:100 bytes_received:200\n'
        result = list(m.parse_sockets(text, 'net:[1]', 'TCP').values())[0]
        self.assertEqual(result['pids'], [20, 21])
        self.assertEqual(result['sent'], 100)
        self.assertEqual(result['ip'], '2001:4860:4860::8888')
        self.assertTrue(result['measurable'])
        udp = list(m.parse_sockets('UNCONN 0 0 0.0.0.0:5000 0.0.0.0:* users:(("test",pid=20,fd=3))', 'net:[1]', 'UDP').values())[0]
        self.assertFalse(udp['measurable'])

    def test_rates_use_socket_sampling_time(self):
        text = 'ESTAB 0 0 192.168.1.2:1 8.8.8.8:443 users:(("test",pid=20,fd=2)) sk:ab\n\t rto:204 bytes_sent:100 bytes_received:200\n'
        old = m.parse_sockets(text, 'net:[1]', 'TCP')
        new = m.parse_sockets(text.replace('sent:100', 'sent:300').replace('received:200', 'received:600'), 'net:[1]', 'TCP')
        for r in old.values(): r['sampleTime'] = 10
        for r in new.values(): r['sampleTime'] = 12
        with patch.object(m, 'namespaces', return_value={'net:[1]': '/proc/self/ns/net'}), \
             patch.object(m, 'socket_snapshot', side_effect=[(old, []), (new, [])]), \
             patch.object(m, 'processes', return_value={20: {'name': 'test', 'description': 'unknown'}}), patch.object(m.time, 'sleep'):
            row = m.network_details()['rows'][0]
        self.assertEqual(row['tx'], 100)
        self.assertEqual(row['rx'], 200)

    def test_pid_reuse_not_old_cpu(self):
        before = {1: {'pid': 1, 'start': 1, 'ticks': 100, 'rss': 20}}
        after = {1: {'pid': 1, 'start': 2, 'ticks': 400, 'rss': 20},
                 2: {'pid': 2, 'start': 1, 'ticks': 20, 'rss': 40}}
        with patch.object(m, 'processes', side_effect=[before, after]), patch.object(m, 'total_ticks', side_effect=[1000, 1400]), patch.object(m.time, 'sleep'):
            rows = m.process_details('memory')['rows']
        self.assertEqual(rows[0]['pid'], 2)
        self.assertIsNone(rows[1]['cpu'])

    def test_unknown_description_does_not_expose_command(self):
        self.assertNotIn('secret', m.describe('unknown', 'unknown --password=secret'))
        self.assertIn('代理', m.describe('mihomo'))


if __name__ == '__main__':
    unittest.main()
