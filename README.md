# ForenChain-DL

### Digital Forensics & Evidence Integrity Platform

ForenChain-DL is a digital forensics application supporting digital
evidence management, integrity verification, chain-of-custody tracking,
machine-learning-assisted image analysis, and structured forensic
reporting.

## Contents

-   [Features](#features)
-   [Requirements](#requirements)
-   [Windows installation](#windows-installation)
-   [MVSS-Net model setup](#mvss-net-model-setup)
-   [Run the application](#run-the-application)
-   [Project structure](#project-structure)
-   [Security and data](#security-and-data)
-   [Troubleshooting](#troubleshooting)

## Features

-   Role-based access control
-   Digital evidence registration and management
-   Evidence integrity verification
-   Chain-of-custody records
-   MVSS-Net-based image manipulation analysis
-   Analysis history
-   Forensic report generation and controlled finalization

## Requirements

-   Windows 10 or later, including Windows 11
-   A Python version compatible with the packages in `requirements.txt`
-   8 GB RAM minimum; 16 GB recommended
-   Internet access for initial package installation and authorized
    model download
-   Sufficient disk space for dependencies, model weights, and evidence

GPU availability is optional; performance depends on hardware and model
configuration.

## Windows installation

### 1. Install Python

Install Python for Windows from
[python.org](https://www.python.org/downloads/windows/). Enable **Add
Python to PATH** during installation.

Verify in PowerShell:

``` powershell
python --version
pip --version
```

### 2. Clone the repository

``` powershell
git clone https://github.com/vigneshPothu23/ForenChainDL.git
cd ForenChainDL
```

### 3. Create and activate a virtual environment

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this for the current terminal
session and activate again:

``` powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## MVSS-Net model setup

The repository includes the MVSS-Net implementation and supporting
source code. The trained checkpoint is distributed separately because of
its large size.

Required checkpoint: `mvssnet_casia.pt`

Expected location:

``` text
ml/
└── mvss/
    └── ckpt/
        └── mvssnet_casia.pt
```

Obtain the checkpoint from the project maintainer through an authorized
distribution method and place it at the path above. Model-dependent
inference will not work until the required checkpoint is available.

## Run the application

From the project root, with `.venv` activated:

``` powershell
streamlit run app.py
```

Open the local URL printed by Streamlit in your browser. Stop the
application with `Ctrl+C`.

## Project structure

``` text
ForenChainDL/
├── .streamlit/
├── forenchain/
├── ml/
│   └── mvss/
├── tests/
├── tools/
├── app.py
├── create_admin.py
├── requirements.txt
└── README.md
```

## Security and data

ForenChain-DL may handle sensitive forensic information.

-   Never publish passwords, API keys, tokens, `.env` files, or
    Streamlit secrets.
-   Keep local databases, evidence files, private reports, and backups
    outside the public repository.
-   Keep model weights and separately distributed datasets outside
    ordinary Git commits unless redistribution is authorized.
-   Share client credentials separately through a secure channel.
-   Back up forensic records before maintenance or migration.
-   Use secure, persistent storage for hosted deployments.

**A fresh Git clone does not include private database records, existing
user accounts, evidence, or the separately distributed model
checkpoint.** These must be provisioned through the approved delivery
process. Do not assume the client's installation will contain the six
existing local user accounts.

## Troubleshooting

**`python` is not recognized:** Reinstall Python with the PATH option
enabled, then reopen PowerShell.

**PowerShell blocks environment activation:** Use the process-scoped
execution policy command in the installation section.

**Dependency installation fails:** Check the Python version and the
specific package error shown by pip.

**The model checkpoint is missing:** Confirm that `mvssnet_casia.pt` is
present in `ml/mvss/ckpt/`.

**The application does not start:** Activate `.venv`, install
`requirements.txt`, and run `streamlit run app.py` from the repository
root.

------------------------------------------------------------------------

**ForenChain-DL --- Digital Forensics, Evidence Integrity, and
Accountable Investigation.**
