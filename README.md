# 小米智能存储控制中心

在小米智能存储 APP 内集中查看设备健康状态，并执行经过白名单限制的维护操作。

## 功能

- CPU 使用率、系统负载、运行时间与 CPU 温度
- 内存使用量、可用内存与可释放页缓存
- 当前物理网卡实时上传/下载速度、累计流量、错误和丢包
- 用户存储池、系统数据、Docker 镜像及存储卷目录（`/data/docker_data`）、日志和固件分区空间
- SATA/NVMe SMART 健康、温度、通电时间与坏扇区相关指标
- 点击硬盘查看完整 SMART 属性、设备信息、错误日志与自检记录
- Docker、Samba、定时任务、Mihomo 和文件快传服务状态及一键重启
- 安全释放 Linux 页缓存
- 将 systemd 日志保留 7 天并控制在约 32 MB
- Android / iOS 安全区、沉浸式状态栏和左右滑动切页

## 安装

```sh
cd nas-center-plugin
bash deploy.sh
```

也可以指定设备和用户：

```sh
bash deploy.sh 192.168.31.100 u123456789
```

在小米智能存储本机 root SSH 中运行时：

```sh
bash deploy.sh u123456789
```

## 安全设计

APP 页面不直接拥有 root 权限。安装器创建 root 所有的固定权限助手：

```text
/data/plugin/.nascenter-system/nas-center-helper
```

助手只接受大小受限的 JSON，并只允许以下动作：读取状态、读取 SMART、重启预定义服务、释放页缓存和整理 systemd 日志。服务名称不能由页面拼接为任意命令。

空间清理不会清空回收站，也不会删除照片、视频、下载文件、Docker 容器、镜像或存储卷。

## 卸载

```sh
bash uninstall.sh
```

卸载只移除控制中心、权限助手和授权规则，不修改被管理的服务或用户数据。
