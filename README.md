# cc-codex

在 Claude Code 里输入一次 `/cc-codex:init`，为当前项目建立 Claude 规划和审查、Codex 实现和测试的协作方式。后续直接向 Claude 描述任务。每个任务有独立记录和 Codex 线程，可以在同一个项目里来回切换。

## 本地试用

准备可以正常使用的 Claude Code、已登录的 Codex CLI，以及 Python 3.9 或更新版本。插件只用 Python 标准库。Windows 支持原生 Codex 可执行文件和标准 npm 全局安装。模型调用使用你本机 CLI 的账号和配额。

在**要开发的项目目录**打开终端，以下示例使用本仓库在 Windows 上的路径。

```powershell
claude --plugin-dir "D:/codex_work/cc-codex/plugins/cc-codex"
```

进入 Claude Code 后输入下列任意一条。

```text
/cc-codex:init
/cc-codex:init 给设置页加深色模式，并在刷新后保留选择
```

第一条只初始化。第二条在验证通过后接着执行任务。探针通过正常派工入口调用一次真实 Codex，检查它能否在选定的项目读取随机值、写回文件并回传结果。测试文件随即清理。已登录或能打印版本号都不足以判定链路就绪。

Claude Code 可能会请求执行插件自带的 `scripts/bridge.py`。在交互界面核对项目路径和子命令后按需授权。无人值守的 `claude -p` 若缺少这项权限，会停在派工前。插件沿用宿主的工具授权设置。

`--plugin-dir` 只在这次启动加载插件。要在新会话里直接继续工作，可以从本地 marketplace 安装一次。在 Claude Code 中依次执行：

```text
/plugin marketplace add D:/codex_work/cc-codex
/plugin install cc-codex@cc-codex
/reload-plugins
```

推送到 GitHub 后，用 `/plugin marketplace add <账号>/<仓库>` 替换第一条。安装命令不变。Claude Code 插件的入口是 `/cc-codex:init`。[Marketplace 使用说明](https://code.claude.com/docs/en/plugin-marketplaces)

## 日常使用

```text
给设置页加一个跟随系统主题的选项。
先放下主题设置，修一下登录超时。
回到主题设置，检查窄屏布局和刷新后的状态。
这次 Codex 用 <本机可用的模型 ID>，思考强度设为 high。
```

普通对话由 Claude 判断是新目标还是已有任务的后续。若需显式进入派工流程，可输入 `/cc-codex:work <任务>`。项目默认的模型选择可以写进项目约定。单次指定只用于对应任务；显式选择不可用时由 Claude 报告。Claude 自身的模型和思考强度沿用当前 Claude Code 会话设置。

例如，若本机 Codex 目录列出 `gpt-6.2-astra`，可直接说“这次 Codex 用 gpt-6.2-astra，high”。自动派工时 Claude 可通过 bridge 的 `models` 查询本机模型描述和支持的思考档位。若要选择 Claude 自身的配置，启动时可使用 `claude --model <Claude模型> --effort high`。

## 架构

| 部件 | 职责 |
| --- | --- |
| `skills/init` | 确认目录和已有指令，执行真实环境探针，按需交接首个任务 |
| `skills/work` | 选择任务、决定派工参数、审查代码或实际页面、决定返工、向用户汇报 |
| `scripts/bridge.py` | 初始化项目，维护项目指导文件的标记区块、任务状态、工作区写锁和探针 |
| `scripts/codex_cli.py` | 以 UTF-8 标准输入调用 `codex exec --json`，解析线程 ID、完成或失败事件和最终答复 |
| `templates/` | 写入项目指导文件的长期分工约定 |

正常调用链为 **用户 → Claude → bridge → Codex CLI → 工程改动 → Claude 独立审查 → 用户**。Claude 检查工作区真实差异、相关验证和界面效果。Codex 通过简短回执报告改动和阻碍。Claude Code 通过项目指令触发这个流程，用户可以显式改派。

## 任务和会话放在哪里

```text
你的项目/
├─ CLAUDE.md                    Claude 的长期分工约定
├─ AGENTS.md                    Codex 的长期工程约定
└─ .cc-codex/                   由目录内的 .gitignore 排除
   ├─ project.json              最近一次探针结果
   ├─ writer.lock               运行期间由操作系统持有的锁
   └─ tasks/<任务ID>.json        标题、验收条件、进度、线程 ID 和审查记录
```

重新初始化只更新两处标记之间的内容。已有 `.claude/CLAUDE.md` 或根目录 `AGENTS.override.md` 时会使用相应的有效文件。任务 A 和 B 各有一个 JSON 文件；临时需求和进度都保存在各自的任务里。独立项目建议各自使用一个项目根目录。

Codex 启动后立即保存它返回的线程 ID。返工使用 `codex exec resume <thread_id>` 定向恢复。Claude 原生会话和 Codex 原生会话各自由对应 CLI 管理。任务文件仅保存接手需要的资料；同一台机器上的新 Claude 会话可以根据它继续工作。Git 克隆只迁移已提交的项目指导文件，本地线程和任务记录需要保留原工作环境才能直接续用。

任务通常经历 `planned → running → review → done`。模型调用失败会进入 `blocked`。进程意外退出可能留下 `running`，Claude 要先核对进程和实际工作区，再续接。Codex 本地线程已清理时，可以在原任务下开替代线程。每个项目同时允许一个派工进程写入；不同任务仍共享项目文件，切换任务不会撤销前一个任务留下的改动。

## 开发验证

```powershell
python -m unittest discover -s tests -v
claude plugin validate . --strict
claude plugin validate plugins/cc-codex --strict
```

回归测试使用临时目录和模拟 Codex 回执，可离线运行。要验证自己的实际环境，请在目标项目中运行 `/cc-codex:init`。初始化失败会报告原因；检查 Codex 的登录、选定模型和项目写权限，修复后可重试。
