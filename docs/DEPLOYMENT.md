## Deploy / Build (cross-platform)

Приложение кроссплатформенное на уровне **одной кодовой базы** (Python + Flet).
Сборка под разные платформы делается через `flet build`.

### Desktop (Windows) — `scripts/build_win.ps1`

Сборка инкапсулирована в [`scripts/build_win.ps1`](../scripts/build_win.ps1). Скрипт делает
шесть шагов; каждый — опциональный.

| # | Шаг              | Когда пропускается                                |
|---|------------------|---------------------------------------------------|
| 1 | venv + deps      | `-NoVenv`                                         |
| 2 | ruff/mypy/pytest | `-SkipChecks`                                     |
| 3 | `flet build`     | `-SkipBuild`                                      |
| 4 | подпись `.exe`   | не задан `-CertPath` или нет `signtool.exe`       |
| 5 | Inno Setup       | `-SkipInstaller` или нет `iscc.exe` в PATH        |
| 6 | подпись `.exe` инсталлера | автоматически, если оба условия (cert + signtool) выполнены |

#### Базовая сборка (без подписи)

```powershell
.\scripts\build_win.ps1
```

Артефакт: `build\windows\PersonalFinance.exe` (голый `.exe`, без подписи — Windows
SmartScreen покажет пользователю предупреждение).

#### Сборка инсталлера

Поставить **Inno Setup 6+** с [jrsoftware.org](https://jrsoftware.org/isinfo.php),
убедиться, что `iscc.exe` есть в `PATH`. Дальше:

```powershell
.\scripts\build_win.ps1 -Version 1.0.1
```

Артефакт: `build\installer\PersonalFinance-Setup-1.0.1.exe` — обычный мастер
с выбором каталога, иконкой в Start Menu, опциональным desktop-shortcut и
встроенным uninstaller'ом.

Если `-Version` не задан, скрипт читает версию из `git describe --tags --abbrev=0`.

#### Подпись (Authenticode)

Чтобы Windows SmartScreen не блокировал .exe, нужен **code-signing сертификат
от CA** (DigiCert, Sectigo, GlobalSign — ~200–500 $/год; EV-сертификат, который
сразу даёт repuation, — ~600 $/год). После получения `.pfx`:

```powershell
.\scripts\build_win.ps1 `
  -Version 1.0.1 `
  -CertPath C:\certs\pfm.pfx `
  -CertPassword (Read-Host -AsSecureString | ConvertFrom-SecureString -AsPlainText)
```

Безопаснее не передавать пароль аргументом, а положить его в переменную
окружения `PFM_CERT_PASSWORD` — скрипт подхватит автоматически:

```powershell
$env:PFM_CERT_PASSWORD = (Read-Host -AsSecureString | ConvertFrom-SecureString -AsPlainText)
.\scripts\build_win.ps1 -Version 1.0.1 -CertPath C:\certs\pfm.pfx
```

Скрипт ищет `signtool.exe` в `PATH`, а если не нашёл — пытается найти его в
`C:\Program Files (x86)\Windows Kits\10\bin\*\x64\`. Для подписи требуется
Windows SDK (обычно ставится вместе с Visual Studio либо отдельно).

Подпись использует RFC 3161 timestamp-сервер (`http://timestamp.digicert.com`
по умолчанию, меняется через `-TimestampUrl`) — без timestamp подпись
протухает вместе с сертификатом.

### Android — `flet build apk`

Требования:
- Python 3.12
- Android SDK (устанавливается автоматически при первом `flet build android`)

```bash
flet build apk --project PersonalFinance
```

Артефакт:
- `build/apk/app-release.apk`

> **Примечание по шифрованию на Android:** для воспроизводимой сборки APK
> рекомендуется использовать `PF_DISABLE_ENCRYPTION=1` или реализовать
> отдельную логику хранения ключа через Android Keystore.

### Docker (только для проверок, без GUI)

```powershell
docker compose run --rm checks
```

Контейнер прогоняет те же проверки, что и CI:
- `ruff`
- `mypy`
- `pytest`
- `pip-audit`
