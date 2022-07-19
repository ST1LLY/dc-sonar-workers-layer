# DC Sonar Workers Layer

It's the part of the [dc-sonar](https://github.com/ST1LLY/dc-sonar) project

## Run for development

Clone [dc-sonar-workers-layer](https://github.com/ST1LLY/dc-sonar-workers-layer)

```bash
git clone https://github.com/ST1LLY/dc-sonar-workers-layer.git
```

### Windows

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

### Ubuntu

Go to folder where directory with source is located

Deactivate previous venv if uses

```shell
deactivate
```

Create venv

```shell
python3.10 -m venv venv-workers-layer
```

Activate venv

```shell
source venv-workers-layer/bin/activate
```

Install dependencies

```shell
pip install -r dc-sonar-workers-layer/requirements.txt
```

Deactivate venv

```
deactivate
```

### PyCharm settings

See common settings in [common PyCharm settings](https://github.com/ST1LLY/dc-sonar#pycharm-settings)

#### Pylint

Arguments: `--max-line-length=119 --disable=too-few-public-methods,import-error,import-outside-toplevel,broad-except,wrong-import-position,duplicate-code`