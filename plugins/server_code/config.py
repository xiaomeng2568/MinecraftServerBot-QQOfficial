"""配置由 NoneBot 合并 .env.prod 与系统环境变量后读取。"""

from pydantic import BaseModel, Field, SecretStr, field_validator


class Config(BaseModel):
    mcs_url: str = "http://127.0.0.1:23333"
    mcs_api_key: SecretStr = SecretStr("")
    mcs_daemon_id: str = ""
    mcs_instance_uuid: str = ""
    instance_name: str = "Minecraft Server"
    admin_user_ids: str | list[str] = ""
    report_group_openid: str = ""
    total_disk_gb: float = Field(default=2000, gt=0)
    enable_hourly_report: bool = False
    report_interval_seconds: int = Field(default=3600, ge=60)
    report_first_delay_seconds: int = Field(default=180, ge=0)
    public_mc_host: str = ""
    public_mc_port: int = Field(default=25565, ge=1, le=65535)

    @field_validator("mcs_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        value = value.strip().rstrip("/")
        url = urlsplit(value)
        if (url.scheme not in {"http", "https"} or not url.hostname
                or url.username or url.password or url.query or url.fragment):
            raise ValueError("MCS_URL 必须是 HTTP(S) 面板地址，不能包含凭据或查询参数")
        return value

    def admin_ids(self) -> set[str]:
        values = self.admin_user_ids
        if isinstance(values, str):
            values = values.split(",")
        return {value.strip() for value in values
                if value.strip() and not value.strip().startswith("YOUR_")}
