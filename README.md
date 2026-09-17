# 小米智能存储控制中心

在小米智能存储 APP 内集中查看设备健康状态并执行受限维护操作，当前插件版本为 `1.1.2`。

## 功能

- CPU 使用率、系统负载、运行时间和 CPU 温度
- 内存用量、可用内存和可释放页缓存
- 实时网络速度、累计流量、错误和丢包
- 用户存储池、系统数据、`/data/docker_data`、日志和固件空间
- SATA/NVMe SMART 健康、温度、通电时间和坏扇区指标
- 点击硬盘查看完整 SMART 属性、设备信息、错误日志和自检记录
- 查看并重启 Docker、Samba、定时任务、Mihomo 和文件快传服务
- 安全释放 Linux 页缓存和整理 systemd 日志
- Android、iOS 安全区、沉浸式状态栏和左右滑动切页

控制中心不监听额外网络端口，可以安装给多个设备用户。页面不直接拥有 root 权限，维护操作通过固定白名单助手执行。

## 安装

从电脑的 WSL/Linux 运行：

```sh
cd nas-center-plugin
bash deploy.sh
```

也可以指定设备和用户：

```sh
bash deploy.sh 192.168.31.100 u123456789
```

在小米智能存储 root SSH 终端内运行：

```sh
cd /home/rootx/nas-center-plugin
bash deploy.sh u123456789
```

## 安全边界

服务名称和维护动作不能由页面拼接为任意命令。空间维护不会清空回收站，也不会删除照片、视频、下载文件、Docker 容器、镜像或存储卷。

## 卸载

```sh
bash uninstall.sh
```

也可以指定设备与用户：

```sh
bash uninstall.sh 192.168.31.100 u123456789
```

设备本机运行时：

```sh
bash uninstall.sh u123456789
```

卸载只移除所选用户的控制中心、授权规则和管理助手引用，不修改被管理的服务或用户数据。
