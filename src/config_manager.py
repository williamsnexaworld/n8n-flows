"""
Sistema de configuración y gestión de credenciales para el agente de marketing
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
from loguru import logger
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv, set_key
import tempfile

@dataclass
class DatabaseConfig:
    """Configuración de base de datos"""
    path: str = "./data/marketing_agent.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24

@dataclass
class ScrapingConfig:
    """Configuración de scraping"""
    headless_browser: bool = True
    max_posts_per_source: int = 3
    scraping_interval_hours: int = 2
    retry_attempts: int = 3
    delay_between_requests: int = 2

@dataclass
class AIConfig:
    """Configuración de IA"""
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    max_tokens: int = 500
    temperature: float = 0.7
    brand_voice: str = "profesional_y_amigable"
    target_audience: str = "jovenes_adultos_25_45"

@dataclass
class FacebookConfig:
    """Configuración de Facebook"""
    access_token: str = ""
    page_id: str = ""
    app_id: str = ""
    app_secret: str = ""
    post_time: str = "09:00"

@dataclass
class InstagramConfig:
    """Configuración de Instagram"""
    username: str = ""
    password: str = ""
    access_token: str = ""
    business_account_id: str = ""
    post_times: List[str] = None
    
    def __post_init__(self):
        if self.post_times is None:
            self.post_times = ["09:00", "14:00", "19:00"]

@dataclass
class ContentConfig:
    """Configuración de contenido"""
    style: str = "profesional"
    content_themes: List[str] = None
    hashtag_strategy: str = "competitive_analysis"
    image_generation_enabled: bool = True
    
    def __post_init__(self):
        if self.content_themes is None:
            self.content_themes = ["motivacion", "tips", "producto", "comunidad"]

@dataclass
class LoggingConfig:
    """Configuración de logging"""
    level: str = "INFO"
    file_path: str = "./logs/marketing_agent.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    console_output: bool = True

@dataclass
class AgentConfig:
    """Configuración completa del agente"""
    agent_name: str = "AgenteMK_v1.0"
    version: str = "1.0.0"
    database: DatabaseConfig = None
    scraping: ScrapingConfig = None
    ai: AIConfig = None
    facebook: FacebookConfig = None
    instagram: InstagramConfig = None
    content: ContentConfig = None
    logging: LoggingConfig = None
    excel_file_path: str = "./data/competidores.xlsx"
    media_storage_path: str = "./media_storage"
    generated_content_path: str = "./generated_content"
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()
        if self.scraping is None:
            self.scraping = ScrapingConfig()
        if self.ai is None:
            self.ai = AIConfig()
        if self.facebook is None:
            self.facebook = FacebookConfig()
        if self.instagram is None:
            self.instagram = InstagramConfig()
        if self.content is None:
            self.content = ContentConfig()
        if self.logging is None:
            self.logging = LoggingConfig()

class ConfigManager:
    """Gestor de configuración y credenciales"""
    
    def __init__(self, config_dir: str = "./config"):
        """
        Inicializa el gestor de configuración
        
        Args:
            config_dir: Directorio donde se almacenan los archivos de configuración
        """
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "agent_config.yaml"
        self.env_file = Path(".env")
        self.credentials_file = self.config_dir / "credentials.enc"
        
        # Crear directorio si no existe
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Clave de encriptación (en producción debería estar en un lugar seguro)
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Configuración actual
        self.config: Optional[AgentConfig] = None
        
        # Cargar configuración
        self._load_config()
        
        logger.info("ConfigManager inicializado")
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Obtiene o crea una clave de encriptación"""
        key_file = self.config_dir / "encryption.key"
        
        if key_file.exists():
            try:
                with open(key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Error al leer clave de encriptación: {e}")
        
        # Crear nueva clave
        key = Fernet.generate_key()
        try:
            with open(key_file, 'wb') as f:
                f.write(key)
            
            # Hacer el archivo de solo lectura
            os.chmod(key_file, 0o600)
            logger.info("Nueva clave de encriptación creada")
            
        except Exception as e:
            logger.error(f"Error al guardar clave de encriptación: {e}")
        
        return key
    
    def _load_config(self):
        """Carga la configuración desde archivos"""
        try:
            # Cargar variables de entorno
            if self.env_file.exists():
                load_dotenv(self.env_file)
            
            # Cargar configuración YAML
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                # Convertir a objeto de configuración
                self.config = self._dict_to_config(config_data)
            else:
                # Crear configuración por defecto
                self.config = AgentConfig()
                self.save_config()
            
            # Cargar credenciales encriptadas
            self._load_encrypted_credentials()
            
            # Aplicar variables de entorno
            self._apply_env_variables()
            
            logger.info("Configuración cargada exitosamente")
            
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            self.config = AgentConfig()
    
    def _dict_to_config(self, data: Dict[str, Any]) -> AgentConfig:
        """Convierte diccionario a objeto de configuración"""
        try:
            # Crear sub-configuraciones
            database_config = DatabaseConfig(**data.get('database', {}))
            scraping_config = ScrapingConfig(**data.get('scraping', {}))
            ai_config = AIConfig(**data.get('ai', {}))
            facebook_config = FacebookConfig(**data.get('facebook', {}))
            instagram_config = InstagramConfig(**data.get('instagram', {}))
            content_config = ContentConfig(**data.get('content', {}))
            logging_config = LoggingConfig(**data.get('logging', {}))
            
            # Crear configuración principal
            config = AgentConfig(
                agent_name=data.get('agent_name', 'AgenteMK_v1.0'),
                version=data.get('version', '1.0.0'),
                database=database_config,
                scraping=scraping_config,
                ai=ai_config,
                facebook=facebook_config,
                instagram=instagram_config,
                content=content_config,
                logging=logging_config,
                excel_file_path=data.get('excel_file_path', './data/competidores.xlsx'),
                media_storage_path=data.get('media_storage_path', './media_storage'),
                generated_content_path=data.get('generated_content_path', './generated_content')
            )
            
            return config
            
        except Exception as e:
            logger.error(f"Error al convertir diccionario a configuración: {e}")
            return AgentConfig()
    
    def _config_to_dict(self, config: AgentConfig) -> Dict[str, Any]:
        """Convierte objeto de configuración a diccionario"""
        try:
            # Convertir a diccionario excluyendo credenciales sensibles
            config_dict = asdict(config)
            
            # Remover credenciales sensibles (se guardan encriptadas por separado)
            sensitive_fields = [
                'openai_api_key', 'access_token', 'app_secret', 'password'
            ]
            
            for section in config_dict.values():
                if isinstance(section, dict):
                    for field in sensitive_fields:
                        if field in section:
                            section[field] = ""
            
            return config_dict
            
        except Exception as e:
            logger.error(f"Error al convertir configuración a diccionario: {e}")
            return {}
    
    def _load_encrypted_credentials(self):
        """Carga credenciales encriptadas"""
        if not self.credentials_file.exists():
            return
        
        try:
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            
            # Aplicar credenciales a la configuración
            if 'ai' in credentials and hasattr(self.config, 'ai'):
                self.config.ai.openai_api_key = credentials['ai'].get('openai_api_key', '')
            
            if 'facebook' in credentials and hasattr(self.config, 'facebook'):
                fb_creds = credentials['facebook']
                self.config.facebook.access_token = fb_creds.get('access_token', '')
                self.config.facebook.app_secret = fb_creds.get('app_secret', '')
            
            if 'instagram' in credentials and hasattr(self.config, 'instagram'):
                ig_creds = credentials['instagram']
                self.config.instagram.password = ig_creds.get('password', '')
                self.config.instagram.access_token = ig_creds.get('access_token', '')
            
            logger.debug("Credenciales encriptadas cargadas")
            
        except Exception as e:
            logger.error(f"Error al cargar credenciales encriptadas: {e}")
    
    def _save_encrypted_credentials(self):
        """Guarda credenciales encriptadas"""
        try:
            credentials = {
                'ai': {
                    'openai_api_key': self.config.ai.openai_api_key
                },
                'facebook': {
                    'access_token': self.config.facebook.access_token,
                    'app_secret': self.config.facebook.app_secret
                },
                'instagram': {
                    'password': self.config.instagram.password,
                    'access_token': self.config.instagram.access_token
                }
            }
            
            credentials_json = json.dumps(credentials).encode()
            encrypted_data = self.cipher.encrypt(credentials_json)
            
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Hacer el archivo de solo lectura
            os.chmod(self.credentials_file, 0o600)
            
            logger.debug("Credenciales encriptadas guardadas")
            
        except Exception as e:
            logger.error(f"Error al guardar credenciales encriptadas: {e}")
    
    def _apply_env_variables(self):
        """Aplica variables de entorno a la configuración"""
        try:
            # Mapeo de variables de entorno
            env_mappings = {
                'OPENAI_API_KEY': ('ai', 'openai_api_key'),
                'FACEBOOK_ACCESS_TOKEN': ('facebook', 'access_token'),
                'FACEBOOK_PAGE_ID': ('facebook', 'page_id'),
                'FACEBOOK_APP_ID': ('facebook', 'app_id'),
                'FACEBOOK_APP_SECRET': ('facebook', 'app_secret'),
                'FACEBOOK_POST_TIME': ('facebook', 'post_time'),
                'INSTAGRAM_USERNAME': ('instagram', 'username'),
                'INSTAGRAM_PASSWORD': ('instagram', 'password'),
                'INSTAGRAM_ACCESS_TOKEN': ('instagram', 'access_token'),
                'INSTAGRAM_BUSINESS_ACCOUNT_ID': ('instagram', 'business_account_id'),
                'BRAND_VOICE': ('ai', 'brand_voice'),
                'TARGET_AUDIENCE': ('ai', 'target_audience'),
                'EXCEL_FILE_PATH': (None, 'excel_file_path'),
                'LOG_LEVEL': ('logging', 'level')
            }
            
            for env_var, (section, field) in env_mappings.items():
                value = os.getenv(env_var)
                if value:
                    if section is None:
                        # Campo de nivel superior
                        setattr(self.config, field, value)
                    else:
                        # Campo en sección
                        section_obj = getattr(self.config, section)
                        setattr(section_obj, field, value)
            
            # Manejar listas (Instagram post times)
            instagram_times = os.getenv('INSTAGRAM_POST_TIMES')
            if instagram_times:
                self.config.instagram.post_times = [time.strip() for time in instagram_times.split(',')]
            
            logger.debug("Variables de entorno aplicadas")
            
        except Exception as e:
            logger.error(f"Error al aplicar variables de entorno: {e}")
    
    def save_config(self):
        """Guarda la configuración actual"""
        try:
            # Guardar configuración principal (sin credenciales sensibles)
            config_dict = self._config_to_dict(self.config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
            # Guardar credenciales encriptadas
            self._save_encrypted_credentials()
            
            logger.info("Configuración guardada exitosamente")
            
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
    
    def get_config(self) -> AgentConfig:
        """Obtiene la configuración actual"""
        return self.config
    
    def update_config(self, **kwargs):
        """Actualiza campos específicos de la configuración"""
        try:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                else:
                    logger.warning(f"Campo de configuración desconocido: {key}")
            
            self.save_config()
            logger.info(f"Configuración actualizada: {list(kwargs.keys())}")
            
        except Exception as e:
            logger.error(f"Error al actualizar configuración: {e}")
    
    def update_section_config(self, section: str, **kwargs):
        """Actualiza campos de una sección específica"""
        try:
            if not hasattr(self.config, section):
                logger.error(f"Sección de configuración no existe: {section}")
                return
            
            section_obj = getattr(self.config, section)
            
            for key, value in kwargs.items():
                if hasattr(section_obj, key):
                    setattr(section_obj, key, value)
                else:
                    logger.warning(f"Campo desconocido en sección {section}: {key}")
            
            self.save_config()
            logger.info(f"Sección {section} actualizada: {list(kwargs.keys())}")
            
        except Exception as e:
            logger.error(f"Error al actualizar sección {section}: {e}")
    
    def validate_config(self) -> Dict[str, List[str]]:
        """Valida la configuración actual y retorna errores/advertencias"""
        errors = []
        warnings = []
        
        try:
            # Validar IA
            if not self.config.ai.openai_api_key:
                errors.append("OpenAI API key es requerida")
            
            if not self.config.ai.openai_api_key.startswith('sk-'):
                warnings.append("OpenAI API key debe comenzar con 'sk-'")
            
            # Validar Facebook
            if self.config.facebook.access_token and not self.config.facebook.page_id:
                warnings.append("Facebook page_id requerido cuando access_token está configurado")
            
            # Validar Instagram
            if not self.config.instagram.username:
                warnings.append("Instagram username no configurado")
            
            if self.config.instagram.username and not self.config.instagram.password:
                warnings.append("Instagram password requerido cuando username está configurado")
            
            # Validar rutas
            excel_path = Path(self.config.excel_file_path)
            if not excel_path.parent.exists():
                warnings.append(f"Directorio para Excel no existe: {excel_path.parent}")
            
            # Validar horarios
            try:
                hour, minute = self.config.facebook.post_time.split(':')
                if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                    errors.append("Horario de Facebook inválido")
            except:
                errors.append("Formato de horario de Facebook inválido (use HH:MM)")
            
            for time_str in self.config.instagram.post_times:
                try:
                    hour, minute = time_str.split(':')
                    if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                        errors.append(f"Horario de Instagram inválido: {time_str}")
                except:
                    errors.append(f"Formato de horario de Instagram inválido: {time_str}")
            
        except Exception as e:
            errors.append(f"Error durante validación: {e}")
        
        return {
            'errors': errors,
            'warnings': warnings
        }
    
    def export_config(self, filepath: str, include_credentials: bool = False):
        """Exporta la configuración a un archivo"""
        try:
            if include_credentials:
                # Exportar configuración completa
                config_dict = asdict(self.config)
            else:
                # Exportar sin credenciales sensibles
                config_dict = self._config_to_dict(self.config)
            
            file_path = Path(filepath)
            
            if file_path.suffix.lower() == '.json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
            else:
                # Default to YAML
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Configuración exportada a: {filepath}")
            
        except Exception as e:
            logger.error(f"Error al exportar configuración: {e}")
    
    def import_config(self, filepath: str):
        """Importa configuración desde un archivo"""
        try:
            file_path = Path(filepath)
            
            if not file_path.exists():
                logger.error(f"Archivo de configuración no existe: {filepath}")
                return
            
            with open(filepath, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    config_data = yaml.safe_load(f)
            
            # Convertir y validar
            imported_config = self._dict_to_config(config_data)
            validation = self.validate_config()
            
            if validation['errors']:
                logger.error(f"Configuración importada tiene errores: {validation['errors']}")
                return
            
            # Aplicar configuración
            self.config = imported_config
            self.save_config()
            
            logger.info(f"Configuración importada desde: {filepath}")
            
            if validation['warnings']:
                logger.warning(f"Advertencias en configuración importada: {validation['warnings']}")
            
        except Exception as e:
            logger.error(f"Error al importar configuración: {e}")
    
    def create_env_file(self):
        """Crea archivo .env con variables de entorno"""
        try:
            env_vars = {
                'AGENT_NAME': self.config.agent_name,
                'OPENAI_API_KEY': self.config.ai.openai_api_key,
                'FACEBOOK_ACCESS_TOKEN': self.config.facebook.access_token,
                'FACEBOOK_PAGE_ID': self.config.facebook.page_id,
                'FACEBOOK_APP_ID': self.config.facebook.app_id,
                'FACEBOOK_APP_SECRET': self.config.facebook.app_secret,
                'FACEBOOK_POST_TIME': self.config.facebook.post_time,
                'INSTAGRAM_USERNAME': self.config.instagram.username,
                'INSTAGRAM_PASSWORD': self.config.instagram.password,
                'INSTAGRAM_ACCESS_TOKEN': self.config.instagram.access_token,
                'INSTAGRAM_BUSINESS_ACCOUNT_ID': self.config.instagram.business_account_id,
                'INSTAGRAM_POST_TIMES': ','.join(self.config.instagram.post_times),
                'BRAND_VOICE': self.config.ai.brand_voice,
                'TARGET_AUDIENCE': self.config.ai.target_audience,
                'EXCEL_FILE_PATH': self.config.excel_file_path,
                'LOG_LEVEL': self.config.logging.level
            }
            
            # Escribir archivo .env
            with open(self.env_file, 'w', encoding='utf-8') as f:
                for key, value in env_vars.items():
                    if value:  # Solo escribir si tiene valor
                        f.write(f"{key}={value}\n")
            
            logger.info("Archivo .env creado/actualizado")
            
        except Exception as e:
            logger.error(f"Error al crear archivo .env: {e}")
    
    def get_social_configs(self) -> Dict[str, Dict]:
        """Obtiene configuraciones para redes sociales"""
        return {
            'facebook': {
                'access_token': self.config.facebook.access_token,
                'page_id': self.config.facebook.page_id,
                'app_id': self.config.facebook.app_id,
                'app_secret': self.config.facebook.app_secret
            },
            'instagram': {
                'username': self.config.instagram.username,
                'password': self.config.instagram.password,
                'access_token': self.config.instagram.access_token,
                'business_account_id': self.config.instagram.business_account_id
            }
        }
    
    def reset_to_defaults(self):
        """Resetea la configuración a valores por defecto"""
        logger.warning("Reseteando configuración a valores por defecto")
        self.config = AgentConfig()
        self.save_config()

# Funciones de utilidad
def create_default_config() -> AgentConfig:
    """Crea una configuración por defecto"""
    return AgentConfig()

def load_config_from_env() -> AgentConfig:
    """Carga configuración desde variables de entorno"""
    load_dotenv()
    
    config = AgentConfig()
    
    # Aplicar variables de entorno
    config.ai.openai_api_key = os.getenv('OPENAI_API_KEY', '')
    config.facebook.access_token = os.getenv('FACEBOOK_ACCESS_TOKEN', '')
    config.facebook.page_id = os.getenv('FACEBOOK_PAGE_ID', '')
    config.instagram.username = os.getenv('INSTAGRAM_USERNAME', '')
    config.instagram.password = os.getenv('INSTAGRAM_PASSWORD', '')
    
    return config

if __name__ == "__main__":
    # Ejemplo de uso
    config_manager = ConfigManager()
    
    # Obtener configuración
    config = config_manager.get_config()
    print(f"Agente: {config.agent_name}")
    print(f"Versión: {config.version}")
    
    # Validar configuración
    validation = config_manager.validate_config()
    if validation['errors']:
        print(f"Errores: {validation['errors']}")
    if validation['warnings']:
        print(f"Advertencias: {validation['warnings']}")
    
    # Actualizar configuración
    config_manager.update_section_config('ai', brand_voice='casual_y_divertido')
    
    # Exportar configuración
    config_manager.export_config('./config_export.yaml')
    
    print("ConfigManager funcionando correctamente")