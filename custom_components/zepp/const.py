"""Constants for the Zepp (Amazfit) integration."""

DOMAIN = "zepp"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_APPTOKEN = "apptoken"
CONF_USERID = "userid"
CONF_CNAME = "cname"
CONF_REGION_HOST = "region_host"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_MAC = "device_mac"
CONF_DEVICE_SN = "device_sn"
CONF_FIRMWARE = "firmware"

AUTH_CALLBACK_PATH = "/api/zepp/callback"
AUTH_CALLBACK_NAME = "api:zepp:callback"

DEFAULT_REGIONS = [
    "https://api-mifit-ru.huami.com",
    "https://api-mifit-de2.huami.com",
    "https://api-mifit-us2.zepp.com",
    "https://api-mifit.huami.com",
    "https://api-mifit-sg2.huami.com",
    "https://api-mifit-cn3.zepp.com",
    "https://api-mifit-cn2.huami.com",
]
