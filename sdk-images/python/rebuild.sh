#!/bin/bash

# 脚本：重新构建 microsandbox/python 镜像

set -e

echo "正在删除现有的 microsandbox/python:latest 镜像..."
docker rmi microsandbox/python:latest 2>/dev/null || echo "镜像不存在，跳过删除"

echo "正在构建新的 microsandbox/python:latest 镜像..."
cd ../..
docker build --platform linux/arm64 -t microsandbox/python:latest -f sdk-images/python/Dockerfile .

echo "正在创建不带标签的镜像..."
docker tag microsandbox/python:latest microsandbox/python

echo "构建完成！"
echo "验证镜像："
docker images | grep microsandbox/python