# Cypress Launch Scripts

英文版请看: [README.md](README.md)

Linux 下用于启动 Cypress 客户端/服务端的脚本。

## Linux 客户端使用（`cypress_launch.py`）

### 1) 前置条件

- 已安装 `umu-run`（推荐）或 `wine`
- 在 `umu-run` 下，请设置 `WINEPREFIX` 和 `PROTONPATH`，用于指定要使用的 wineprefix 和 Proton
- 从 https://github.com/dotthefox/CypressLauncher 下载最新版本的 CypressLauncher
- `--launcher-dir` 指向的目录中需要有对应的 `cypress_*.dll`

### 2) 基本命令

```bash
WINEPREFIX=/path/to/prefix \
PROTONPATH=/path/to/proton \
./cypress_launch.py \
  --game GW2 \
  --game-dir "C:/Program Files/EA Games/Plants vs Zombies Garden Warfare 2" \
  --server-ip 127.0.0.1:25200 \
  --username your_name \
  --runner umu-run \
  --launcher-dir ~/Downloads/CypressLauncher-vX.Y.Z \
  --ea-launcher "C:/Program Files/Electronic Arts/EA Desktop/.../EALauncher.exe" \
  --use-mods \
  --mod-pack Default
```

### 3) 常用参数

- `--ea-launcher`：必填，EA Launcher 可执行文件路径
- `--ea-delay-seconds`：EA 启动后等待多少秒再启动游戏，默认 `30`
- `--runner`：`umu-run` / `wine` / `native`，Linux 推荐 `umu-run`
- `--launcher-dir`：运行资源目录。请传入从 https://github.com/dotthefox/CypressLauncher 下载的最新 CypressLauncher 文件夹
- `--dry-run`：只打印启动命令，不实际启动

### 4) 路径兼容规则

`--game-dir` 和 `--ea-launcher` 都支持两种写法：

- Windows 路径：例如 `C:/Program Files/...`
- Linux 路径：例如 `/home/user/Games/...`

脚本会在 Proton 模式下自动处理路径转换。

### 5) 退出注意事项

关闭游戏后，EA App 通常仍会驻留在前台/后台。  
如果你想完全退出，请手动把 EA App 也关掉。

## 服务端

服务端使用 `cypress_launch_server.py`，不需要 `--ea-launcher`。

### Linux 服务端启动示例

```bash
WINEPREFIX=/path/to/prefix \
PROTONPATH=/path/to/proton \
./cypress_launch_server.py \
  --game GW2 \
  --game-dir /home/zerodegress/Games/ea-app/drive_c/Program\ Files/EA\ Games/Plants\ vs\ Zombies\ Garden\ Warfare\ 2 \
  --device-ip 127.0.0.1 \
  --level Level_Coop_ZombossFactory \
  --inclusion 'GameMode=GraveyardOps0;TOD=Day;HostedMode=ServerHosted' \
  --launcher-dir ~/Downloads/CypressLauncher-vX.Y.Z \
  --runner umu-run \
  --use-mods \
  --mod-pack Default
```
