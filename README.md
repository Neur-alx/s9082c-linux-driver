# Linux Kernel Driver for SmartChip S9082C / S9082xs Wi-Fi (`02E7:9082` SDIO)

[![Linux Kernel 5.10 - 6.12+](https://img.shields.io/badge/Kernel-5.10%20--%206.12%2B-brightgreen.svg)](https://kernel.org)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![Architecture: ARM / ARM64](https://img.shields.io/badge/Arch-ARM%20%7C%20ARM64-orange.svg)]()
[![Platform: Amlogic S905X / S905W](https://img.shields.io/badge/SoC-Amlogic%20S905X%2FS905W-red.svg)]()

Production-grade, out-of-tree Linux driver for the **SmartChip S9082C / S9082xs / Tilk9082x** SDIO wireless chip (SDIO ID: `02E7:9082`), commonly integrated into millions of budget Amlogic TV boxes (S905X, S905W, S905L, S905D).

---

## 📖 The Story: Solving an 8-Year "Impossible" Mystery

For nearly a decade, the SmartChip S9082C was notorious in the single-board computer (SBC) and TV box communities (Armbian, CoreELEC, LibreELEC, 4PDA, Freaktab). The chip vendor never published an open-source driver—only proprietary Android 3.14 binary object blobs (`9082xs_obj.o`). 

Whenever users attempted to run Armbian or CoreELEC on devices like the **TX3 Mini**, **X96 Mini**, or **Tanix TX3**, Wi-Fi either failed to initialize or suffered from severe packet drops and authentication timeouts. The universal recommendation across developer forums was:

> *"Buy a cheap USB Wi-Fi dongle. S9082C on mainline Linux is completely impossible."*

**That myth is officially debunked.** 

Through extensive reverse-engineering of the original Android binary blob, hardware tracing, and direct RF synthesis debugging, the underlying hardware anomalies have been identified, corrected, and integrated cleanly into a modern Linux kernel module.

---

## 🔬 Reverse-Engineering Breakthroughs

The S9082C shares significant architectural heritage with the Realtek RTL8189ES/RTL8188EU family, but contains unique SmartChip hardware quirks and undocumented register behaviors:

1. **The Core Fix: +25 MHz Synthesizer Offset (`0x4026 = 0xac82`)**
   - *The Symptom:* Beacons were received inconsistently, and WPA2 association failed with timeouts (`association took too long`, `ssid-not-found`) even when standing 1 meter from the AP.
   - *The Discovery:* During baseband initialization, the crystal capacitor control register `0x4024` was leaving upper bits in an invalid state (`0xbc19`), causing the RF synthesizer frequency to lock **+25 MHz above the target 2.4 GHz channel** (e.g. Channel 11 was locking at Channel 16 frequencies).
   - *The Solution:* Setting `rtw_write16(Adapter, 0x4026, 0xac82)` in baseband config forces the synthesizer PLL to lock on exact center frequencies with zero offset (`ch_offset = 0`).

2. **Native Hardware EFUSE & Factory MAC Extraction**
   - Reverse-engineered the 16-bit bit-reversal pattern required for S9082C EFUSE reading, allowing the driver to read the genuine factory MAC address and crystal cap calibration (`0x0c`) directly from chip OTP memory without fake MAC fallback.

3. **Control Register & BSSID Bit Reversals**
   - Corrected 32-bit register inversions in `REG_HMETFR` (`0x41cc`) and BSSID unicast filter matching (`0x4618`), fixing corrupted beacon time stamps and unicast RX drops.

4. **Integrated Dynamic Rate Adaptation (PHYDM)**
   - Enabled real-time signal tracking and MCS rate adaptation (`rtw_s9082_disable_phydm=0`). The driver seamlessly scales between MCS0 and MCS7 based on channel RSSI.

5. **Self-Contained Firmware**
   - The 8051 MCU microcode (`s9082c_fw_nic`) is embedded directly into the driver source code as a C byte array (`hal/rtl8188e/hal8188e_s9082c_fw.c`). **No external firmware files in `/lib/firmware` are required.**

---

## ⚡ Verified Performance Benchmarks

Tested on an **Amlogic S905X TV Box** running **Armbian 26.11** (Linux Kernel `6.12.117-ophub`, ARM64) connected to an AVM FRITZ!Box 7520 (WPA2-CCMP):

| Metric | Result | Notes |
| :--- | :--- | :--- |
| **Real Throughput** | **22.0 – 25.5 MBit/s** | Sustained TCP transfer (iperf3 / curl) |
| **PHY Rate** | **72.2 MBit/s** | 802.11n Wi-Fi 4 (20 MHz, MCS7, SGI) |
| **Ping Latency** | **3.3 – 3.7 ms** | Average RTT to local gateway |
| **Packet Loss** | **0.0%** | Zero dropped packets during 60s load tests |
| **SDIO Bus** | **4-Bit @ 50 MHz** | SDIO High-Speed (200 MBit/s bus limit) |
| **CPU Usage** | **~12–15%** | Highly efficient SDIO tasklet handling |

---

## 📱 Supported Devices & TV Boxes

The S9082C chip (identifiable via `lsmod` / `dmesg` as SDIO ID `02E7:9082`) is found in:

* **TX3 Mini** (Amlogic S905W / S905X)
* **X96 Mini / X96W** (Amlogic S905W)
* **Tanix TX3 Max / TX3 Mini**
* **MXQ Pro 4K** (Amlogic S905X variants)
* **H96 Mini / H96 Pro**
* **Sunvell T95X / T95N**
* Any custom board or embedded device featuring the SmartChip S9082C / S9082xs module.

---

## 🚀 Installation

### Option 1: DKMS Installation (Recommended)
DKMS automatically rebuilds the driver whenever your distribution updates the Linux kernel:

```bash
# 1. Install prerequisites
sudo apt update
sudo apt install -y build-essential dkms git bc

# 2. Clone repository
git clone https://github.com/Neur-alx/s9082c-linux-driver.git
cd s9082c-linux-driver

# 3. Install via DKMS
sudo make dkms_install

# 4. Copy recommended modprobe configuration
sudo cp 8189es.conf /etc/modprobe.d/

# 5. Load module
sudo modprobe 8189es
```

### Option 2: Manual Build & Install

```bash
cd s9082c-linux-driver

# Build module
make -j$(nproc)

# Install module into /lib/modules/$(uname -r)/
sudo make install

# Copy modprobe configuration
sudo cp 8189es.conf /etc/modprobe.d/

# Load driver
sudo modprobe 8189es
```

---

## ⚙️ Module Options (`/etc/modprobe.d/8189es.conf`)

For optimal throughput and connection stability, the following options are recommended:

```ini
# /etc/modprobe.d/8189es.conf
options 8189es rtw_s9082_disable_phydm=0 rtw_power_mgnt=0
```

* `rtw_s9082_disable_phydm=0`: Enables dynamic rate adaptation (3× throughput improvement up to 25.5 MBit/s).
* `rtw_power_mgnt=0`: Disables aggressive power saving to ensure steady low ping (3–4 ms) and prevent drops.

---

## 🔍 Verification

Once loaded, check kernel output with `dmesg`:

```text
Identified SmartChip S9082C / 9082xs (SDIO 02E7:9082)!
S9082C RF Path Switch set to Main (0x404e=0x08)
S9082C LCK done (tmpreg=0x00, lc_cal=0xac820 restored=0xac820)
S9082C IQK done: cand=0 e94=0x100 e9c=0x0 ea4=0x100 eac=0x0
wlan0: IPv6: ADDRCONF(NETDEV_CHANGE): link becomes ready
```

You can now connect to your Wi-Fi network using standard networking tools (`nmcli`, `nmtui`, or `wpa_supplicant`):

```bash
nmcli dev wifi connect "YourSSID" password "YourPassword"
```

---

## 🤝 Contributing & Distributions

We welcome patches, tests on other TV box models, and distribution integrations!
If you are packaging this driver for distributions like **Armbian**, **CoreELEC**, **LibreELEC**, or **EmuELEC**, feel free to open an issue or pull request.

---

## 📄 License

This driver is licensed under the **GNU General Public License v2.0 (GPLv2)**. See [LICENSE](LICENSE) for details.
