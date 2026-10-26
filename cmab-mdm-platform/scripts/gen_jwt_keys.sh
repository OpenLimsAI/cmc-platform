#!/usr/bin/env bash
# 生成 JWT RS256 密钥对
# 用法：
#   bash scripts/gen_jwt_keys.sh                  # 默认输出到 deploy/jwt/
#   bash scripts/gen_jwt_keys.sh /path/to/dir     # 自定义目录
#
# 输出文件：
#   <dir>/jwt_private.pem  (chmod 600)  ← 仅签发端读取
#   <dir>/jwt_public.pem   (chmod 644)  ← 可分发给所有验签端
#
# 生产部署：
# 1) 私钥用 secrets manager / k8s Secret / HSM 注入容器（不进 git）
# 2) JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH 指向挂载位置
# 3) JWT_ALGORITHM=RS256
set -euo pipefail

OUT_DIR="${1:-deploy/jwt}"
mkdir -p "$OUT_DIR"

PRIV="$OUT_DIR/jwt_private.pem"
PUB="$OUT_DIR/jwt_public.pem"

if [[ -f "$PRIV" || -f "$PUB" ]]; then
  echo "✗ 已存在密钥文件，请先删除或换目录：$PRIV / $PUB" >&2
  exit 1
fi

echo "→ 生成 RSA-2048 私钥: $PRIV"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$PRIV"
chmod 600 "$PRIV"

echo "→ 导出公钥: $PUB"
openssl rsa -in "$PRIV" -pubout -out "$PUB"
chmod 644 "$PUB"

echo ""
echo "✓ 完成。指纹（公钥 SHA-256）："
openssl pkey -in "$PRIV" -pubout -outform DER 2>/dev/null | sha256sum | awk '{print "  "$1}'

echo ""
echo "下一步："
echo "  1) 把以下变量加入 .env / .env.prod："
echo "       JWT_ALGORITHM=RS256"
echo "       JWT_PRIVATE_KEY_PATH=$PRIV   # 容器内绝对路径"
echo "       JWT_PUBLIC_KEY_PATH=$PUB     # 容器内绝对路径"
echo "       JWT_KEY_ID=2026-05-16       # 可选；密钥轮换时改"
echo "  2) 重启后端服务"
echo "  3) 旧 HS256 token 将立即失效，用户需重新登录"
