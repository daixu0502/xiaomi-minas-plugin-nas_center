#!/usr/bin/env bash
set -Eeuo pipefail
NAS_IP="${1:-}"; PLUGIN_USER="${2:-}"; SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIRECT=false
if [[ "$(id -u)" == 0 ]] && command -v plugincenter >/dev/null 2>&1 && [[ -f /etc/config/plugin ]]; then DIRECT=true; [[ "${1:-}" =~ ^u[0-9]+$ ]] && { PLUGIN_USER="$1"; NAS_IP=""; }; fi
if [[ "$DIRECT" != true && -z "$NAS_IP" ]]; then [[ -t 0 ]] || { echo "错误：请运行 bash deploy.sh <设备IP> [插件用户]" >&2; exit 2; }; read -r -p "请输入设备 IP：" NAS_IP; fi
ssh_options=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
choose(){ local users=("$@"); ((${#users[@]})) || { echo "错误：没有插件用户" >&2; exit 2; }; if ((${#users[@]}==1)); then PLUGIN_USER="${users[0]}"; return; fi; [[ -t 0 ]] || { echo "错误：多个用户，请显式指定" >&2; exit 2; }; select u in "${users[@]}"; do [[ -n "$u" ]]&&{ PLUGIN_USER="$u";break;};done; }
if [[ -z "$PLUGIN_USER" ]]; then users=(); if [[ "$DIRECT" == true ]]; then shopt -s nullglob; for f in /data/plugin/u*.list; do u="${f##*/}";u="${u%.list}";[[ "$u" =~ ^u[0-9]+$ ]]&&users+=("$u");done;shopt -u nullglob; else mapfile -t users < <(ssh "${ssh_options[@]}" "root@$NAS_IP" 'for f in /data/plugin/u*.list; do u=${f##*/};u=${u%.list};case "$u" in u[0-9]*) [ -d "/home/$u" ]&&echo "$u";;esac;done'|sort -u);fi;choose "${users[@]}";fi
[[ "$PLUGIN_USER" =~ ^u[0-9]+$ ]]||exit 2
work=$(mktemp -d); trap 'case "$work" in /tmp/*) rm -rf "$work";;esac' EXIT HUP INT TERM; stage="$work/nas-center-plugin";mkdir -p "$stage";cp -R "$SCRIPT_DIR/payload" "$stage/payload";cp "$SCRIPT_DIR/remote-install.sh" "$stage/remote-install.sh"
if [[ "$DIRECT" == true ]]; then /bin/sh "$stage/remote-install.sh" "$PLUGIN_USER";exit;fi
tar -C "$work" -czf "$work/plugin.tgz" nas-center-plugin;remote="/tmp/nas-center-$$-$RANDOM.tgz";scp "${ssh_options[@]}" "$work/plugin.tgz" "root@$NAS_IP:$remote";ssh "${ssh_options[@]}" "root@$NAS_IP" "R='$remote' U='$PLUGIN_USER' /bin/sh -s" <<'REMOTE'
set -eu;t=/tmp/nas-center-install-$$;trap 'rm -rf "$t" "$R"' EXIT HUP INT TERM;mkdir -p "$t";tar -xzf "$R" -C "$t";/bin/sh "$t/nas-center-plugin/remote-install.sh" "$U"
REMOTE
echo "控制中心安装完成。"
