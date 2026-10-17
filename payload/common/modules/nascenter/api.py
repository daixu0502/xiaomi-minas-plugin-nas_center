"""Registered-user monitoring and fixed maintenance operations."""
import json
import os
from pathlib import Path
import subprocess
import privileged_runtime as runtime

ACTIONS = {'overview','smart','processes','process_network','health_details','service_restart','drop_caches','clean_logs'}

def api(user, request):
    runtime.authorize(user, 'nascenter')
    action = request.get('action')
    if action not in ACTIONS:
        raise ValueError('未知控制中心操作')
    def invoke():
        env = {'PATH':'/data/docker:/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL':'C.UTF-8', 'PYTHONDONTWRITEBYTECODE':'1', 'SUDO_USER':user}
        result = subprocess.run(['/usr/bin/python3','-B',str(Path(__file__).with_name('nas-center-helper'))], input=json.dumps(dict(request, pluginUser=user)), capture_output=True, text=True, env=env, timeout=110)
        if result.returncode:
            raise ValueError('控制中心助手执行失败')
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError('控制中心助手返回无效数据')
        return value
    if action == 'service_restart' and request.get('service') == 'docker':
        with runtime.docker_transaction():
            return invoke()
    return invoke()
