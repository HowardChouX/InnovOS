"""
InnovOS 本地密钥管理 — 类似 ssh-keygen 的体验。

用法:
    python scripts/keygen.py                    # 生成所有密钥
    python scripts/keygen.py --show             # 显示当前配置
    python scripts/keygen.py --rotate jwt       # 轮换 JWT 密钥
    python scripts/keygen.py --rotate admin     # 轮换管理员密码
"""

import os
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


def generate_secret(bits: int = 256) -> str:
    """生成强随机密钥。"""
    return secrets.token_hex(bits // 8)


def generate_password(length: int = 24) -> str:
    """生成可读的强密码。"""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    # 确保包含每种字符类型
    password = [
        secrets.choice("abcdefghijklmnopqrstuvwxyz"),
        secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        secrets.choice("0123456789"),
        secrets.choice("!@#$%^&*"),
    ]
    password += [secrets.choice(chars) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def read_env() -> dict[str, str]:
    """读取当前 .env 配置。"""
    config = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def write_env_value(key: str, value: str):
    """更新 .env 中的单个值。"""
    if not ENV_FILE.exists():
        print(".env 不存在，从 .env.example 复制...")
        if ENV_EXAMPLE.exists():
            ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)

    if not found:
        updated.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")
    print(f"  ✓ {key} 已更新")


def keygen():
    """生成所有密钥。"""
    print("🔑 InnovOS 密钥生成器")
    print("====================")
    print()
    print("⚠  注意：生成的密码仅显示一次，请妥善保存！")
    print()

    # 使用临时文件避免写入终端历史
    secrets_file = PROJECT_ROOT / ".secrets"
    secrets_data = {}

    config = read_env()

    if config.get("INNOVOS_JWT_SECRET", "").startswith("your-"):
        secrets_data["JWT_SECRET"] = generate_secret(256)
    if config.get("INNOVOS_ADMIN_PASSWORD", "").startswith("your-"):
        secrets_data["ADMIN_PASSWORD"] = generate_password(24)
    if config.get("POSTGRES_PASSWORD", "").startswith("your-"):
        secrets_data["DB_PASSWORD"] = generate_password(20)
    if config.get("MINIO_ROOT_PASSWORD", "").startswith("your-"):
        secrets_data["MINIO_PASSWORD"] = generate_password(20)

    if not secrets_data:
        print("所有密钥已配置，无需生成")
        return

    # 写入临时密钥文件
    print("正在生成密钥并保存到 .secrets 文件...")
    with open(secrets_file, "w", encoding="utf-8") as f:
        f.write("# InnovOS 密钥 — 请妥善保存，生成后立即删除此文件\n")
        f.write("# 生成时间: 见文件名\n\n")
        for name, value in secrets_data.items():
            f.write(f"{name}={value}\n")

    # 权限控制：仅所有者可读
    os.chmod(secrets_file, 0o600)

    # 写入 .env
    if "JWT_SECRET" in secrets_data:
        write_env_value("INNOVOS_JWT_SECRET", secrets_data["JWT_SECRET"])
    if "ADMIN_PASSWORD" in secrets_data:
        write_env_value("INNOVOS_ADMIN_PASSWORD", secrets_data["ADMIN_PASSWORD"])
    if "DB_PASSWORD" in secrets_data:
        write_env_value("POSTGRES_PASSWORD", secrets_data["DB_PASSWORD"])
    if "MINIO_PASSWORD" in secrets_data:
        write_env_value("MINIO_ROOT_PASSWORD", secrets_data["MINIO_PASSWORD"])

    # .env 也设置最小权限
    os.chmod(ENV_FILE, 0o600)

    print()
    print("✅ 密钥已生成并保存到 .env")
    print()
    print("📋 新密钥清单：")
    for name in secrets_data:
        print(f"   {name}: 已设置")
    print()
    print("⚠ 下一步:")
    print(f"   1. 查看密钥: cat {secrets_file}")
    print(f"   2. 保存到密码管理器")
    print(f"   3. 删除密钥文件: rm {secrets_file}")
    print(f"   4. .env 已设置权限 600，不要提交到 Git")


def rotate(key_name: str):
    """轮换指定密钥。"""
    print(f"🔄 轮换密钥: {key_name}")
    print()

    if key_name == "jwt":
        write_env_value("INNOVOS_JWT_SECRET", generate_secret(256))
        print("⚠ 注意：轮换 JWT 密钥会使所有现有 token 失效")
    elif key_name == "admin":
        new_pass = generate_password(24)
        write_env_value("INNOVOS_ADMIN_PASSWORD", new_pass)
        print(f"⚠ 新管理员密码: {new_pass}")
        print(f"   请立即保存！不会再次显示。")
    else:
        print(f"未知密钥: {key_name}")
        print("可用: jwt, admin")


def show():
    """显示当前配置状态。"""
    config = read_env()
    secrets_keys = [
        "INNOVOS_JWT_SECRET",
        "INNOVOS_ADMIN_PASSWORD",
        "POSTGRES_PASSWORD",
        "MINIO_ROOT_PASSWORD",
    ]
    print("📋 当前密钥状态")
    print("===============")
    for key in secrets_keys:
        value = config.get(key, "")
        if not value:
            print(f"  ✗ {key}: 未设置")
        elif value.startswith("your-"):
            print(f"  ✗ {key}: 占位符（需要生成）")
        else:
            masked = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "****"
            print(f"  ✓ {key}: {masked}")


if __name__ == "__main__":
    if "--show" in sys.argv:
        show()
    elif "--rotate" in sys.argv:
        idx = sys.argv.index("--rotate")
        key = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        rotate(key)
    else:
        keygen()
