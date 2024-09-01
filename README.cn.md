# TRCloud Studio Pterodactyl 资源

<div align="center">

[中文版本](README.cn.md) | [English Version](README.md)

</div>

## 简介

本仓库包含 TRCloud Studio 使用的 Pterodactyl 面板相关资源

### 目录结构

- `docker/`: 镜像构建相关工具
  - `installer/`: 用于自动下载并安装服务端
  - `runtime/`: 运行服务端所需的环境（包括 MCDR 及相关依赖）

- `template/`: Pterodactyl 面板预设配置文件
  - 包含 YAML 和 JSON 格式版本
  - `convert.py`: 用于 YAML 和 JSON 格式互转的脚本

> **注意**：仅支持导入 JSON 格式的预设配置文件，请勿直接导入 YAML 格式文件。

## 使用说明

1. 镜像构建：使用 `docker/` 目录下的工具进行服务端安装和环境配置
2. 预设配置：从 `template/` 目录选择所需的 JSON 格式配置文件导入 Pterodactyl 面板
3. 格式转换：如需将 YAML 格式转为 JSON，请使用 `template/convert.py` 脚本

## 致谢

本仓库的大部分代码参考自 [Fallen_breath](https://github.com/Fallen-Breath) 的个人仓库：[pterodactyl-eggs](https://github.com/Fallen-Breath/pterodactyl-eggs)

## 许可证

本仓库中的所有文件均遵循 Apache 2.0 协议。详细信息请参阅 [LICENSE](LICENSE) 文件
