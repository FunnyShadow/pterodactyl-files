# FoxRealms Pterodactyl Files

## 介绍

此处是 FoxRealms 使用的 Pterodactyl 面板相关的一些东西

- `docker` 文件夹内为镜像构建相关工具

> 其中分为两个部分, `installer` 与 `runtime`, 其介绍如下
> - `installer` 用于自动下载并安装服务端
> - `runtime` 为运行服务端所需要的环境 (包括 MCDR 即相关依赖)

- `template` 文件夹内为 Pterodactyl 面板的预设配置文件备份, 有 yaml 版本也有 json 版本, 通过位于该目录中的 `run.sh` 可进行互转

**请注意: 只有 json 版本的预设配置文件才可以导入, 请不要直接导入 yaml 版本**

## 致谢

本仓库大量代码参考 [Fallen_breath](https://github.com/Fallen-Breath) 的个人仓库: https://github.com/Fallen-Breath/pterodactyl-eggs

## 版权

本仓库中的所有文件均遵循 Apache 2.0 协议, 请查看 [LICENSE](LICENSE) 文件以获取更多信息