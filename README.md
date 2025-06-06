# :satellite: Radio Frequency Direction Finding System

The RF-DFS is a movable 3-meter dish antenna with azimuth and elevation drivers to locate the source of RF interference. This project combines the function of the DFS with the RF - Environmental Monitoring System; a similar utility that is built off of an effectively isotropic antenna. Both RF chains are connected to a Keysight N9040B Spectrum Analyzer and are controlled by a Python GUI.

**Hardware:** Automation Direct P1AM-100 PLC with 15-point discrete output module, Parker Hannifin ACR9000 Motion Controller, 2 Aries AR-04AE Servo Drives, Keysight N9040B Spectrum Analyzer, and a Windows computer.

## 🏗️ Tech Stack

```mermaid
graph BT

    subgraph Hardware
    P1AM
    win[Windows Machine]
    ACR9000
    AR-04AE
    N9040B
    end

    subgraph Firmware
    C++
    AcroBASIC
    SCPI
    end

    subgraph client[Edge Client]
    Python([Python Front End])
    end

    subgraph Back End
    Database[(DRIFT<br>Database)]
    end

    C++ -->|Serial| Python
    AcroBASIC -->|Serial| Python
    SCPI -->|GPIB/LAN| Python

    P1AM --> C++
    win --> Python
    ACR9000 & AR-04AE --> AcroBASIC
    N9040B --> SCPI
    client --> Database
```

## 🚀 Deployment Requirements

- [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html) or other suitable PyVISA backend.
- Ethernet, GPIB, serial, or other SCPI instrument connection.
  - [NI-488.2](https://www.ni.com/en/support/downloads/drivers/download.ni-488-2.html#484357) if using GPIB.

## 🛠️ Development Requirements

- All above requirements.
- [Python 3.11+](https://www.python.org/) and an understanding of the following:
  - [tkinter](https://docs.python.org/3/library/tkinter.html#module-tkinter)
  - [pySerial](https://pypi.org/project/pyserial/)
  - [PyVisa](https://pyvisa.readthedocs.io/en/latest/)
  - [matplotlib](https://matplotlib.org/)
- Suitable Python IDE (Recommended [VSCode](https://code.visualstudio.com/))
- Python packager (Recommended [PyInstaller](https://pyinstaller.org/en/stable/))
- [PlatformIO](https://platformio.org/) for updating PLC firmware.

> [!NOTE]
> Freezing tools (Such as PyInstaller) package the entire Python Interpreter and installed libraries which generates large executables and could be flagged as a virus. It is recommended to create a virtual environment and only install/package the libraries used in the program. These executables will also only work on the OS that built them (A Windows deployment must be built on a Windows computer).

### Packages

```bash
pip install pyserial
```

```bash
pip install pyvisa
```

```bash
pip install matplotlib
```

```bash
pip install numpy
```

```bash
pip install apscheduler
```

```bash
pip install ttkthemes
```

```bash
pip install tkcalendar
```

```bash
pip install tktimepicker
```

## :mailbox: Authors

- [Remy Nguyen](https://github.com/RomiFC)
- [Hina Suzuki](https://github.com/hina18201716)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://public.nrao.edu/wp-content/uploads/2023/02/logoGroupWhite.png">
  <source media="(prefers-color-scheme: light)" srcset="https://public.nrao.edu/wp-content/uploads/2023/02/logoGroupColor.png">
  <img alt="If previous images cannot be displayed" src="https://public.nrao.edu/wp-content/uploads/2023/02/logoGroupColor.png">
</picture>
