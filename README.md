# USR-M300-EW IoT Gateway Simulation

> Aplikasi ini digunakan untuk mensimulasikan USR-M300-EW IoT Gateway, menggunakan data dummy yang dihasilkan dari simulasi sensor. Aplikasi ini juga digunakan untuk mensimulasikan kontroler yang dapat membaca data sensor dan memanipulasi aktuator atau perangkat lainnya dalam ekosistem gateway. Protokol yang digunakan dalam aplikasi ini adalah TCP/IP dan Modbus (komunikasi serial diubah menjadi TCP/IP untuk memudahkan penggunaan).

## Dependencies

```bash
pip install pyModbusTCP
```

## Fungsi Aplikasi

### M300_sim.py
Aplikasi ini mensimulasikan USR-M300-EW IoT gateway yang berfungsi sebagai **komunikasi hub** bidirectional antara kontroler dengan sensor dan aktuator. Gateway ini mengimplementasikan **Dual Protocol** dengan bertindak sebagai:
- **TCP Server** untuk sensor digital dan aktuator (port 5000 dan 5001)
- **Modbus Server** untuk sensor kualitas air (port 502)
- **TCP Client** yang terhubung ke controller (port 6000)

**Alur Kerja Gateway:**

1. **Menerima Data Sensor:**
   - **Digital sensors** → TCP connection (port 5000) → parse dan forward ke controller
   - **Modbus sensors** → Modbus registers (port 502) → read, parse, dan forward ke controller

2. **Mengirim Feedback ke Controller:**
   - Semua data sensor diteruskan melalui TCP connection ke controller (port 6000)
   - Format pengiriman: `TCP|DIGITAL|data` atau `MODBUS|data`

3. **Menerima dan Meneruskan Perintah:**
   - Menerima perintah actuator dari controller melalui `listen_to_controller()`
   - Broadcast perintah ke semua actuator yang terhubung melalui `forward_to_actuator()`

4. **Monitoring Actuator:**
   - Menerima status feedback dari actuator
   - Meneruskan status actuator kembali ke controller untuk monitoring

**Data yang didukung:**

**Modbus (Water Quality Sensors):**
1. pH - Register 0
2. TSS - Register 10
3. COD - Register 20
4. Ammonia - Register 30  

**Digital (TCP - Physical/Operational Sensors):**
1. Status Alat
2. Status Pompa
3. Status Alarm
4. Flow Rate Air  
5. Posisi Aktuator

Gateway hanya meneruskan data yang **berubah** untuk menghindari spam ke controller.

### controller_sim.py
Aplikasi ini bertindak sebagai **Water Treatment Controller** yang mengimplementasikan logika kontrol otomatis berdasarkan data sensor. Controller berfungsi untuk:

**1. Data Reception & Processing:**
- Mendengarkan pada **port 6000** sebagai TCP server
- Parsing data dari gateway dengan format: `MODBUS|` atau `TCP|DIGITAL|`
- Menyimpan data sensor terbaru dalam `self.sensor_data`

**2. Decision Making Logic:**
Controller mengimplementasikan logika kontrol otomatis untuk sistem pengolahan air:

- **pH Control**: 
  - pH < 6.5 → `PUMP_ALKALI|START|50` (tambah basa)
  - pH > 8.5 → `PUMP_ACID|START|30` (tambah asam)
  - pH normal → stop kedua pompa

- **TSS Control**:
  - TSS > 100 mg/L → `VALVE_BACKWASH|OPEN|100` (backwash filter)
  - TSS normal → `VALVE_BACKWASH|CLOSE|0`

- **Flow Control**:
  - Flow < 20 L/min → `MAIN_PUMP|START|75` (increase pump speed)  
  - Flow > 45 L/min → `MAIN_PUMP|REDUCE|40` (reduce pump speed)

**3. Command Transmission:**
- Mengirim perintah actuator melalui `send_actuator_command()`
- Format perintah: `ACTUATOR_CMD|DEVICE_NAME|ACTION|VALUE`
- Perintah dikirim ke gateway (port 6000) yang kemudian diteruskan ke actuator

**4. Maintenance Operations:**
- Periodic commands setiap 30 detik untuk maintenance
- Status LED blinking dan system check

**Contoh Data yang Diproses:**
- **Modbus**: `"MODBUS|pH:7.25|TSS:85|COD:150|Ammonia:2.35"`
- **Digital (TCP)**: `"TCP|DIGITAL|FLOW:35.7L/min|ACTUATOR:45.2%|STATUS:OK|PUMP:ON|ALARM:NORMAL|TS:1674567890"`

**Actuator yang Dapat Dikontrol:**
- **Pump**: `MAIN_PUMP` (mengatur flow), `PUMP_ACID` (menurunkan pH), `PUMP_ALKALI` (menaikkan pH)
- **Valve**: `VALVE_BACKWASH` (mengatur TSS)
- **LED**: `STATUS_LED` (status indicator)

> **⚠️ Penting**: Ketika memulai aplikasi `actuator_sim.py`, pastikan nama sesuai dengan list diatas

### digital_sensor_sim.py
Aplikasi ini digunakan untuk mensimulasikan sensor digital yang terhubung ke gateway M300 melalui komunikasi TCP (**port 5000**). Aplikasi ini mensimulasikan koneksi kabel/serial yang diubah menjadi TCP untuk memudahkan pengujian.

Sensor digital yang disimulasikan menghasilkan data operasional sistem pengolahan air, meliputi:
- **Flow Rate**: Kecepatan aliran air dalam L/min (10.0 - 50.0 L/min)
- **Actuator Position**: Posisi aktuator dalam persentase (0-100%)
- **Signal Status**: Status sinyal perangkat (OK, WARN, FAULT)
- **Pump Status**: Status pompa utama (ON, OFF)
- **Alarm Status**: Status alarm sistem (NORMAL, ALARM)
- **Timestamp**: Waktu pengambilan data

**Format data yang dikirim**: 
```
DIGITAL|FLOW:35.7L/min|ACTUATOR:45.2%|STATUS:OK|PUMP:ON|ALARM:NORMAL|TS:1674567890
```

Aplikasi ini akan terus mengirim data setiap **3 detik** dan menunggu acknowledgment (ACK) dari gateway M300. Jika koneksi terputus, aplikasi akan secara otomatis mencoba untuk terhubung kembali.

### modbus_sensor_sim.py
Aplikasi ini mensimulasikan sensor kualitas air yang menggunakan protokol MODBUS untuk berkomunikasi dengan gateway M300 (**port 502**). Aplikasi ini mensimulasikan sensor-sensor yang umumnya digunakan dalam sistem pengolahan air limbah.

Sensor MODBUS yang disimulasikan meliputi:
- **pH Sensor**: Mengukur tingkat keasaman air (6.0 - 9.0 pH) - Register 0
- **TSS (Total Suspended Solids)**: Mengukur padatan tersuspensi (5 - 150 mg/L) - Register 10
- **COD (Chemical Oxygen Demand)**: Mengukur kebutuhan oksigen kimia (10 - 300 mg/L) - Register 20
- **Ammonia**: Mengukur kadar ammonia (0.1 - 10.0 mg/L) - Register 30
- **Flow**: Mengukur aliran tambahan (50 - 500 L/min) - Register 40
- **Pressure**: Mengukur tekanan sistem (0.5 - 3.0 bar) - Register 50

Setiap sensor menulis data ke register MODBUS yang telah ditentukan dengan menggunakan multiplier untuk presisi (misalnya pH dikalikan 100 untuk mendapatkan desimal). Aplikasi mengirim data setiap **5 detik** dan menampilkan nilai yang ditulis ke register.

Aplikasi menggunakan library `pyModbusTCP` untuk komunikasi MODBUS dan akan secara otomatis mencoba terhubung kembali jika koneksi terputus.

### actuator_sim.py
Aplikasi ini mensimulasikan aktuator dalam sistem pengolahan air yang menerima perintah dari kontroler melalui gateway M300 (**port 5001**). Aplikasi mendukung berbagai jenis aktuator dengan ID yang telah ditentukan.

#### Jenis Aktuator yang Didukung:

**PUMP (Pompa):**
- `MAIN_PUMP`: Pompa utama untuk mengatur flow rate air
- `PUMP_ALKALI`: Pompa dosing untuk menaikkan pH (menambah basa)
- `PUMP_ACID`: Pompa dosing untuk menurunkan pH (menambah asam)

**VALVE (Katup):**
- `VALVE_BACKWASH`: Katup untuk proses backwash/pembersihan filter

**LED (Indikator):**
- `STATUS_LED`: LED indikator status sistem

#### Perintah yang Dapat Diterima:
- **Pompa**: `START` (mulai dengan kecepatan tertentu), `STOP` (berhenti), `REDUCE` (kurangi kecepatan)
- **Katup**: `OPEN` (buka dengan persentase tertentu), `CLOSE` (tutup)
- **LED**: `ON` (nyala), `OFF` (mati), `BLINK` (berkedip)

**Format perintah**: `ACTUATOR_CMD|DEVICE_NAME|ACTION|VALUE`

**Contoh**: `ACTUATOR_CMD|MAIN_PUMP|START|75` (start pompa utama dengan kecepatan 75%)

#### Fitur Aplikasi:
- **Command Parsing**: Memproses buffer untuk menangani multiple perintah
- **Status Feedback**: Mengirim status kembali ke kontroler setiap 10 detik
- **Operation Simulation**: Simulasi operasi realistis termasuk kemungkinan fault (1% untuk pompa)
- **Auto Reconnection**: Otomatis terhubung kembali jika koneksi terputus

**Format status yang dikirim**: `STATUS|ACTUATOR_ID|STATUS|POS:position|SPEED:speed|TS:timestamp`

Saat menjalankan aplikasi, pengguna akan diminta memasukkan jenis aktuator (PUMP/VALVE/LED) dan ID aktuator sesuai dengan daftar yang telah ditentukan di atas.

## Cara Menjalankan Simulasi

Jalankan tiap program secara **berurutan**:

1. **Jalankan Controller**: `python controller_sim.py`
2. **Jalankan M300 Gateway**: `python M300_sim.py`
3. **Jalankan Aktuator**: `python actuator_sim.py`
4. **Jalankan Sensor Digital**: `python digital_sensor_sim.py`
5. **Jalankan Sensor MODBUS**: `python modbus_sensor_sim.py`

## Arsitektur Sistem
![Diagram Arsitektur](app_diagram.png)

---

# M300 Water Treatment Controller - Dokumentasi REST API

## Endpoint API

### Base URL
```
http://127.0.0.1:5555
```

---

### 1. Dapatkan Pembacaan Sensor Terbaru

**Endpoint:** `GET /api/sensors`

**Deskripsi:** Mengambil data sensor terbaru dari semua sensor yang terhubung.

**Format Respon:**
```json
{
  "timestamp": "2025-07-28T15:30:45.123456",
  "sensors": {
    "pH": 7.2,
    "TSS": 85.5,
    "FLOW": "35.2L/min",
    "TEMPERATURE": 22.5,
    "PRESSURE": 2.1,
    "LEVEL": "75%"
  }
}
```

**Contoh Request:**
```bash
curl -X GET http://127.0.0.1:5555/api/sensors
```

---

### 2. Dapatkan Histori Data Sensor

**Endpoint:** `GET /api/history`

**Deskripsi:** Mengambil data historis sensor, perintah aktuator, dan kejadian sistem.

**Parameter Query:**
- `limit` (opsional): Jumlah record yang dikembalikan (default: 100, maksimal: 1000)

**Format Respon:**
```json
{
  "history": [
    {
      "timestamp": "2025-07-28T15:30:45.123456",
      "type": "sensor",
      "data": {
        "pH": 7.2,
        "TSS": 85.5
      }
    },
    {
      "timestamp": "2025-07-28T15:30:50.123456",
      "type": "actuator",
      "data": {
        "PUMP_ALKALI": {
          "status": "START",
          "value": 50
        }
      }
    },
    {
      "timestamp": "2025-07-28T15:30:55.123456",
      "type": "alarm",
      "data": "pH terlalu rendah (6.2), menambahkan alkali"
    }
  ],
  "total_records": 150
}
```

**Contoh Request:**
```bash
# Dapatkan 100 record terakhir (default)
curl -X GET http://127.0.0.1:5555/api/history

# Dapatkan 50 record terakhir
curl -X GET http://127.0.0.1:5555/api/history?limit=50

# Dapatkan semua record yang tersedia
curl -X GET http://127.0.0.1:5555/api/history?limit=1000
```

---

### 3. Hapus Histori Data Sensor

**Endpoint:** `DELETE /api/clear-history`

**Deskripsi:** Menghapus semua data historis yang tersimpan.

**Format Respon:**
```json
{
  "status": "success",
  "message": "History cleared"
}
```

**Contoh Request:**
```bash
curl -X DELETE http://127.0.0.1:5555/api/clear-history
```

---

## Tipe Data Sensor

| Sensor | Tipe | Unit | Deskripsi |
|--------|------|------|-----------|
| `pH` | float | unit pH | Tingkat pH air (0-14) |
| `TSS` | float | mg/L | Total Suspended Solids |
| `FLOW` | string | L/min | Laju aliran air |
| `TEMPERATURE` | float | °C | Suhu air |
| `PRESSURE` | float | bar | Tekanan sistem |
| `LEVEL` | string | % | Persentase level tangki |

---

## Penanganan Error

Semua endpoint mengembalikan kode status HTTP yang sesuai:

- `200 OK` - Request berhasil
- `400 Bad Request` - Parameter tidak valid
- `500 Internal Server Error` - Error server

**Format Respon Error:**
```json
{
  "error": "Pesan deskripsi error"
}
```

---

## Arsitektur Sistem

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Sensor        │    │   M300 Gateway  │    │   Controller    │
│  (TCP/MODBUS)   │───▶│   (Port 5000)   │───▶│   (Port 6000)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   REST API      │
                                               │   (Port 5555)   │
                                               └─────────────────┘
```

---

## Konfigurasi

### Konfigurasi Jaringan
```python
controller_ip = '127.0.0.1'
controller_port = 6000    # Koneksi M300 Gateway
api_port = 5555          # Port server REST API
```

### Batas Penyimpanan Data
- **Record Historis:** 1.000 entri (FIFO)
- **Riwayat Alarm:** 10 entri (FIFO)
- **Penggunaan Memori:** ~205KB maksimal

---