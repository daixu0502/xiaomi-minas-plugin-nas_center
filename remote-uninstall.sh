#!/bin/sh
set -eu
u=${1:-};case "$u" in u[0-9]*) ;;*)exit 1;;esac
home="/home/$u/plugin/nascenter";list="/data/plugin/$u.list";src="";tmp="";[ -L "$home/src" ]&&src=$(readlink "$home/src" 2>/dev/null||true);[ -L "$home/tmp" ]&&tmp=$(readlink "$home/tmp" 2>/dev/null||true);plugincenter -u "$u" -p nascenter disable>/dev/null 2>&1||true
if [ -f "$list" ]&&jq empty "$list">/dev/null 2>&1;then t="$list.nascenter-uninstall.$$";jq 'del(.nascenter)' "$list">"$t";chmod --reference="$list" "$t" 2>/dev/null||chmod 0644 "$t";chown --reference="$list" "$t" 2>/dev/null||true;mv -f "$t" "$list";fi
rm -f "/data/plugin/www/$u/nascenter" "/etc/sudoers.d/nascenter-$u" "/data/plugin/.$u.nascenter.lock"
case "$src" in /nas/pool*/"$u"/plugin/pluginsrc/nascenter)rm -rf "$src";;esac
case "$tmp" in /nas/pool*/"$u"/plugin/plugintmp/nascenter)rm -rf "$tmp";;esac
[ "$home" = "/home/$u/plugin/nascenter" ]&&rm -rf "$home"
if ! find /etc/sudoers.d -name 'nascenter-u*'|grep -q .;then rm -rf /data/plugin/.nascenter-system;rm -f /data/plugin/www/icon/nascenter.icon;fi
echo '控制中心已卸载。'
