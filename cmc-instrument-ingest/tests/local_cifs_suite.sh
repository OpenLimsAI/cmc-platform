#!/bin/bash
# =============================================================================
# 本地 CIFS 回归测试套件 —— 在任意有 Docker 的机器上跑，不需要实验室网络
#
#   Samba 容器提供两个共享（instrument 只读 / nas 可写），
#   特权容器把两者挂成真 CIFS，跑完整采集流程并断言结果。
#
# ⚠️ 覆盖边界见 tests/README.md。最重要的一条：
#    **本地 Samba 的 rename 不会重置 mtime，而生产 NAS 会。**
#    凡涉及 NAS 具体实现行为的结论，必须在真实环境复验。
#
# ⚠️ 后端存储必须用 Docker 卷，不能用 macOS 主机 bind mount——
#    Docker Desktop 的主机文件共享层不支持 SMB 需要的 rename 语义，
#    会让 os.replace 报 [Errno 95]，产生与产品无关的假失败。
#
# 用法：  bash tests/local_cifs_suite.sh
# =============================================================================
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NET=cifs-suite; SRV=cifs-suite-smb; VOL_I=cifs-suite-inst; VOL_N=cifs-suite-nas
RESULT="$(mktemp)"

cleanup() {
  docker rm -f "$SRV" >/dev/null 2>&1
  docker volume rm "$VOL_I" "$VOL_N" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
  rm -f "$RESULT"
}
trap cleanup EXIT

echo "=== 准备 Samba 环境（Docker 卷后端）==="
docker rm -f "$SRV" >/dev/null 2>&1
docker volume rm "$VOL_I" "$VOL_N" >/dev/null 2>&1
docker network create "$NET" >/dev/null 2>&1
docker volume create "$VOL_I" >/dev/null; docker volume create "$VOL_N" >/dev/null

docker run -d --name "$SRV" --network "$NET" \
  -v "$VOL_I":/instrument -v "$VOL_N":/nas \
  dperson/samba:latest -p -u "tester;pass123" \
  -s "instrument;/instrument;yes;yes;no;tester" \
  -s "nas;/nas;yes;no;no;tester" >/dev/null
sleep 8
docker ps --filter name="$SRV" --format '{{.Status}}' | grep -q Up || { echo "Samba 启动失败"; exit 1; }

# 造测试数据（在容器内，避开主机文件共享层）
docker exec "$SRV" sh -c '
  mkdir -p /instrument/Data /instrument/Export /instrument/Images/S1
  for i in 1 2 3; do echo "sample-$i" > /instrument/Data/f$i.txt; done
  echo xls > /instrument/Export/f1.xls
  for i in 1 2; do echo "tif-$i" > /instrument/Images/S1/S1_$i.tif; done
  chmod -R a+rX /instrument; chmod -R a+rwX /nas' >/dev/null
echo "Samba 就绪，测试数据已就位"

docker run --rm --network "$NET" --privileged -v "$REPO":/app python:3.11-slim bash -c '
set -u
apt-get -qq update >/dev/null 2>&1; apt-get -qq install -y cifs-utils >/dev/null 2>&1
mkdir -p /src /nas /local
M="username=tester,password=pass123,vers=3.0"
mount -t cifs //cifs-suite-smb/instrument /src -o "$M,ro" || { echo "@@FAIL 挂载源失败"; exit 1; }
mount -t cifs //cifs-suite-smb/nas        /nas -o "$M"    || { echo "@@FAIL 挂载NAS失败"; exit 1; }
E="VICELL_MACHINE_NAME=LOCAL_ViCell VICELL_SRC_MOUNT=/src VICELL_NAS_MOUNT=/nas \
   VICELL_IMAGES_ORIGIN=/none VICELL_LEGACY_MOUNT=/none VICELL_CONFIG_SOURCE=/none \
   VICELL_LOCAL_STATE_DIR=/local"
HB=/nas/State/LOCAL_ViCell_heartbeat.json

echo "@@CASE 只读源自验：源挂载点必须不可写"
touch /src/__probe 2>/dev/null && echo "@@FAIL 源竟然可写" || echo "@@OK"

echo "@@CASE 正常运行：退出码 0"
env $E python3 /app/vicell/vicell_ingest.py > /tmp/r1.log 2>&1
RC=$?; [ $RC = 0 ] && echo "@@OK" || { echo "@@FAIL 退出码 $RC"; grep ALERT /tmp/r1.log | head -3; }

echo "@@CASE 归档文件数正确（3 txt + 1 xls + 2 tif = 6）"
N=$(find /nas/Daily -type f ! -name ".*" 2>/dev/null | wc -l)
[ "$N" = 6 ] && echo "@@OK" || echo "@@FAIL 实际 $N"

echo "@@CASE SHA256 比对全部 MATCH"
F=$(ls /nas/Checksums/LOCAL_ViCell/*.csv 2>/dev/null | head -1)
if [ -z "$F" ]; then echo "@@FAIL 无比对文件"; else
  # 比对 CSV 由 csv.writer 写出，行尾是 CRLF，比较前必须去掉 \r
  BAD=$(tail -q -n +2 "$F" | tr -d "\r" | awk -F, "\$NF!=\"MATCH\"" | wc -l)
  [ "$BAD" = 0 ] && echo "@@OK" || echo "@@FAIL $BAD 行非 MATCH"; fi

echo "@@CASE metadata 采集到 Windows 创建时间（CIFS xattr）"
F=$(ls /nas/Metadata/LOCAL_ViCell/*.csv 2>/dev/null | head -1)
if [ -z "$F" ]; then echo "@@FAIL 无 metadata 文件"; else
  FULL=$(tail -q -n +2 "$F" | awk -F, "\$9 ~ /xattr/" | wc -l)
  [ "$FULL" -ge 6 ] && echo "@@OK ($FULL 条完整)" || echo "@@FAIL 仅 $FULL 条完整"; fi

echo "@@CASE 心跳字段完整且 SUCCESS"
if [ ! -f "$HB" ]; then echo "@@FAIL 无心跳文件"; else
python3 - "$HB" <<PY
import json,sys
h=json.load(open(sys.argv[1]))
need=["machine_name","last_run_time","last_success_time","backup_status",
      "files_processed","files_failed","software_version","max_silence_hours"]
miss=[k for k in need if k not in h]
print("@@OK" if not miss and h["backup_status"]=="SUCCESS" else f"@@FAIL 缺{miss} 状态{h.get(chr(39)+chr(39))}")
PY
fi

echo "@@CASE 幂等：二次运行新增 0"
env $E python3 /app/vicell/vicell_ingest.py > /tmp/r2.log 2>&1
grep -q "Data   : 新增 0" /tmp/r2.log && echo "@@OK" || { echo "@@FAIL"; grep "Data " /tmp/r2.log; }

echo "@@CASE 归档副本保留源修改时间"
python3 - <<PY
import os
try:
    s=os.stat("/src/Data/f1.txt").st_mtime; d=os.stat("/nas/Daily/LOCAL_ViCell/data/f1.txt").st_mtime
    print("@@OK" if abs(s-d)<=2 else f"@@FAIL 差 {abs(s-d):.1f}s")
except Exception as e: print(f"@@FAIL {e}")
PY

echo "@@CASE 源端删除检测：删源文件后应报告而不删归档"
python3 - <<PY
import json
p="/nas/State/LOCAL_ViCell_backup_state.json"
s=json.load(open(p)); s["data_files"]["__ghost.txt"]={"sha256":"x","size":1,"archived_at":"x"}
json.dump(s, open(p,"w"))
PY
env $E python3 /app/vicell/vicell_ingest.py > /tmp/r3.log 2>&1
grep -q "源端已消失" /tmp/r3.log && echo "@@OK" || echo "@@FAIL 未报告源端删除"

echo "@@CASE NAS 不可写：退出码 1 且本地兜底告警生成"
umount /nas && mount -t cifs //cifs-suite-smb/nas /nas -o "$M,ro"
rm -rf /local/alerts
env $E VICELL_MACHINE_NAME=LOCAL2_ViCell python3 /app/vicell/vicell_ingest.py > /tmp/r4.log 2>&1
RC=$?; A=$(ls /local/alerts/*.jsonl 2>/dev/null | wc -l)
[ $RC = 1 ] && [ "$A" -ge 1 ] && echo "@@OK" || echo "@@FAIL 退出码 $RC 本地告警 $A"

umount /nas && mount -t cifs //cifs-suite-smb/nas /nas -o "$M"
echo "@@CASE 心跳巡检：新鲜心跳 -> 退出码 0"
python3 /app/tools/heartbeat_check.py --state-dir /nas/State --quiet >/dev/null 2>&1
[ $? = 0 ] && echo "@@OK" || echo "@@FAIL"

echo "@@CASE 心跳巡检：陈旧心跳 -> 退出码 1"
python3 - "$HB" <<PY
import json,sys,datetime as dt
h=json.load(open(sys.argv[1]))
h["last_success_time"]=(dt.datetime.now().astimezone()-dt.timedelta(hours=500)).isoformat()
json.dump(h, open(sys.argv[1],"w"))
PY
python3 /app/tools/heartbeat_check.py --state-dir /nas/State >/dev/null 2>&1
[ $? = 1 ] && echo "@@OK" || echo "@@FAIL"
' > "$RESULT" 2>&1

echo
echo "=== 测试结果 ==="
PASS=0; FAIL=0
while IFS= read -r line; do
  case "$line" in
    @@CASE*) printf "  %-46s" "${line#@@CASE }";;
    @@OK*)   echo "✅ ${line#@@OK}"; PASS=$((PASS+1));;
    @@FAIL*) echo "❌ ${line#@@FAIL }"; FAIL=$((FAIL+1));;
    *) [ -n "$line" ] && echo "       $line";;
  esac
done < "$RESULT"

echo
echo "=================================================="
printf " 通过 %d   失败 %d\n" "$PASS" "$FAIL"
[ "$FAIL" = 0 ] && echo " 结论：全部通过 ✅" || echo " 结论：有失败项 ❌"
echo "=================================================="
[ "$FAIL" = 0 ]
