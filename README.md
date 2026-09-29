# GLaDOS Auto Checkin

GLaDOS 自动签到工具，支持 GitHub Actions 定时运行并通过 Telegram Bot 发送签到结果与账户状态推送。

> **声明**：
> 本项目 Fork 自 [Elykia093/GLaDOS_Auto_Checkin](https://github.com/Elykia093/GLaDOS_Auto_Checkin)。
> 为应对 GLaDOS 最新的反自动化检测机制（设备平台校验 / `Automated check-in detected`），本项目参考了 [BreakFree003/Gladoscheckin](https://github.com/BreakFree003/Gladoscheckin) 与 [Devilstore/Glados-Railgun-checkin](https://github.com/Devilstore/Glados-Railgun-checkin) 的真实浏览器行为对齐思路，进行了全面重构与优化。

---

## ✨ 功能特性

- **高度还原真实浏览器请求**：
  - 严格消除 JSON 请求体中的空格指纹（紧凑序列化为 24 字节，与前端 `axios` 行为一致）；
  - 自动移除 `Referer` 头（符合签到页面 `<meta name="referrer" content="no-referrer">` 规范）；
  - 统一 API 请求路径与 `Origin` 为 `https://glados.cloud`；
  - 彻底规避 GLaDOS 最新的设备指纹拦截机制（`code 4`）。
- **设备平台一致性（User-Agent 对齐）**：
  - 支持通过环境变量配置真实浏览器的 `navigator.userAgent`，彻底消除签到设备与登录平台不一致引发的风控；
  - 保持全流程请求 UA 恒定，杜绝跨平台随机摇号造成的拦截。
- **细分响应诊断与智能 Telegram 推送**：
  - 精准识别：首次签到成功、今日已重复签到、反作弊拦截（带服务端返回的诊断信息）、Cookie 过期失效等；
  - 消息推送动态展示当前总积分、账号剩余有效期及最终执行状态，告别盲目的“任务执行完成”。
- **支持积分自动兑换（可选）**：
  - 默认关闭；显式配置 `GLADOS_EXCHANGE_POINTS` 时，积分达标后自动兑换为会员天数（支持 100、200、500 积分）；
  - 具备前置积分门槛校验，积分不足时自动跳过，绝不发起无效网络请求。
- **GitHub Actions 无感自动签到**：
  - 支持每日定时自动化运行与手动一键触发（`workflow_dispatch`）；
  - 内置 `gh-workflow-keepalive`，防止长时间无提交被 GitHub 自动停用。

---

## 🛠️ 配置指南

### 1. Fork 本仓库
点击仓库右上角的 **Fork** 按钮，将本项目复制到你的个人 GitHub 账号下。

---

### 2. 获取参数

#### (1) 获取 `GLADOS_COOKIE`（必填）
> ⚠️ **注意**：由于 GLaDOS 会绑定登录平台与会话，**请务必在日常使用的电脑浏览器中完成登录并获取**。

1. 打开 [glados.cloud](https://glados.cloud) 并登录你的账号，进入**签到页面**（`https://glados.cloud/console/checkin`）；
2. 按键盘上的 `F12`（或右键点击页面任意位置选择“检查”）打开**开发者工具**；
3. 切换到顶部的 **Network（网络）** 选项卡；
4. 按 `F5` 或刷新页面；
5. 在网络请求列表中点击任意请求（例如 `checkin` 或 `status` 请求）；
6. 在右侧弹出的面板中选择 **Headers（标头）**，向下滚动找到 **Request Headers（请求标头）**；
7. 找到 **`Cookie`** 这一项，右键点击其完整值并复制。
   - 标准格式示例：`koa:sess=...; koa:sess.sig=...; gld:sess=...; gld:sess.sig=...`
   - **请务必复制完整内容**，其中必须包含 `gld:sess` 与 `gld:sess.sig` 字段。

#### (2) 获取 `GLADOS_USER_AGENT`（强烈建议）
GLaDOS 会在服务端将你的 Cookie 与登录时浏览器的平台进行绑定（如 Windows / macOS / Linux）。如果脚本发送的 UA 平台与登录平台不一致，会立刻触发 `Automated check-in detected` 并使 Cookie 失效。

1. 在刚才**登录 GLaDOS 的同一个浏览器窗口**中，保持开发者工具打开；
2. 切换到顶部的 **Console（控制台）** 选项卡；
3. 输入以下命令并按回车：
   ```javascript
   navigator.userAgent
   ```
4. 复制控制台输出的引号内部的完整字符串。
   - 示例：`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36`

#### (3) 获取 Telegram Bot 参数（必填）
- **`TG_BOT_TOKEN`**：在 Telegram 中与 [@BotFather](https://t.me/BotFather) 对话，输入 `/newbot` 创建一个 Bot，并复制生成的 HTTP API Token；
- **`TG_CHAT_ID`**：在 Telegram 中先向你的 Bot 发送一条消息，然后与 [@userinfobot](https://t.me/userinfobot) 对话，获取你自己的用户 ID（数字形式）。

#### (4) 积分自动兑换门槛 `GLADOS_EXCHANGE_POINTS`（选填）
默认不进行自动兑换。若希望积分累积达到门槛后自动兑换为使用天数，可配置此选项：
- `100`：满 100 积分自动兑换 10 天；
- `200`：满 200 积分自动兑换 30 天；
- `500`：满 500 积分自动兑换 100 天。

---

### 3. 在 GitHub 仓库中添加 Secrets

1. 进入你 Fork 后的个人仓库页面；
2. 点击顶部的 **Settings** 选项卡；
3. 展开左侧菜单的 **Secrets and variables** → 点击 **Actions**；
4. 在 **Repository secrets** 区域点击 **New repository secret**，依次添加以下变量：

| Secret 名称 | 是否必填 | 说明 |
| :--- | :---: | :--- |
| `GLADOS_EMAIL` | 是 | 你的 GLaDOS 注册邮箱 |
| `GLADOS_COOKIE` | 是 | 从浏览器复制的完整 Cookie 字符串 |
| `TG_BOT_TOKEN` | 是 | Telegram Bot 的 API Token |
| `TG_CHAT_ID` | 是 | 接收通知的 Telegram 账号 ID |
| `GLADOS_USER_AGENT` | 建议 | 浏览器控制台执行 `navigator.userAgent` 得到的完整字符串 |
| `GLADOS_EXCHANGE_POINTS` | 否 | 自动兑换积分门槛（默认不开启），仅支持纯数字：`100`、`200`、`500` |

---

### 4. 手动测试运行

1. 进入仓库顶部的 **Actions** 标签页；
2. 在左侧选择 **GLaDOS Auto Checkin** 工作流；
3. 点击右侧的 **Run workflow** 下拉按钮，点击绿色的 **Run workflow** 按钮手动触发；
4. 稍等片刻，检查 Actions 运行日志，同时你的 Telegram 应该会收到一条规范的推送消息。

---

## 🔔 推送消息说明

> 💡 若配置了 `GLADOS_EXCHANGE_POINTS`，**仅在积分达标且当天实际完成兑换时**，通知中才会展示 `🎁 消耗...` 兑换详情（显示消耗积分与兑换天数，并同步展示兑换后的最新积分与到期时间）；日常未触发兑换或未配置时**均不展示**该行，保持通知清爽。

- **正常签到成功（日常通知）**：
  ```text
  🕒 2026-09-29 16:38

  🔔 获得 1 积分 🎉
  📊 当前 85 积分
  🗓️ 2026-12-31 到期

  ✅ 签到成功
  ```
- **积分自动兑换成功（仅在实际触发兑换当天出现）**：
  ```text
  🕒 2026-09-29 16:38

  🔔 获得 1 积分 🎉
  📊 当前 25 积分
  🗓️ 2027-01-10 到期
  🎁 消耗 100 积分兑换 10天 🎉

  ✅ 签到成功
  ```
- **今日已签到（重复运行）**：
  ```text
  🕒 2026-09-29 16:38

  🔔 今日已签过，请明天再试 ⏳
  📊 当前 125 积分
  🗓️ 2026-12-31 到期

  ℹ️ 今日已签到
  ```
- **触发反自动化检测（平台不匹配）**：
  ```text
  🕒 2026-09-29 16:38

  🔔 反作弊拦截(设备平台不符) (原因: device-mismatch, 登录设备: Windows) ❌ (Code: 4)
  📊 当前 未知 积分
  🗓️ 2026-12-31 到期

  🚨 签到失败: 设备平台不匹配 (Code: 4)
  ```
  *(若遇到此提示，请重新登录并在控制台获取最新的 `navigator.userAgent` 更新至 `GLADOS_USER_AGENT`)*

- **Cookie 失效**：
  ```text
  🕒 2026-09-29 16:38

  🔔 Cookie已失效或无权限: 没有权限 ❌ (Code: -2)
  📊 当前 未知 积分
  🗓️ 状态查询失败: ... ❌

  🚨 签到失败: Cookie 已失效 (Code: -2)
  ```
  *(若遇到此提示，表明 Cookie 已过期，请重新登录并复制完整 Cookie)*

---

## 🤖 驱动与支持

本项目由 **Google Antigravity** 辅助开发，全流程问题分析、代码重构与浏览器指纹对齐均基于 **Gemini 3.8 Flash** 模型完成。

---

## ⚠️ 免责声明

本项目仅供个人技术研究与 Python 自动化学习交流使用。请遵守相关服务条款，作者不对因使用此脚本导致的账号封禁等后果承担责任。

---

## 📄 开源许可证

本项目基于 [GNU General Public License v3.0 (GPL-3.0)](LICENSE) 协议开源。
