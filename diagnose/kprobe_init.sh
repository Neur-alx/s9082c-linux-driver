#!/bin/sh
# Phase 2b: Live-Capture aller Register-Writes von rtl8188es_hal_init()
# via Kprobe. AUF EINER FRISCH KALTGESTARTETEN BOX ausfuehren, BEVOR
# irgendwann "ip link set wlan0 up" lief (wegen bMacPwrCtrlOn-Bypass in
# _InitPowerOn_8188ES wuerde sonst der Power-On-Teil fehlen).
#
# Ablauf: buffer vergroessern -> kprobes setzen -> EINMALIG ip link up -> trace sichern.
set -e
TR=/sys/kernel/debug/tracing
OUT=/root/s9test/kprobe_init_trace.txt

echo "=== wlan0 status (soll DOWN/unmanaged sein, noch KEIN ip up) ==="
ip -br link wlan0 2>/dev/null || echo "wlan0 not present"
cat /sys/module/8189es/parameters/rtw_s9082_fixchan 2>/dev/null || true

echo "=== buffer_size_kb = 16384 ==="
echo 16384 > $TR/buffer_size_kb 2>/dev/null || echo "buffer set failed"
cat $TR/buffer_size_kb

echo "=== kprobes setzen ==="
cd $TR
# alte kprobes saeubern
echo > kprobe_events 2>/dev/null || true
# _rtw_write8/16/32 (addr=%x1:x32 val=%x2:x32) + _sdio_local_write
echo "p:rtw_w8 _rtw_write8 addr=%x1:x32 val=%x2:x32" >> kprobe_events 2>&1 || echo "kprobe w8 failed"
echo "p:rtw_w16 _rtw_write16 addr=%x1:x32 val=%x2:x32" >> kprobe_events 2>&1 || echo "kprobe w16 failed"
echo "p:rtw_w32 _rtw_write32 addr=%x1:x32 val=%x2:x32" >> kprobe_events 2>&1 || echo "kprobe w32 failed"
echo "p:sdio_wloc _sdio_local_write addr=%x1:x32 val=%x2:x32" >> kprobe_events 2>&1 || echo "kprobe sdio failed (evtl. nicht symbol)" || true
cat kprobe_events

echo "=== events aktivieren + tracer ==="
echo 1 > events/kprobes/enable 2>/dev/null || true
echo function > current_tracer 2>/dev/null || true
echo 0 > tracing_on
echo > trace

echo "=== EINMALIG ip link set wlan0 up (Init laeuft) ==="
echo 1 > tracing_on
ip link set wlan0 up
echo "ip_up_rc=$?"
sleep 3
echo 0 > tracing_on

echo "=== trace sichern ==="
cp trace $OUT
echo "trace zeilen: $(wc -l < $OUT)"

echo "=== kprobes saeubern ==="
echo 0 > events/kprobes/enable 2>/dev/null || true
echo > kprobe_events 2>/dev/null || true
sync
echo "DONE. Trace: $OUT"