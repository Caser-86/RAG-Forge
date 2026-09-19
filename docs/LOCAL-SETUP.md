# 本地发布 profile

这份说明用于从新环境启动 RAG-Forge，并确认它加载的是哪个知识库。项目默认保留用户已有 `.env`，不会自动覆盖它。

## 1. 安装与配置

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e ".[vector,dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

推荐的本地持久化 profile 使用 `RAG_VECTOR_STORE=qdrant_local`，索引位于 `RAG_QDRANT_PATH`，身份清单位于 `RAG_INDEX_MANIFEST_PATH`。如果使用已安装的 Qdrant Server，改用 `RAG_VECTOR_STORE=qdrant_server`、`RAG_QDRANT_URL=http://127.0.0.1:6333`；不要同时把 local path 和 server 当成同一个索引。

生产/发布 profile 不应使用 `in_memory`，它只适合测试和 `scripts/smoke.py`，进程重启后会丢失全部 chunk。

如果使用本机安装的 Qdrant Server（例如 `D:\Program Files\Qdrant Server`），先启动服务并检查 ready 状态：

```powershell
$qdrantExe = 'D:\Program Files\Qdrant Server\qdrant.exe'
$qdrantConfig = 'D:\Program Files\Qdrant Server\config\config.yaml'
Start-Process -FilePath $qdrantExe `
  -ArgumentList @('--config-path', ('"' + $qdrantConfig + '"')) `
  -WorkingDirectory 'D:\Program Files\Qdrant Server' -WindowStyle Hidden
Invoke-WebRequest http://127.0.0.1:6333/readyz -UseBasicParsing
```

`--config-path` 必须保留引号，因为默认安装路径包含空格。启动前不要删除或重置 `storage`；服务会恢复现有集合。

## 2. 运行只读环境检查

```powershell
& $python -m scripts.check_environment --json
```

检查结果中的 `runtime` 会显示：向量库后端、嵌入/生成后端、配置集合、manifest 的 active collection、manifest 兼容性、可见 chunk 数和 `knowledge_state`。`knowledge_state=empty` 表示服务可以启动但尚未形成可查询知识库；`ready` 才表示存在可用且身份匹配的持久索引。检查不会加载模型，不输出 API key。

## 3. 首次建立或迁移索引

将 `.md`、`.txt`、`.pdf` 或 `.html` 放入 `data/raw/docs/`。模型名、backend、维度、digest 或分块算法发生变化时，先执行候选重建：

```powershell
& $python -m scripts.reindex data/raw/docs --collection rag_forge_rebuild_20260912
```

候选集合名必须不存在；重建脚本会在第一次写入前拒绝 active/旧集合。成功后才写入 schema 2 manifest，旧集合不会自动删除。旧 manifest 或缺少 provider digest 时，不要通过复制文件强行绕过兼容性检查；应记录 provider 的真实 revision 到 `RAG_EMBEDDER_DIGEST` 后重新索引。

## 4. 启停与重启验收

```powershell
.\scripts\start.ps1
.\scripts\status.ps1
.\scripts\stop.ps1
```

启动脚本会检查自有 PID、端口、模型可用性，并显示当前 backend/collection/manifest；不会停止或覆盖其他进程。停止后再次启动，使用同一问题查询，确认 `indexed_chunks`、来源和回答保持一致。

Docker 环境使用 `docker-compose.yml` 时，Qdrant 使用 `qdrant_data`，API 的 manifest 与知识库 SQLite 使用独立 `api_state`；执行 API `recreate` 不应清空索引身份。可用以下隔离验收：

```powershell
.\scripts\verify_compose_recovery.ps1 -RunRecreate
```

该脚本使用随机 Compose project 和临时文档，验收后清理容器、网络和临时目录，不调用现有项目的 `down -v`。
