import hashlib
import hmac


# 使用SHA256进行密码加密（加盐）
def get_hash_password(password: str):
    # 使用固定的salt（生产环境应该使用随机salt）
    salt = "toutiao_news_salt_2024"
    # 使用HMAC-SHA256
    return hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()


# 密码验证
def verify_password(plain_password, hashed_password):
    return hmac.compare_digest(get_hash_password(plain_password), hashed_password)
