"""JWT RS256 升级（ARCH2）单元测试

覆盖：
- HS256 默认配置：encode + decode 闭环
- RS256：生成临时 RSA 密钥对 + monkeypatch settings + 验签往返
- RS256 用错公钥验签 → TokenInvalidError
- RS256 缺失私钥路径配置 → RuntimeError fail-fast
- HS256 sign 后切换 RS256 验签 → 失败（算法不匹配）
- JWT_KEY_ID 写入 header.kid

注意：所有测试用 fixture 隔离 settings + 重置 jwt_keys 缓存，避免影响其他测试。
"""
import subprocess
from pathlib import Path

import pytest
from app.core import jwt_keys as keys_module
from app.core.config import settings
from app.core.exceptions import TokenInvalidError
from app.core.security import (
    create_access_token,
    decode_token,
)
from jose import jwt as jose_jwt


def _reset_keys_cache() -> None:
    """强制清空 jwt_keys 模块级缓存，下次 get_signing_key/get_verifying_key 会重新加载"""
    keys_module._signing_key = None
    keys_module._verifying_key = None
    keys_module._loaded_for = None


@pytest.fixture
def rsa_keypair(tmp_path: Path):
    """生成 RSA-2048 临时密钥对，返回 (private_pem_path, public_pem_path)"""
    priv = tmp_path / "jwt_private.pem"
    pub = tmp_path / "jwt_public.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA",
         "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(priv)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "rsa", "-in", str(priv), "-pubout", "-out", str(pub)],
        check=True, capture_output=True,
    )
    return priv, pub


@pytest.fixture
def hs256_baseline():
    """确保测试结束时算法恢复到 HS256（不污染后续测试）"""
    yield
    settings.JWT_ALGORITHM = "HS256"
    settings.JWT_PRIVATE_KEY_PATH = None
    settings.JWT_PUBLIC_KEY_PATH = None
    settings.JWT_KEY_ID = None
    _reset_keys_cache()


# ============== HS256 基线 ==============
def test_hs256_roundtrip():
    _reset_keys_cache()
    settings.JWT_ALGORITHM = "HS256"
    token = create_access_token(subject=42, extra_claims={"x": "y"})
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["x"] == "y"


# ============== RS256 ==============
def test_rs256_roundtrip(hs256_baseline, rsa_keypair):
    priv, pub = rsa_keypair
    settings.JWT_ALGORITHM = "RS256"
    settings.JWT_PRIVATE_KEY_PATH = str(priv)
    settings.JWT_PUBLIC_KEY_PATH = str(pub)
    _reset_keys_cache()

    token = create_access_token(subject=99, extra_claims={"role": "admin"})
    # 头部 alg=RS256
    header = jose_jwt.get_unverified_header(token)
    assert header["alg"] == "RS256"

    payload = decode_token(token)
    assert payload["sub"] == "99"
    assert payload["role"] == "admin"


def test_rs256_with_key_id(hs256_baseline, rsa_keypair):
    priv, pub = rsa_keypair
    settings.JWT_ALGORITHM = "RS256"
    settings.JWT_PRIVATE_KEY_PATH = str(priv)
    settings.JWT_PUBLIC_KEY_PATH = str(pub)
    settings.JWT_KEY_ID = "test-2026-05"
    _reset_keys_cache()

    token = create_access_token(subject=1)
    header = jose_jwt.get_unverified_header(token)
    assert header.get("kid") == "test-2026-05"


def test_rs256_wrong_public_key_rejected(hs256_baseline, rsa_keypair, tmp_path):
    """用 keypair A 的私钥签名，但 verify 配 keypair B 的公钥 → TokenInvalidError"""
    priv_a, _pub_a = rsa_keypair

    # 生成第二对密钥（pub_b）
    priv_b = tmp_path / "other_priv.pem"
    pub_b = tmp_path / "other_pub.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA",
         "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(priv_b)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "rsa", "-in", str(priv_b), "-pubout", "-out", str(pub_b)],
        check=True, capture_output=True,
    )

    # 用 A 私钥签
    settings.JWT_ALGORITHM = "RS256"
    settings.JWT_PRIVATE_KEY_PATH = str(priv_a)
    settings.JWT_PUBLIC_KEY_PATH = str(pub_b)  # 故意配错（B 的公钥）
    _reset_keys_cache()

    token = create_access_token(subject=1)
    with pytest.raises(TokenInvalidError):
        decode_token(token)


def test_rs256_missing_private_key_path_fail_fast(hs256_baseline):
    """RS256 但未配 path → 启动加载时 RuntimeError（fail-fast）"""
    settings.JWT_ALGORITHM = "RS256"
    settings.JWT_PRIVATE_KEY_PATH = None
    settings.JWT_PUBLIC_KEY_PATH = None
    _reset_keys_cache()

    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY_PATH"):
        create_access_token(subject=1)


def test_rs256_nonexistent_key_file_fail_fast(hs256_baseline, tmp_path):
    settings.JWT_ALGORITHM = "RS256"
    settings.JWT_PRIVATE_KEY_PATH = str(tmp_path / "nope.pem")
    settings.JWT_PUBLIC_KEY_PATH = str(tmp_path / "nope_pub.pem")
    _reset_keys_cache()

    with pytest.raises(RuntimeError, match="不存在"):
        create_access_token(subject=1)


# ============== 算法切换隔离 ==============
def test_hs256_token_rejected_under_rs256(hs256_baseline, rsa_keypair):
    """HS256 签发的 token，切到 RS256 后 decode 失败（合规：不允许 HS256 token
    在 RS256 部署里继续生效）"""
    # 先用 HS256 签
    settings.JWT_ALGORITHM = "HS256"
    _reset_keys_cache()
    hs256_token = create_access_token(subject=7)

    # 切换 RS256
    priv, pub = rsa_keypair
    settings.JWT_ALGORITHM = "RS256"
    settings.JWT_PRIVATE_KEY_PATH = str(priv)
    settings.JWT_PUBLIC_KEY_PATH = str(pub)
    _reset_keys_cache()

    with pytest.raises(TokenInvalidError):
        decode_token(hs256_token)
