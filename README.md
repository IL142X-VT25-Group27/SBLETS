# About
SBLETS is an application or service that makes it possible for a HAPP BLE device to communicate with a LwM2M server.
SBLETS acts as a gateway translating the BLE communication to UDP.
SBLETS also includes other relevant tools and services
that make it possible to perform and host a Bluetooth Low Energy Test of Husqvarna HAPP Devices.

# For LINUX
Run this python application with the systemd SBLETS.service or start the app.py.
Make sure parameters in the systemd and config.ini is correct.

# For Windows
SBLETS is also available as a standalone executable that can be run on its own, but it requires a config.ini file in the root directory of the executable.

## Debug
In Linux debug mode can be activated by running `app.py -v`,
the same applies for the executable which can be started with `SBLETS.exe -v`.

## Compile a new executable
All compile parameters are defined in app.spec and should work for a new compilation.
However, if any new files or libraries are added between compilations, they need to be specified in the spec file.
The hidden_imports variable defines hidden imports,
and datas defines all files that should be included in the executable.
Add any new files here, or if a file is in a folder other than the root, only the folder needs to be specified.
In the root folder, there also exists a SBLETSp3.12 folder which contains all needed python libraries,
and can be used as an interpreter in an IDE.

Compile application with pyinstaller command: `pyinstaller --clean app.spec`