"""Read-only /proc and socket telemetry. Never capture payloads or expose argv."""
import ipaddress
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

DISK_CACHE = Path('/run/nascenter-space')


def physical_space(path):
    s = os.statvfs(path)
    total = s.f_blocks * s.f_frsize
    free = s.f_bfree * s.f_frsize
    ordinary = max(0, s.f_bavail * s.f_frsize)
    used = max(0, total - free)
    return {'total': total, 'used': used, 'available': free, 'ordinaryAvailable': ordinary,
            'restrictedFree': max(0, free - ordinary), 'percent': round(used * 100 / max(1, total), 1)}


def disk_cache_dir():
    DISK_CACHE.mkdir(mode=0o700, exist_ok=True)
    s = DISK_CACHE.lstat()
    if DISK_CACHE.is_symlink() or s.st_uid != 0 or s.st_mode & 0o077:
        raise RuntimeError('空间缓存目录权限无效')


def read_disk_cache():
    try:
        data = json.loads((DISK_CACHE / 'docker.json').read_text())
        if data.get('device') == os.stat('/data/docker_data').st_dev:
            return data
    except (OSError, ValueError):
        pass
    return {}


def docker_directory_usage():
    # Do not recursively scan Docker on the three-second UI polling path.
    disk_cache_dir()
    data = read_disk_cache()
    age = time.time() - data.get('checkedAt', 0)
    if not 0 <= age < 60:
        subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--refresh-docker-usage'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    return data


def refresh_docker_usage():
    if os.geteuid() != 0:
        return
    disk_cache_dir()
    with (DISK_CACHE / 'scan.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        data = read_disk_cache()
        if 0 <= time.time() - data.get('checkedAt', 0) < 60:
            return
        try:
            device = os.stat('/data/docker_data').st_dev
            result = subprocess.run(['du', '-x', '-s', '-k', '/data/docker_data'], capture_output=True,
                                    text=True, timeout=20, check=True)
            if os.stat('/data/docker_data').st_dev != device:
                raise RuntimeError('挂载发生变化')
            data = {'bytes': int(result.stdout.split()[0]) * 1024, 'sampledAt': time.time(), 'device': device}
        except (OSError, ValueError, subprocess.SubprocessError, RuntimeError):
            data['error'] = '目录扫描未完成或失败；有旧值时保留旧值'
            try: data.setdefault('device', os.stat('/data/docker_data').st_dev)
            except OSError: return
        data['checkedAt'] = time.time()
        temp = DISK_CACHE / ('docker.json.' + str(os.getpid()))
        try:
            temp.write_text(json.dumps(data))
            os.replace(temp, DISK_CACHE / 'docker.json')
        finally:
            temp.unlink(missing_ok=True)


def describe(name, command='', kernel=False):
    name = name.lower()
    known = [('mihomo', '代理核心：执行代理规则与网络转发'), ('aria2', '下载中心：直链、BT 下载与做种'),
             ('syncthing', '文件夹双向同步与文件校验'), ('openlist', '文件聚合、网盘与文件访问服务'),
             ('smbd', 'SMB 文件共享：电脑访问 NAS 文件'), ('nmbd', '局域网 SMB 名称发现'),
             ('cfs', '小米存储池文件系统与磁盘数据访问'), ('rsync', '文件同步或磁盘间备份'),
             ('axon', '小米客户端通信与远程连接服务'), ('miio', '小米设备通信服务'),
             ('xunlei', '迅雷下载、传输或媒体文件访问'), ('baidunas', '百度网盘下载与同步'),
             ('p2pclient', '百度网盘 P2P 传输组件'), ('findexd', '文件索引与扫描'),
             ('mediacenter', '官方影视媒体库扫描、索引与播放管理'), ('upsnap', '局域网设备唤醒与在线状态探测'),
             ('ffmpeg', '影音处理、转码或缩略图生成'), ('ffprobe', '读取影音格式与媒体信息'),
             ('nginx', '网页、插件页面与反向代理服务'), ('dockerd', 'Docker 容器管理服务'),
             ('containerd', '容器运行时与生命周期管理'), ('mosquitto', '设备内部 MQTT 消息服务'),
             ('ipc_mgr', '摄像头与设备通信管理'), ('taskcenter', '小米系统任务管理服务'),
             ('kswapd', '内核内存回收与换页'), ('kworker', '内核后台工作线程'),
             ('btrfs', '磁盘文件系统元数据与后台维护'), ('systemd-journal', '系统日志记录'),
             ('syslog', '系统日志收集'), ('dbus', '系统服务间通信'), ('sshd', 'SSH 远程管理'),
             ('dropbear', 'SSH 远程管理'), ('crond', '定时任务调度'), ('avahi', '局域网服务发现')]
    for token, text in known:
        if name.startswith(token):
            return text
    for token, text in [('nascenter', '控制中心状态采集'), ('downloadcenter', '下载中心任务管理'),
                        ('quickshare', '文件快传与临时分享'), ('taskcenter', '定时任务插件'),
                        ('mihomo', 'Mihomo 插件管理')]:
        if '/plugin/' + token + '/' in command or '/pluginsrc/' + token + '/' in command or '.nascenter-system/' in command and token == 'nascenter':
            return text
    if kernel:
        return '内核线程；具体任务依名称判断'
    return '暂未收录用途；仅凭进程名无法确定实际任务'


def processes():
    result = {}
    page_size = os.sysconf('SC_PAGE_SIZE')
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            raw = (p / 'stat').read_text()
            end = raw.rindex(')')
            fields = raw[end + 2:].split()
            name = raw[raw.index('(') + 1:end]
            # Only interpreters need argv to identify an installed plugin; avoid
            # reading hundreds of irrelevant command lines every refresh.
            command = ''
            if name in ('python', 'python3', 'sh', 'bash', 'node') and int(p.name) != os.getpid():
                with (p / 'cmdline').open('rb') as stream:
                    command = stream.read(4096).replace(b'\0', b' ').decode(errors='replace')
            result[int(p.name)] = {'pid': int(p.name), 'start': int(fields[19]),
                'ticks': int(fields[11]) + int(fields[12]), 'rss': max(0, int(fields[21])) * page_size,
                'name': name, 'description': '控制中心实时采样（本次请求）' if int(p.name) == os.getpid() else describe(name, command, bool(int(fields[6]) & 0x200000)), 'state': fields[0]}
        except (OSError, ValueError, IndexError):
            continue  # Exiting processes are normal, not a page-wide error.
    return result


def total_ticks():
    # guest/guest_nice are already included in user/nice; do not count twice.
    return sum(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))


def process_details(kind):
    before = processes()
    first = total_ticks()
    time.sleep(.6)
    after = processes()
    elapsed = max(1, total_ticks() - first)
    total_mem = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemTotal:'))) * 1024
    rows = []
    for pid, row in after.items():
        old = before.get(pid)
        row['cpu'] = round(min(100, max(0, row['ticks'] - old['ticks']) * 100 / elapsed), 2) if old and old['start'] == row['start'] else None
        row['memoryPercent'] = round(row['rss'] * 100 / max(1, total_mem), 2)
        del row['ticks']
        rows.append(row)
    rows.sort(key=lambda r: (-(r['rss'] if kind == 'memory' else r['cpu'] or 0), r['pid']))
    return {'ok': True, 'rows': rows, 'total': len(rows), 'cores': os.cpu_count(), 'timestamp': time.time(),
            'note': 'CPU 按整机总算力百分比统计（所有核心合计 100%）；新进程等待下次采样，采样本身也会短暂占用 CPU。内存为实际驻留 RSS，共享页可能重复计入，不等于首页已用内存。用途按名称推测，不代表已确认当前操作。'}


def endpoint(value):
    host, _, port = value.rpartition(':')
    return host.strip('[]').split('%')[0], port


def address_scope(host):
    try:
        ip = ipaddress.ip_address(host)
        ip = getattr(ip, 'ipv4_mapped', None) or ip
        if ip.is_unspecified: return '未指定目标'
        if ip.is_loopback: return '本机回环'
        if ip.is_multicast: return '组播'
        if ip.version == 4 and ip in ipaddress.ip_network('100.64.0.0/10'): return '运营商共享地址'
        if ip.is_private or ip.is_link_local: return '局域网/私网'
        if ip.is_global: return '广域网/公网'
        return '特殊地址'
    except ValueError:
        return '未指定目标'


def parse_sockets(text, namespace, protocol):
    records = []
    for line in text.splitlines():
        if line[:1].isspace() and records:
            records[-1] += ' ' + line.strip()
        elif line.strip():
            records.append(line)
    result = {}
    for record in records:
        cols = record.split(None, 5)
        if len(cols) < 5: continue
        local, remote = cols[3:5]
        host, port = endpoint(remote)
        pids = sorted(set(map(int, re.findall(r'pid=(\d+)', record))))
        cookie = re.search(r'\bsk:([\da-f]+)', record)
        key = (namespace, protocol, cookie.group(1) if cookie else local + '/' + remote, tuple(pids))
        counters = dict((k, int(v)) for k, v in re.findall(r'\b(bytes_sent|bytes_received):(\d+)', record))
        result[key] = {'pids': pids, 'protocol': protocol, 'local': local, 'remote': remote,
            'ip': host, 'port': port, 'scope': address_scope(host), 'namespace': namespace,
            'sent': counters.get('bytes_sent', 0), 'received': counters.get('bytes_received', 0),
            'measurable': protocol == 'TCP' and ('rto:' in record or bool(counters))}
    return result


def namespaces():
    result = {}
    paths = [Path('/proc/self')] + [p for p in Path('/proc').iterdir() if p.name.isdigit()]
    for p in paths:
        try:
            name = os.readlink(p / 'ns/net')
            result.setdefault(name, str(p / 'ns/net'))
        except OSError:
            pass
    return result


def socket_snapshot(spaces, deadline):
    result, warnings = {}, []
    own = os.readlink('/proc/self/ns/net')
    for namespace, path in spaces.items():
        if time.monotonic() >= deadline:
            warnings.append('采集达到时间上限，部分网络空间未采集')
            break
        for protocol, flags in [('TCP', '-Htinpe'), ('UDP', '-Huanpe')]:
            args = ['/usr/sbin/ss', flags]
            if namespace != own:
                args = ['/usr/bin/nsenter', '--net=' + path, '--'] + args
            try:
                done = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      timeout=max(.1, min(1.5, deadline - time.monotonic())))
                if done.returncode:
                    warnings.append('部分网络空间不可用（可能容器已退出）')
                    continue
                batch = parse_sockets(done.stdout, namespace, protocol)
                for row in batch.values(): row['sampleTime'] = time.monotonic()
                result.update(batch)
            except (OSError, subprocess.TimeoutExpired):
                warnings.append('部分网络空间采集失败或超时')
    return result, warnings


def network_details():
    spaces = namespaces()
    warnings = ['网络为 TCP 字节计数差值；UDP/QUIC 暂不支持测速，未连接的 UDP 无法提供目标 IP。',
                '仅统计采样期间存活的连接，短连接可能遗漏；共享套接字合并显示，不能与网卡总速率直接相加。',
                '公网/私网按目标 IP 分类，不代表实际路由；经代理时只显示当前一跳，外发流量可能归属 Mihomo。']
    if len(spaces) > 16:
        warnings.append('网络空间超过 16 个，仅采集前 16 个')
        spaces = dict(list(spaces.items())[:16])
    start = time.monotonic()
    before, errors = socket_snapshot(spaces, start + 3)
    first = time.monotonic()
    time.sleep(.6)
    after, more_errors = socket_snapshot(spaces, time.monotonic() + 3)
    seconds = max(.1, time.monotonic() - first)
    procs, groups = processes(), {}
    if len(after) > 2000:
        warnings.append('连接超过 2000 条，仅显示前 2000 条，汇总不完整')
    for key, conn in list(after.items())[:2000]:
        ids = tuple(conn['pids'])
        group_key = (conn['namespace'], ids)
        if group_key not in groups:
            names = [procs[p]['name'] for p in ids if p in procs]
            groups[group_key] = {'key': repr(group_key), 'pids': list(ids), 'name': ' / '.join(names) or '进程已退出或无法归属',
                'description': procs[ids[0]]['description'] if ids and ids[0] in procs else '无法确认用途',
                'rx': 0, 'tx': 0, 'measured': False, 'connections': []}
        old = before.get(key)
        measured = old is not None and conn['measurable'] and old['measurable']
        duration = max(.1, conn['sampleTime'] - old['sampleTime']) if measured else seconds
        conn['rx'] = max(0, conn['received'] - old['received']) / duration if measured else None
        conn['tx'] = max(0, conn['sent'] - old['sent']) / duration if measured else None
        conn['reason'] = '' if measured else 'UDP 暂不支持测速' if conn['protocol'] == 'UDP' else '新连接/计数不可用'
        row = groups[group_key]
        if measured:
            row['measured'] = True
            row['rx'] += conn['rx']; row['tx'] += conn['tx']
        row['connections'].append({k: v for k, v in conn.items() if k not in ('sent', 'received', 'namespace', 'pids', 'measurable', 'sampleTime')})
    rows = sorted(groups.values(), key=lambda r: -(r['rx'] + r['tx']))
    return {'ok': True, 'rows': rows, 'timestamp': time.time(), 'interval': round(seconds, 2),
            'namespaces': len(spaces), 'warnings': list(dict.fromkeys(warnings + errors + more_errors))}


if __name__ == '__main__' and sys.argv[1:] == ['--refresh-docker-usage']:
    refresh_docker_usage()
