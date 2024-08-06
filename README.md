# Radio Frequency Direction Finding System

The RF-DFS is a controllable 3-meter dish antenna with azimuth and elevation drivers to locate the source of RF interference. This project combines the function of the DFS with the RF - Environmental Monitoring System; a similar utility that is built off of an effectively isotropic antenna. Both RF chains are connected to a Keysight N9040B Spectrum Analyzer and are controlled by an external Python GUI.

## Deployment Requirements

- [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html) or other suitable PyVISA backend.
- [NI-488.2](https://www.ni.com/en/support/downloads/drivers/download.ni-488-2.html#484357)
- Ethernet, [GPIB](https://www.ni.com/en-us/shop/model/gpib-usb-hs.html), serial, or other SCPI instrument connection.

## Development Requirements

- All above requirements.
- [Python 3.6+](https://www.python.org/)
  - [tkinter](https://docs.python.org/3/library/tkinter.html#module-tkinter)
  - [pySerial](https://pypi.org/project/pyserial/)
  - [PyVisa](https://pyvisa.readthedocs.io/en/latest/)
- Suitable Python IDE (Recommended [VSCode](https://code.visualstudio.com/))
- Python packager (Recommended [PyInstaller](https://pyinstaller.org/en/stable/))

> [!NOTE]
> Freezing tools (Such as PyInstaller) package the entire Python Interpreter and installed libraries which generates large executables and could be flagged as a virus. It is recommended to create a virtual environment and only install/package the libraries used in the program. These executables will also only work on the OS that built them (A Windows deployment must be built on a Windows computer).
