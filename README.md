# DC Sonar Workers Layer

It's the part of [dc-sonar](https://github.com/ST1LLY/dc-sonar) project

## Run for development

### Windows

Clone [dc-sonar-workers-layer](https://github.com/ST1LLY/dc-sonar-workers-layer)

```bash
git clone https://github.com/ST1LLY/dc-sonar-workers-layer.git
```

Open Powershell, cd to created dc-sonar-workers-layer folder

Create Python virtual environment

```powershell
&"C:\Program Files\Python310\python.exe" -m venv venv
```

Active venv

```
.\venv\Scripts\Activate.ps1
```

Install python_ldap‑3.4.0‑cp310‑cp310‑win_amd64.whl

```
pip install .\windows_whl\python_ldap-3.4.0-cp310-cp310-win_amd64.whl
```

Install pip packages

```
pip install -r .\requirements.txt
```

