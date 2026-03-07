"""
Cloud Sync Module - 支持多平台配置同步

支持:
- Dropbox (默认)
- 后续可扩展 WebDAV, iCloud 等
"""

import json
import os
from pathlib import Path
from typing import Optional
import httpx
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
REMOTE_CONFIG_PATH = "/speekium/config.json"


class CloudSync:
    """云同步基类"""
    
    def __init__(self, token: str):
        self.token = token
    
    def upload(self, local_path: str) -> bool:
        raise NotImplementedError
    
    def download(self, local_path: str) -> bool:
        raise NotImplementedError
    
    def get_remote_version(self) -> Optional[str]:
        raise NotImplementedError


class DropboxSync(CloudSync):
    """Dropbox 云同步实现"""
    
    API_UPLOAD = "https://content.dropboxapi.com/2/files/upload"
    API_DOWNLOAD = "https://content.dropboxapi.com/2/files/download"
    API_METADATA = "https://api.dropboxapi.com/2/files/get_metadata"
    
    def upload(self, local_path: str) -> bool:
        """上传配置文件到 Dropbox"""
        try:
            with open(local_path, 'r') as f:
                content = f.read()
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Dropbox-API-Arg": json.dumps({
                    "path": REMOTE_CONFIG_PATH,
                    "mode": "overwrite",
                    "autorename": False,
                    "mute": False
                }),
                "Content-Type": "application/octet-stream"
            }
            
            response = httpx.post(self.API_UPLOAD, headers=headers, content=content, timeout=30)
            
            if response.status_code == 200:
                logger.info("config_uploaded_to_dropbox", path=REMOTE_CONFIG_PATH)
                return True
            else:
                logger.error("dropbox_upload_failed", status=response.status_code, body=response.text)
                return False
                
        except Exception as e:
            logger.error("dropbox_upload_error", error=str(e))
            return False
    
    def download(self, local_path: str) -> bool:
        """从 Dropbox 下载配置文件"""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Dropbox-API-Arg": json.dumps({
                    "path": REMOTE_CONFIG_PATH
                })
            }
            
            response = httpx.post(self.API_DOWNLOAD, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # 确保本地目录存在
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'w') as f:
                    f.write(response.text)
                logger.info("config_downloaded_from_dropbox", path=local_path)
                return True
            else:
                logger.error("dropbox_download_failed", status=response.status_code)
                return False
                
        except Exception as e:
            logger.error("dropbox_download_error", error=str(e))
            return False
    
    def get_remote_version(self) -> Optional[str]:
        """获取远程配置版本（用于冲突检测）"""
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            body = json.dumps({"path": REMOTE_CONFIG_PATH})
            
            response = httpx.post(self.API_METADATA, headers=headers, content=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("server_modified")
            return None
            
        except Exception as e:
            logger.error("dropbox_metadata_error", error=str(e))
            return None


def sync_to_cloud(config_path: str, token: str) -> bool:
    """同步配置到云端"""
    sync = DropboxSync(token)
    return sync.upload(config_path)


def sync_from_cloud(config_path: str, token: str) -> bool:
    """从云端同步配置"""
    sync = DropboxSync(token)
    return sync.download(config_path)


# OAuth 授权 URL 生成
DROPBOX_APP_KEY = "your_app_key"  # 需要替换为实际 App Key

def get_dropbox_auth_url(redirect_uri: str) -> str:
    """生成 Dropbox OAuth 授权 URL"""
    auth_url = (
        f"https://www.dropbox.com/oauth2/authorize?"
        f"client_id={DROPBOX_APP_KEY}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code"
    )
    return auth_url


def exchange_code_for_token(code: str, redirect_uri: str) -> Optional[str]:
    """用授权码换取 access token"""
    try:
        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": DROPBOX_APP_KEY,
            "redirect_uri": redirect_uri
        }
        
        response = httpx.post(token_url, data=data, timeout=30)
        
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception as e:
        logger.error("token_exchange_error", error=str(e))
        return None
