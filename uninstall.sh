#!/usr/bin/env bash
set -Eeuo pipefail
NAS_IP="${1:-}";U="${2:-}";D="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";DIRECT=false
if [[ "$(id -u)" == 0 ]]&&command -v plugincenter>/dev/null&&[[ -f /etc/config/plugin ]];then DIRECT=true;[[ "${1:-}" =~ ^u[0-9]+$ ]]&&{ U="$1";NAS_IP="";};fi
if [[ "$DIRECT" != true&&-z "$NAS_IP" ]];then [[ -t 0 ]]||exit 2;read -r -p "请输入设备 IP：" NAS_IP;fi
opts=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
if [[ -z "$U" ]];then if [[ "$DIRECT" == true ]];then mapfile -t us < <(find /home -path '/home/u*/plugin/nascenter' -type d 2>/dev/null|sed -n 's#^/home/\(u[0-9]*\)/.*#\1#p');else mapfile -t us < <(ssh "${opts[@]}" "root@$NAS_IP" "find /home -path '/home/u*/plugin/nascenter' -type d 2>/dev/null"|sed -n 's#^/home/\(u[0-9]*\)/.*#\1#p');fi;((${#us[@]}))||exit 2;if ((${#us[@]}==1));then U="${us[0]}";elif [[ -t 0 ]];then select u in "${us[@]}";do [[ -n "$u" ]]&&{ U="$u";break;};done;else exit 2;fi;fi
[[ "$U" =~ ^u[0-9]+$ ]]||exit 2
if [[ "$DIRECT" == true ]];then exec /bin/sh "$D/remote-uninstall.sh" "$U";fi
ssh "${opts[@]}" "root@$NAS_IP" /bin/sh -s -- "$U" < "$D/remote-uninstall.sh"
