# 本地 Lean 回测配置（网络受限方案）

## 问题简述

- **不挂代理**：GitHub 下载超时  
- **挂代理**：QuantConnect SSL/ProxyError  

## 方案一：代理隔离后重试 `lean init`（优先尝试）

在**项目根目录**执行，清除代理后运行 lean：

```powershell
.\scripts\run_lean_no_proxy.ps1 init
```

若 QuantConnect 直连可行，应能完成 init。若 GitHub 仍超时，尝试方案二。

## 方案二：分域代理（QuantConnect 直连，GitHub 走代理）

保持系统代理开启，让 QuantConnect 相关域名直连：

```powershell
.\scripts\run_lean_split_proxy.ps1 init
```

## 方案三：浏览器手动下载 + 脚本初始化（完全离线 init）

当以上都失败时，用浏览器下载（浏览器常能正常走代理/VPN）：

1. **下载 Lean 数据压缩包**  
   用浏览器打开并下载：  
   https://github.com/QuantConnect/Lean/archive/refs/heads/master.zip  

2. **将 zip 放到项目根目录**  
   命名为 `Lean-master.zip`

3. **执行手动初始化脚本**（在项目根目录）：

```powershell
.\scripts\setup_lean_manual.ps1
```

脚本会解压 `Data` 到 `lean_workspace\data\`，并生成 `lean.json`。

4. **创建回测项目**（需能访问 QuantConnect API）：

```powershell
.\scripts\run_lean_no_proxy.ps1 project-create TradeSwarm --language python
```

5. **复制算法与信号**：

```powershell
Copy-Item quantconnect\main.py lean_workspace\TradeSwarm\main.py -Force
New-Item -ItemType Directory -Force -Path lean_workspace\TradeSwarm\signals
Copy-Item quantconnect\signals\signals.json lean_workspace\TradeSwarm\signals\ -Force
```

6. **运行回测**：

```powershell
.\scripts\run_lean_no_proxy.ps1 backtest TradeSwarm --download-data
```

---

## 回测时仍需网络

`lean backtest --download-data` 会从 QuantConnect 拉取 NVDA 行情。若此处也报错，可尝试：

- 使用 `.\scripts\run_lean_no_proxy.ps1 backtest ...`
- 或 `.\scripts\run_lean_split_proxy.ps1 backtest ...`（视直连/代理谁更稳定）

## 备选：QuantConnect Algorithm Lab 云回测

若本地网络始终不稳定，可直接在浏览器中使用 Algorithm Lab 做回测，无需 Lean CLI。
