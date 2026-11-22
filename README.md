# cc-codex

在 Claude Code 里打通 Claude 和 Codex：**Claude 负责理解需求、设计架构、审查代码，Codex（GPT）负责实际写代码和跑测试**。每个任务有独立记录和可续接的 Codex 线程，可以随时暂停、切换、第二天接着做。

```
用户 → Claude（规划/审查）→ bridge.py → Codex CLI（实现）→ 改动落到工作区 → Claude 复核 → 用户
```

## 安装

需要：已登录的 Codex CLI（`codex login status` 能看到登录状态）、Python 3.9+、Claude Code 2.1.292+。

在系统终端（PowerShell / Terminal）任意目录运行：

```shell
claude plugin install cc-codex --marketplace Ding141/cc-codex --scope user
```

`--scope user` 表示本机当前用户的所有项目都能用。已打开的 Claude Code 会话输入 `/reload-plugins` 生效；新会话自动加载。

更新插件：

```shell
claude plugin marketplace update cc-codex
claude plugin update cc-codex@cc-codex
```

试用本地源码：`claude --plugin-dir "<仓库>/plugins/cc-codex"`。

## 快速开始

1. 在项目目录启动 `claude`，输入 `/cc-codex:init`。
   这一步会真实调用一次 Codex：让它把一个随机串从临时文件读出来、写回去、并在回复里传回。三项都对上才算就绪，同时在项目里写入分工约定（`CLAUDE.md` / `AGENTS.md` 的标记区块）。
2. 直接描述你要做的事，或输入 `/cc-codex:work 给设置页加个深色模式开关，刷新后保留选择`。
   Claude 会先和你确认验收标准，再建立任务、派给 Codex，最后自己看 diff、跑测试、复核结果。
3. 之后的返工、切换、恢复都用 `/cc-codex:work`，例如「深色模式下按钮文字太暗，调高对比度」——它会沿用同一任务和同一个 Codex 线程。
4. 想看进度用 `/cc-codex:status`（只读，不会触发任何 Codex 调用）。

## 三个命令

| 命令 | 用途 |
| --- | --- |
| `/cc-codex:init [任务]` | 首次接入项目，或重新检查链路。带任务时检查通过后直接开工 |
| `/cc-codex:work [描述]` | 主流程：规划 → 派工给 Codex → 审查 → 返工/交付。也负责列出、切换项目与任务 |
| `/cc-codex:status [项目]` | 只读查看：项目是否就绪、上次检查的时间与模型、选中任务的检查点和 Codex 结果、其他未完成任务 |

`work` 里可以自然语言完成项目操作，例如「切到 D:/work/网站后台」「列出所有任务，包括已完成的」「用 T2 那个任务继续」。

## 任务、状态与恢复

任务状态流转：`planned → running → review → done`，调用失败进入 `blocked`。

- 每次派工都会先把 Codex 的线程 ID 存下来；下一次 `work` 自动 `codex exec resume <thread_id>` 接着同一个上下文。
- 进程意外中断时会留下 `running`。Claude 会先核对进程和工作区实际改动，用 checkpoint 记录真实进度，再派发剩余工作。
- 原线程丢了（比如 Codex 本地会话被清理），在同一个任务上开替代线程即可，任务编号和历史不变。
- 每个任务有一份 JSON 记录，保存标题、简报、检查点、Codex 结果、线程 ID 和模型的独立选择。
- 同一项目同一时刻只允许一个派工进程写（文件锁）；不同任务共享工作区，切换任务不会撤销前一个任务的改动。

指定 Codex 配置：直接在对话里说「这个任务用 gpt-6.2-astra，思考强度 high」。不确定本机有哪些模型时，说「列出本机 Codex 模型」——Claude 会查 `codex debug models`；目录只是候选，账号能否调用以实际派工为准。

## 跨平台

- Windows：原生 `codex.exe`、npm 全局安装（含 `codex.cmd` 垫片，插件会绕开 shell 直接调 node 入口）都支持。
- macOS / Linux：`codex` 在 PATH 即可。
- 端口和环境变量冲突时可用 `CODEX_BIN` 指定 codex 可执行文件。
- Python 解释器自动适配：技能里按 `python` → `python3` → `py -3` 的顺序使用本机存在的那个；插件只依赖标准库。
- 路径都用绝对路径传递，项目目录含空格或中文（如 `网站 后台`）也能正常工作。

## 数据放在哪里

```
你的项目/
├─ CLAUDE.md                  Claude 的长期分工约定（只在标记区块内更新）
├─ AGENTS.md                  Codex 的长期工程约定
└─ .cc-codex/                 自带 .gitignore，整目录被排除
   ├─ project.json            最近一次环境检查结果
   ├─ writer.lock             运行期间由操作系统持有的写锁
   └─ tasks/<任务ID>.json      简报、检查点、线程 ID、结果
```

本机索引 `~/.cc-codex/navigation.sqlite3` 保存已登记项目和各 Claude 会话的选择（可用 `CC_CODEX_HOME` 改位置）。模型目录、任务正文都不出本机。重新 `init` 只更新标记区块，保留任务记录和你手写的内容。

## 插件结构

| 部件 | 职责 |
| --- | --- |
| `skills/init` | 确认目录与已有指令，真实探针，写分工约定 |
| `skills/work` | 选任务、决定模型与强度、派工、审查、返工、汇报 |
| `skills/status` | 只读汇总 |
| `scripts/bridge.py` | 唯一入口：初始化、项目/任务记录、状态机、写锁 |
| `scripts/codex_cli.py` | 以 UTF-8 stdin 调用 `codex exec --json`，解析线程 ID、完成/失败事件和最终答复 |
| `scripts/navigation.py` | 本机项目登记与会话级选择（SQLite） |
| `templates/` | 写入项目的长期分工约定 |

所有桥命令输出单个 JSON 文档。脚本命令参考（调试用）：

```
bridge.py [--session 会话ID] [--project 项目根] <子命令>
  models | status [目标] | init [--model M] [--effort E]
  project list | project use 目标
  task list [--all] | task show REF | task use REF | task new 标题
  task checkpoint REF planned|review|blocked|done
  task run REF [--model M] [--effort E] [--fresh]
```

`REF` 可以是 `T1` 这样的项目内短编号，也可以是完整任务 ID。正文（简报、检查点、派工要求）通过标准输入传入。

## 常见问题

**初始化被权限拦截**：Claude Code 会先要求你授权执行插件脚本。核对命令后确认即可。若使用 auto 权限模式，注意 auto 模式会调用安全分类模型做判定——如果你的 API 代理没有配置该模型，授权会一直失败，此时请切换到「默认」或「接受编辑」模式。

**探针失败**：按报错检查 `codex login status`、`codex --version`、指定模型是否可用、项目目录写权限，修好后重跑 `/cc-codex:init`。失败期间插件不会派工，已有任务记录保留。

**任务停在 running**：说明上次进程异常退出。先确认没有残留的 codex 进程，再让 Claude 核对工作区并 checkpoint 后续接。

## 开发验证

```shell
python -m unittest discover -s tests -v
claude plugin validate . --strict
claude plugin validate plugins/cc-codex --strict
```

回归测试用临时目录和模拟 Codex 回执，离线可跑。验证真实环境请在某项目里跑 `/cc-codex:init` 和一个小任务。

## 从 0.2 升级

旧任务记录和线程 ID 继续有效：旧记录会自动获得 `T` 编号。命令面已收敛——原来的 `/cc-codex:project` 和 `/cc-codex:task` 并入 `/cc-codex:work` 与 `/cc-codex:status`，脚本里的 `new/list/show/run/checkpoint` 统一为 `task new/list/show/run/checkpoint`。

MIT License.
