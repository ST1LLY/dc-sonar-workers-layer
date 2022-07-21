# DC Sonar Workers Layer

It is part of the [dc-sonar](https://github.com/ST1LLY/dc-sonar) project.

## Deploy for development

Clone [dc-sonar-workers-layer](https://github.com/ST1LLY/dc-sonar-workers-layer)

```bash
git clone https://github.com/ST1LLY/dc-sonar-workers-layer.git
```

### Windows

Open Powershell.

Go to the created dc-sonar-workers-layer folder:

```
cd {YOUR_PATH}
```

Create Python virtual environment

```powershell
&"C:\Program Files\Python310\python.exe" -m venv venv
```

Active created venv:

```
.\venv\Scripts\Activate.ps1
```

Install the python_ldap‑3.4.0‑cp310‑cp310‑win_amd64.whl package:

```
pip install .\windows_whl\python_ldap-3.4.0-cp310-cp310-win_amd64.whl
```

Install pip packages:

```
pip install -r .\requirements.txt
```

### Ubuntu

Go to the folder where the directory with the source is located.

Deactivate the previous venv if it uses:

```shell
deactivate
```

Create venv:

```shell
python3.10 -m venv venv-workers-layer
```

Activate created venv:

```shell
source venv-workers-layer/bin/activate
```

Install dependencies:

```shell
pip install -r dc-sonar-workers-layer/requirements.txt
```

Deactivate venv:

```
deactivate
```

### Config

Copy `configs/settings_blank.conf` to `configs/settings.conf`.

Set the params:

The param `aes_256_key` in `APP` section is being used for decryption and encryption saved passed of accounts have been bruted.

The `DB` section is being used for connection to `back_workers_db`.

Example:

```ini
[APP]
aes_256_key=8^xjD=0v3Lk_1QNZW+1sb6u)oDQw0nhcPvu^gh:jHCyR*}jn+_T#Ak%*>3p_yvZe

[RMQ]
host=localhost

[NTLM_SCRUT]
host=localhost
port=5000

[DB]
user=dc_sonar_workers_layer
pass=3I98mM1Hz!O8
host=localhost
port=5432

[LOG]
level=INFO
```

Before the first run, it is needed to init models.

Open terminal.

Activate venv and go to the project directory:

```shell
source venv-workers-layer/bin/activate
cd dc-sonar-workers-layer/
```

Init scheduled jobs for the first connection to DB:

```shell
python sheduled_jobs.py
```

Press CTRL+C to stop after the log string shows  "Scheduler started".

Run alembic migrations:

```shell
alembic upgrade heads
```

### Run

Open terminal.

Execute commands for running ntlm_dump_job_runner:

```
source venv-workers-layer/bin/activate
cd dc-sonar-workers-layer/
python ntlm_dump_job_runner.py
```

Open terminal.

Execute commands for running sheduled_jobs:

```
source venv-workers-layer/bin/activate
cd dc-sonar-workers-layer/
python sheduled_jobs.py
```

Open terminal.

Execute commands for running no_exp_pass_job_runner:

```
source venv-workers-layer/bin/activate
cd dc-sonar-workers-layer/
python no_exp_pass_job_runner.py
```

Open terminal.

Execute commands for running reused_pass_job_runner:

```
source venv-workers-layer/bin/activate
cd dc-sonar-workers-layer/
python reused_pass_job_runner.py
```

